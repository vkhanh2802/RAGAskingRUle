import os
from hashlib import sha256

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from regularag.generation.local import GeneratedAnswer
from regularag.generation.service import AnswerService
from regularag.main import create_app
from regularag.retrieval.keyword import KeywordRepository
from regularag.retrieval.pipeline import RetrievalPipeline
from regularag.retrieval.repository import PgVectorRepository
from tests.integration.test_metadata_filters import QueryEmbedder
from tests.integration.test_metadata_filters import scoped as scoped
from tests.integration.test_vector_baseline import artifacts as artifacts
from tests.unit.generation.test_service import FakeGenerator

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("REGULARAG_RUN_DB_TESTS") != "1", reason="PostgreSQL opt-in"),
]


@pytest.mark.parametrize("year,expected", [(2025, "insufficient_evidence"), (2026, "answered")])
def test_question_scope_flows_into_sql_and_cannot_reuse_wrong_cohort(
    database_settings, scoped, year, expected
):
    config, ids = scoped
    config.behaviour.enabled = True
    config.generation.response_policy = "verified_passages"
    text = "Sinh viên CTC sau hai học kỳ chưa đạt ngoại ngữ chỉ đăng ký tối đa 16 tín chỉ."
    with psycopg.connect(str(database_settings.database_url)) as connection:
        connection.execute(
            "UPDATE documents SET metadata=metadata || %s WHERE document_id=%s",
            (Jsonb({"domain": "foreign_language", "applies_to": "undergraduate_regular"}), ids[1]),
        )
        connection.execute(
            "UPDATE chunks SET text=%s,content_sha256=%s WHERE document_id=%s",
            (text, sha256(text.encode()).hexdigest(), ids[1]),
        )

    class Selector(FakeGenerator):
        def generate(self, prompt):
            assert expected == "answered", "Wrong cohort must not reach generation"
            return GeneratedAnswer("answered", "", (), "raw", passage_ids=("P1",))

    embedder = QueryEmbedder()
    pipeline = RetrievalPipeline(
        config,
        embedder,
        PgVectorRepository(database_settings, config),
        KeywordRepository(database_settings, config),
    )
    app = create_app(database_settings)
    app.state.answer_service = AnswerService(config, embedder, pipeline, Selector(None))
    response = TestClient(app).post(
        "/api/v1/ask",
        json={
            "question": f"Em khóa{year} hệ chính quy chương trìnhCTC "
            "sau hai học kỳ chưa đạt ngoại ngữ bị giới hạn thế nào?"
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == expected
    assert payload["requested_filters"]["cohort_year"] is None
    assert payload["applied_filters"]["cohort_year"] == year
    if expected == "answered":
        assert {s["document_id"] for s in payload["sources"]} == {ids[1]}
        assert "16" in payload["answer"]


def test_missing_scope_response_is_structured_and_has_no_citations(database_settings, scoped):
    config, _ = scoped
    config.behaviour.enabled = True
    embedder = QueryEmbedder()
    pipeline = RetrievalPipeline(
        config,
        embedder,
        PgVectorRepository(database_settings, config),
        KeywordRepository(database_settings, config),
    )
    app = create_app(database_settings)
    app.state.answer_service = AnswerService(config, embedder, pipeline, FakeGenerator(None))
    payload = (
        TestClient(app)
        .post("/api/v1/ask", json={"question": "Em cần đạt chuẩn ngoại ngữ nào để tốt nghiệp?"})
        .json()
    )
    assert payload["status"] == "needs_clarification"
    assert set(payload["clarification"]["required_fields"]) == {
        "cohort_year",
        "applies_to",
        "programmes",
    }
    assert not payload["sources"] and not payload["evidence_passages"]
    assert payload["behaviour_policy"] == config.behaviour.policy_version
