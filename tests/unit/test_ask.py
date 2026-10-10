from dataclasses import dataclass, replace

import pytest
from fastapi.testclient import TestClient

from regularag.core.config import Settings
from regularag.generation.service import AnswerResult, AnswerSource
from regularag.main import create_app
from regularag.retrieval.filters import RetrievalFilters


@dataclass
class FakeAnswerService:
    def ask(self, question: str, top_k: int | None = None) -> AnswerResult:
        return AnswerResult(
            status="answered",
            answer=f"Answer for {question} [S1]",
            sources=(
                AnswerSource(
                    source_id="S1",
                    chunk_id="doc:chunk:0000",
                    document_id="doc",
                    document_number="1/QD",
                    title="Document",
                    source_url="https://example.test/document",
                    pdf_page_start=1,
                    pdf_page_end=1,
                    printed_page_start=None,
                    printed_page_end=None,
                    score=0.9,
                    cited=True,
                    excerpt="Evidence",
                ),
            ),
            embedding_model="embedding-model",
            generation_model="generation-model",
            prompt_version="prompt-v1",
        )


def test_ask_endpoint_returns_answer_and_backend_sources() -> None:
    app = create_app(Settings(environment="test"))
    app.state.answer_service = FakeAnswerService()

    response = TestClient(app).post("/api/v1/ask", json={"question": "Test question"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "answered"
    assert payload["sources"][0]["source_id"] == "S1"
    assert payload["sources"][0]["cited"] is True


def test_ask_endpoint_rejects_blank_question() -> None:
    app = create_app(Settings(environment="test"))
    app.state.answer_service = FakeAnswerService()

    response = TestClient(app).post("/api/v1/ask", json={"question": "   "})

    assert response.status_code == 422


def test_ask_endpoint_returns_503_without_exposing_backend_exception() -> None:
    class UnavailableService:
        def ask(self, question: str, top_k: int | None = None) -> AnswerResult:
            raise OSError("connection failed with private connection string")

    app = create_app(Settings(environment="test"))
    app.state.answer_service = UnavailableService()

    response = TestClient(app).post("/api/v1/ask", json={"question": "Test question"})

    assert response.status_code == 503
    assert "private" not in response.text


def test_ask_endpoint_passes_retrieval_mode_and_serializes_branch_provenance() -> None:
    class ModeService:
        def ask(self, question, top_k=None, mode=None):
            assert mode == "hybrid"
            result = FakeAnswerService().ask(question, top_k)
            source = replace(
                result.sources[0],
                score=0.03,
                score_kind="rrf",
                rank=1,
                retrieval_branches=("vector", "keyword"),
                dense_rank=2,
                keyword_rank=1,
                dense_score=0.8,
                keyword_score=0.02,
                rrf_score=0.03,
            )
            return replace(result, sources=(source,), retrieval_mode=mode)

    app = create_app(Settings(environment="test"))
    app.state.answer_service = ModeService()
    response = TestClient(app).post(
        "/api/v1/ask", json={"question": "Test question", "retrieval_mode": "hybrid"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_mode"] == "hybrid"
    assert payload["sources"][0]["retrieval_branches"] == ["vector", "keyword"]
    assert payload["sources"][0]["score_kind"] == "rrf"
    assert payload["sources"][0]["dense_rank"] == 2
    assert payload["sources"][0]["keyword_rank"] == 1


def test_api_passes_filters_and_exposes_unknown_legal_status() -> None:
    class FilterService:
        def ask(self, question, top_k=None, mode=None, filters=None):
            assert filters == RetrievalFilters(document_ids=("doc",), cohort_year=2026)
            return replace(FakeAnswerService().ask(question), applied_filters=filters)

    app = create_app(Settings(environment="test"))
    app.state.answer_service = FilterService()
    response = TestClient(app).post(
        "/api/v1/ask",
        json={
            "question": "Test question",
            "filters": {"document_ids": ["doc"], "cohort_year": 2026},
        },
    )
    assert response.status_code == 200
    assert response.json()["applied_filters"]["document_ids"] == ["doc"]
    assert response.json()["sources"][0]["legal_status"] == "unknown"


@pytest.mark.parametrize(
    "filters",
    [
        {"domain": "typo_singular"},
        {"as_of": "2026-02-30"},
        {"as_of": 1704067200},
        {"as_of": "2026-10-08T00:00:00"},
        {"cohort_year": "2026"},
        {"document_ids": ["doc'; DROP TABLE documents;"]},
    ],
)
def test_api_rejects_invalid_or_unknown_filters(filters) -> None:
    app = create_app(Settings(environment="test"))
    app.state.answer_service = FakeAnswerService()
    response = TestClient(app).post(
        "/api/v1/ask", json={"question": "Test question", "filters": filters}
    )
    assert response.status_code == 422


def test_api_structured_scope_reply_is_forwarded_and_serialized():
    from regularag.generation.clarification import QuestionScope

    class ScopeService(FakeAnswerService):
        def ask(self, question, top_k=None, scope=None):
            assert scope == QuestionScope(cohort_year=2026, programmes=["cta"])
            return replace(super().ask(question, top_k), resolved_scope=scope)

    app = create_app(Settings(environment="test"))
    app.state.answer_service = ScopeService()
    response = TestClient(app).post(
        "/api/v1/ask",
        json={"question": "Test question", "scope": {"cohort_year": 2026, "programmes": ["CTA"]}},
    )
    assert response.status_code == 200
    assert response.json()["resolved_scope"]["programmes"] == ["cta"]


@pytest.mark.parametrize(
    "scope", [{"unknown": 1}, {"programmes": ["invalid"]}, {"cohort_year": "2026"}]
)
def test_api_rejects_invalid_scope(scope):
    app = create_app(Settings(environment="test"))
    app.state.answer_service = FakeAnswerService()
    response = TestClient(app).post(
        "/api/v1/ask", json={"question": "Test question", "scope": scope}
    )
    assert response.status_code == 422
