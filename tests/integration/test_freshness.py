import json
import os
from dataclasses import asdict
from hashlib import sha256

import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from regularag.generation.local import EvidenceQuote, GeneratedAnswer
from regularag.generation.service import AnswerService
from regularag.main import create_app
from regularag.retrieval.filters import RetrievalFilters
from regularag.retrieval.indexer import index_baseline
from regularag.retrieval.keyword import KeywordRepository
from regularag.retrieval.pipeline import RetrievalPipeline
from regularag.retrieval.repository import PgVectorRepository
from tests.integration.test_vector_baseline import SyntheticEmbedder
from tests.integration.test_vector_baseline import artifacts as artifacts
from tests.unit.generation.test_service import FakeGenerator

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("REGULARAG_RUN_DB_TESTS") != "1", reason="PostgreSQL opt-in"),
]


class QueryEmbedder:
    def embed_query(self, question):
        vector = np.zeros(384, dtype=np.float32)
        vector[0] = 1
        return vector


@pytest.fixture
def family(database_settings, artifacts):
    config, manifest, processed = artifacts
    index_baseline(database_settings, config, SyntheticEmbedder(), manifest, processed)
    ids = config.retrieval.eligible_document_ids
    update_text = "New cap is 70 students."
    with psycopg.connect(str(database_settings.database_url)) as connection:
        for index, document_id in enumerate(ids):
            issued = ("2024-01-01", "2025-01-01", "2026-01-01")[index]
            source_hash = str(index) * 64
            metadata = {
                "issued_date": issued,
                "effective_from": issued,
                "effective_evidence": "From signature",
                "domain": "academic_training" if index < 2 else "unrelated",
                "applies_to": "undergraduate_regular",
                "_version_review": {
                    "source_sha256": source_hash,
                    "issued_date": issued,
                    "issued_evidence": "Signature on PDF1",
                },
            }
            if index == 1:
                metadata["_document_relations"] = [
                    {
                        "kind": "amends",
                        "source_sha256": source_hash,
                        "target_document_number": "test-0",
                        "target_source_sha256": "0" * 64,
                        "affected_clauses": {"12": ["1"]},
                        "evidence_chunk_id": f"{document_id}:chunk:0000",
                        "evidence_content_sha256": sha256(update_text.encode()).hexdigest(),
                        "relation_evidence": "Article1 updates old article12clause1",
                    }
                ]
            connection.execute(
                "UPDATE documents SET metadata=%s,document_role=%s,related_document_number=%s "
                "WHERE document_id=%s",
                (
                    Jsonb(metadata),
                    "base" if index == 0 else "amendment" if index == 1 else "standalone",
                    "test-1" if index == 0 else "test-0" if index == 1 else None,
                    document_id,
                ),
            )
            text = "Old cap is 50 students." if index == 0 else update_text
            connection.execute(
                "UPDATE chunks SET text=%s,content_sha256=%s,article=%s,clauses=%s "
                "WHERE document_id=%s",
                (text, sha256(text.encode()).hexdigest(), "12", Jsonb(["1"]), document_id),
            )
    config.freshness.enabled = True
    embedder = QueryEmbedder()
    pipeline = RetrievalPipeline(
        config,
        embedder,
        PgVectorRepository(database_settings, config),
        KeywordRepository(database_settings, config),
    )
    return config, ids, embedder, pipeline


def test_latest_evidence_is_fetched_with_publication_and_hash_gates_when_dense_misses_it(
    database_settings, family
):
    config, ids, embedder, pipeline = family
    hits = pipeline.search("Class size", 5, "vector")
    assert len(hits) == 1 and hits[0].document_id == ids[1]
    assert hits[0].score_kind == "freshness_dependency"
    assert hits[0].latest_document_number == "test-1"
    assert hits[0].latest_issued_date == "2025-01-01"
    assert json.loads(json.dumps(asdict(hits[0])))["score"] == 0.0
    generated = GeneratedAnswer(
        "answered",
        "",
        ("S1",),
        "raw",
        evidence_quotes=(EvidenceQuote("S1", "New cap is 70 students."),),
    )
    app = create_app(database_settings)
    app.state.answer_service = AnswerService(config, embedder, pipeline, FakeGenerator(generated))
    payload = TestClient(app).post("/api/v1/ask", json={"question": "Class size"}).json()
    assert payload["status"] == "answered" and "50" not in payload["answer"]
    assert payload["sources"][0]["latest_document_number"] == "test-1"
    assert payload["freshness_policy"] == config.freshness.policy_version


