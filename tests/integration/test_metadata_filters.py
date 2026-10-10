import os
from datetime import date
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


@pytest.fixture
def scoped(database_settings, artifacts):
    config, manifest, processed = artifacts
    index_baseline(database_settings, config, SyntheticEmbedder(), manifest, processed)
    ids = config.retrieval.eligible_document_ids
    scopes = [
        {
            "domain": "graduation_thesis",
            "document_type": "regulation",
            "applies_to": "undergraduate_regular;undergraduate_distance",
            "effective_from": "2024-03-05",
            "effective_evidence": "Article18: from signature",
        },
        {
            "domain": "academic_training",
            "document_type": "decision",
            "applies_to": "undergraduate_regular",
            "effective_from": "2023-12-29",
            "effective_evidence": "Article2: from signature",
            "cohort_from": "2026",
            "cohort_to": "2028",
            "cohort_evidence": "Explicit cohort range",
        },
        {
            "domain": "foreign_language",
            "document_type": "regulation",
            "applies_to": "undergraduate",
            "effective_from": "Học kỳ 1 năm học 2026-2027",
            "effective_evidence": "Academic period only",
            "cohort_scope": "from_2026",
        },
    ]
    with psycopg.connect(str(database_settings.database_url)) as connection:
        for document_id, metadata in zip(ids, scopes, strict=True):
            connection.execute(
                "UPDATE documents SET metadata=%s WHERE document_id=%s",
                (Jsonb(metadata), document_id),
            )
            connection.execute(
                "UPDATE chunks SET text=%s,content_sha256=%s WHERE document_id=%s",
                ("SharedQuery", sha256(b"SharedQuery").hexdigest(), document_id),
            )
    return config, ids


class QueryEmbedder:
    def embed_query(self, question):
        vector = np.zeros(384, dtype=np.float32)
        vector[:3] = 1
        return vector


@pytest.mark.parametrize("mode", ["vector", "keyword", "hybrid"])
@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"document_ids": ["@0"]}, {0}),
        ({"document_ids": ["@0", "@2"]}, {0, 2}),
        ({"document_ids": ["unlisted"]}, set()),
        ({"domains": ["graduation_thesis"]}, {0}),
        ({"document_types": ["decision"]}, {1}),
        ({"applies_to": ["undergraduate_regular"]}, {0, 1}),
        ({"applies_to": ["undergraduate_distance"]}, {0}),
        ({"applies_to": ["joint_program"]}, set()),
        ({"domains": ["foreign_language"], "document_types": ["decision"]}, set()),
        ({"cohort_year": 2026}, {1}),
        ({"cohort_year": 2028}, {1}),
        ({"cohort_year": 2029}, set()),
        ({"as_of": "2024-03-05"}, {0, 1}),
        ({"as_of": "2023-12-29"}, {1}),
        ({"as_of": "2023-12-28"}, set()),
        ({"document_ids": ["@0"], "as_of": "2024-03-04"}, set()),
    ],
)
def test_all_modes_apply_identical_filters_before_ranking(
    database_settings, scoped, mode, values, expected
):
    config, ids = scoped
    values = dict(values)
    if "document_ids" in values:
        values["document_ids"] = [
            ids[int(v[1:])] if v.startswith("@") else v for v in values["document_ids"]
        ]
    pipeline = RetrievalPipeline(
        config,
        QueryEmbedder(),
        PgVectorRepository(database_settings, config),
        KeywordRepository(database_settings, config),
    )
    hits = pipeline.search("SharedQuery", 20, mode, RetrievalFilters.model_validate(values))

    assert {hit.document_id for hit in hits} == {ids[index] for index in expected}
    assert all(hit.legal_status == "unknown" for hit in hits)


@pytest.mark.parametrize(
    "end,evidence,expected",
    [
        ("2024-03-06", "Explicit last applicable date", True),
        ("2024-03-05", "Explicit last applicable date", False),
        ("2024-03-06", "", False),
        ("2024-02-30", "Invalid date", False),
    ],
)
def test_date_upper_bound_requires_evidence_and_is_inclusive(
    database_settings, scoped, end, evidence, expected
):
    config, ids = scoped
    with psycopg.connect(str(database_settings.database_url)) as connection:
        connection.execute(
            "UPDATE documents SET metadata=metadata || %s WHERE document_id=%s",
            (Jsonb({"effective_to": end, "effective_to_evidence": evidence}), ids[0]),
        )
    filters = RetrievalFilters(document_ids=(ids[0],), as_of=date(2024, 3, 6))
    query = QueryEmbedder().embed_query("")
    assert bool(PgVectorRepository(database_settings, config).search(query, 5, filters)) == expected
    assert (
        bool(KeywordRepository(database_settings, config).search("SharedQuery", 5, filters))
        == expected
    )


def test_missing_or_invalid_scope_never_infers_dates_or_cohort_from_title(
    database_settings, scoped
):
    config, ids = scoped
    with psycopg.connect(str(database_settings.database_url)) as connection:
        connection.execute(
            "UPDATE documents SET metadata=%s, title='From cohort2026; issued2024' "
            "WHERE document_id=%s",
            (
                Jsonb(
                    {
                        "effective_from": "2024-02-30",
                        "effective_evidence": "Invalid date",
                        "cohort_from": "from2026",
                        "cohort_evidence": "Invalid bounds",
                    }
                ),
                ids[0],
            ),
        )
        row = connection.execute(
            "SELECT effective_from_date,cohort_from FROM documents WHERE document_id=%s",
            (ids[0],),
        ).fetchone()
    assert row == (None, None)
    assert (
        KeywordRepository(database_settings, config).search(
            "SharedQuery", 5, RetrievalFilters(document_ids=(ids[0],), cohort_year=2026)
        )
        == []
    )


@pytest.mark.parametrize("mode", ["vector", "keyword", "hybrid"])
def test_api_filters_flow_through_real_repositories_with_scope_provenance(
    database_settings, scoped, mode
):
    config, ids = scoped
    embedder = QueryEmbedder()
    pipeline = RetrievalPipeline(
        config,
        embedder,
        PgVectorRepository(database_settings, config),
        KeywordRepository(database_settings, config),
    )
    generated = GeneratedAnswer(
        "answered", "", ("S1",), "raw", evidence_quotes=(EvidenceQuote("S1", "SharedQuery"),)
    )
    app = create_app(database_settings)
    app.state.answer_service = AnswerService(config, embedder, pipeline, FakeGenerator(generated))
    response = TestClient(app).post(
        "/api/v1/ask",
        json={
            "question": "SharedQuery",
            "retrieval_mode": mode,
            "filters": {"domains": ["graduation_thesis"], "as_of": "2024-03-05"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "answered"
    assert payload["applied_filters"]["as_of"] == "2024-03-05"
    assert payload["sources"][0]["document_id"] == ids[0]
    assert payload["sources"][0]["domain"] == "graduation_thesis"
    assert payload["sources"][0]["effective_from_date"] == "2024-03-05"
    assert payload["sources"][0]["legal_status"] == "unknown"
    assert any("chưa xác minh" in warning for warning in payload["warnings"])