@pytest.mark.parametrize(
    "gate", ["blocked", "partial", "allowlist", "revision", "quality", "hash", "filter"]
)
def test_missing_latest_cannot_expose_a_stale_answer_through_real_repositories(
    database_settings, family, gate
):
    config, ids, embedder, pipeline = family
    with psycopg.connect(str(database_settings.database_url)) as connection:
        if gate == "blocked":
            connection.execute(
                "UPDATE documents SET retrieval_status='blocked' WHERE document_id=%s", (ids[1],)
            )
        elif gate == "partial":
            connection.execute(
                "UPDATE documents SET coverage_status='partial' WHERE document_id=%s", (ids[1],)
            )
        elif gate == "revision":
            connection.execute(
                "UPDATE chunks SET embedding_revision=%s WHERE document_id=%s", ("f" * 40, ids[1])
            )
        elif gate == "quality":
            connection.execute(
                "UPDATE chunks SET quality_status='review_required' WHERE document_id=%s", (ids[1],)
            )
        elif gate == "hash":
            connection.execute(
                "UPDATE chunks SET content_sha256=%s WHERE document_id=%s", ("b" * 64, ids[1])
            )
    if gate == "allowlist":
        config.retrieval.eligible_document_ids = [ids[0], ids[2]]
    filters = RetrievalFilters(document_ids=[ids[0]]) if gate == "filter" else None

    class UnusedGenerator(FakeGenerator):
        def generate(self, prompt):
            raise AssertionError("Unavailable update must block generation")

    service = AnswerService(
        config,
        embedder,
        pipeline,
        UnusedGenerator(GeneratedAnswer("answered", "Old answer [S1]", ("S1",), "raw")),
    )
    result = service.ask("Class size", retrieval_mode="vector", filters=filters)
    assert result.status == "insufficient_evidence" and result.failure_reason
    assert not any(source.cited for source in result.sources)


def test_explicit_historical_date_keeps_old_version_without_future_update_gate(family):
    config, ids, embedder, pipeline = family
    service = AnswerService(
        config,
        embedder,
        pipeline,
        FakeGenerator(
            GeneratedAnswer(
                "answered",
                "",
                ("S1",),
                "raw",
                evidence_quotes=(EvidenceQuote("S1", "Old cap is 50 students."),),
            )
        ),
    )
    result = service.ask("Class size", filters=RetrievalFilters(as_of="2024-06-01"))
    assert result.status == "answered" and "50" in result.answer
    assert result.sources[0].document_id == ids[0]
    assert result.sources[0].freshness_status == "historical"


@pytest.mark.parametrize("invalid_id", [False, True])
def test_passage_api_resolves_citations_from_bound_current_database_text(
    database_settings, family, invalid_id
):
    config, ids, embedder, pipeline = family
    config.generation.response_policy = "verified_passages"

    class Selector(FakeGenerator):
        def generate(self, prompt):
            offered = json.loads(prompt)["passages"]
            selected = "P99" if invalid_id else offered[0]["passage_id"]
            return GeneratedAnswer("answered", "Invented prose", (), "raw", passage_ids=(selected,))

    app = create_app(database_settings)
    app.state.answer_service = AnswerService(config, embedder, pipeline, Selector(None))
    response = TestClient(app).post("/api/v1/ask", json={"question": "70 students?"})
    assert response.status_code == 200
    payload = response.json()
    if invalid_id:
        assert payload["status"] == "insufficient_evidence"
        assert payload["failure_reason"] == "invalid_passage_ids"
        assert not any(p["cited"] for p in payload["evidence_passages"])
    else:
        assert payload["status"] == "answered" and "70 students" in payload["answer"]
        assert "Invented" not in payload["answer"]
        assert payload["sources"][0]["document_id"] == ids[1]
        passage = payload["evidence_passages"][0]
        assert (
            passage["cited"]
            and passage["text_sha256"] == sha256(passage["text"].encode()).hexdigest()
        )
