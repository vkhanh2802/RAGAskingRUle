from dataclasses import replace

import numpy as np
import pytest

from regularag.generation.local import EvidenceQuote, GeneratedAnswer
from regularag.generation.service import AnswerService
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.filters import RetrievalFilters
from regularag.retrieval.repository import RetrievedChunk


class FakeEmbedder:
    @property
    def dimension(self) -> int:
        return 2

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        return [np.array([1, 0], dtype=np.float32) for _ in texts]

    def embed_query(self, text: str) -> np.ndarray:
        return np.array([1, 0], dtype=np.float32)


class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks

    def search(self, query_embedding, limit: int) -> list[RetrievedChunk]:
        return self.chunks[:limit]


class FakeGenerator:
    def __init__(self, answer: GeneratedAnswer) -> None:
        self.answer = answer

    @property
    def input_token_limit(self) -> int:
        return 4096

    def count_prompt_tokens(self, prompt: str) -> int:
        return len(prompt.split())

    def generate(self, prompt: str) -> GeneratedAnswer:
        return self.answer


def _config() -> RagBaselineConfig:
    return RagBaselineConfig.model_validate(
        {
            "pipeline_version": "test",
            "embedding": {
                "model_name": "test-embedding",
                "model_revision": "a" * 40,
                "dimension": 2,
                "device": "cpu",
                "batch_size": 2,
                "max_sequence_tokens": 32,
                "window_overlap_tokens": 4,
                "query_prefix": "query: ",
                "document_prefix": "passage: ",
            },
            "retrieval": {
                "top_k": 5,
                "minimum_score": 0.5,
                "eligible_document_ids": ["doc"],
            },
            "generation": {
                "model_name": "test-generator",
                "model_revision": "b" * 40,
                "device": "cpu",
                "max_new_tokens": 32,
                "context_chunks": 2,
                "prompt_version": "test-prompt",
            },
        }
    )


def _chunk(score: float = 0.8) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="doc:chunk:0000",
        document_id="doc",
        document_number="1/QD",
        title="Test document",
        source_url="https://example.test/document",
        legal_status="unknown",
        document_role="standalone",
        related_document_number=None,
        text="Evidence text.",
        pdf_page_start=1,
        pdf_page_end=1,
        printed_page_start=None,
        printed_page_end=None,
        score=score,
    )


def test_answer_service_keeps_only_backend_validated_citations() -> None:
    generated = GeneratedAnswer("answered", "Answer [S1]", ("S1",), "raw")
    service = AnswerService(
        _config(),
        FakeEmbedder(),
        FakeRetriever([_chunk()]),
        FakeGenerator(generated),
    )

    result = service.ask("Question")

    assert result.status == "answered"
    assert len(result.sources) == 1
    assert result.sources[0].source_id == "S1"
    assert result.sources[0].cited is True


def test_answer_service_abstains_when_model_omits_citations() -> None:
    generated = GeneratedAnswer("answered", "Unsupported answer", (), "raw")
    service = AnswerService(
        _config(),
        FakeEmbedder(),
        FakeRetriever([_chunk()]),
        FakeGenerator(generated),
    )

    result = service.ask("Question")

    assert result.status == "insufficient_evidence"
    assert not any(source.cited for source in result.sources)


def test_answer_service_skips_generation_below_score_threshold() -> None:
    generated = GeneratedAnswer("answered", "Should not be used", ("S1",), "raw")
    service = AnswerService(
        _config(),
        FakeEmbedder(),
        FakeRetriever([replace(_chunk(), score=0.2)]),
        FakeGenerator(generated),
    )

    result = service.ask("Question")

    assert result.status == "insufficient_evidence"
    assert result.answer.startswith("Không tìm thấy")


@pytest.mark.parametrize(
    ("answer", "source_ids"),
    [
        ("Answer [S1] [S9]", ("S1", "S9")),
        ("Answer [S9]", ("S1",)),
        ("Answer with no inline citation", ("S1",)),
    ],
)
def test_answer_service_rejects_any_invalid_or_mismatched_citation(
    answer: str, source_ids: tuple[str, ...]
) -> None:
    service = AnswerService(
        _config(),
        FakeEmbedder(),
        FakeRetriever([_chunk()]),
        FakeGenerator(GeneratedAnswer("answered", answer, source_ids, "raw")),
    )

    result = service.ask("Question")

    assert result.status == "insufficient_evidence"
    assert result.failure_reason == "invalid_citations"
    assert not any(source.cited for source in result.sources)


def test_answer_service_abstains_if_cited_base_is_missing_its_amendment() -> None:
    chunk = replace(_chunk(), document_role="base", related_document_number="2/QD")
    service = AnswerService(
        _config(),
        FakeEmbedder(),
        FakeRetriever([chunk]),
        FakeGenerator(GeneratedAnswer("answered", "Answer [S1]", ("S1",), "raw")),
    )

    result = service.ask("Question")

    assert result.status == "insufficient_evidence"
    assert result.failure_reason == "missing_amendment"
    assert "2/QD" in result.answer
    assert result.warnings


def test_verified_quote_mode_does_not_return_the_models_unverified_explanation() -> None:
    config = _config()
    config.generation.response_policy = "verified_quotes"
    generated = GeneratedAnswer(
        "answered",
        "An invented explanation.",
        ("S1",),
        "raw",
        evidence_quotes=(EvidenceQuote("S1", "Evidence text."),),
    )
    service = AnswerService(
        config, FakeEmbedder(), FakeRetriever([_chunk()]), FakeGenerator(generated)
    )

    result = service.ask("Question")

    assert result.status == "answered"
    assert result.answer == "“Evidence text.” [S1]"
    assert "invented" not in result.answer


def test_verified_quote_mode_rejects_a_changed_threshold() -> None:
    config = _config()
    config.generation.response_policy = "verified_quotes"
    generated = GeneratedAnswer(
        "answered",
        "A plausible answer",
        ("S1",),
        "raw",
        evidence_quotes=(EvidenceQuote("S1", "Evidence threshold is 6 points."),),
    )
    chunk = replace(_chunk(), text="Evidence threshold is 5 points.")
    service = AnswerService(
        config, FakeEmbedder(), FakeRetriever([chunk]), FakeGenerator(generated)
    )

    result = service.ask("Question")

    assert result.status == "insufficient_evidence"
    assert result.failure_reason == "unverified_quote"


def test_indexed_amendment_must_also_be_available_in_the_context() -> None:
    base = replace(
        _chunk(), document_role="base", related_document_number="2/QD", related_document_ready=True
    )
    service = AnswerService(
        _config(),
        FakeEmbedder(),
        FakeRetriever([base]),
        FakeGenerator(GeneratedAnswer("answered", "Answer [S1]", ("S1",), "raw")),
    )

    result = service.ask("Question")

    assert result.status == "insufficient_evidence"
    assert result.failure_reason == "amendment_not_in_context"


@pytest.mark.parametrize("kind", ["ts_rank_cd", "rrf"])
def test_keyword_and_fusion_scores_are_not_compared_to_a_cosine_threshold(kind: str) -> None:
    hit = replace(_chunk(), score=0.01, score_kind=kind, keyword_rank=1, keyword_score=0.01)
    service = AnswerService(
        _config(),
        FakeEmbedder(),
        FakeRetriever([hit]),
        FakeGenerator(GeneratedAnswer("answered", "Answer [S1]", ("S1",), "raw")),
    )

    result = service.ask("Question")

    assert result.status == "answered"
    assert result.sources[0].score_kind == kind
    assert result.sources[0].keyword_rank == 1


def test_service_returns_filters_and_time_caveat_even_when_no_evidence_matches() -> None:
    class FilteredRetriever:
        def search(self, question, limit, filters=None):
            assert filters.as_of.isoformat() == "2023-01-01"
            return []

    class UnusedGenerator(FakeGenerator):
        def generate(self, prompt):
            raise AssertionError("No matching evidence must not call generation")

    filters = RetrievalFilters(as_of="2023-01-01")
    service = AnswerService(
        _config(),
        FakeEmbedder(),
        FilteredRetriever(),
        UnusedGenerator(GeneratedAnswer("answered", "", (), "")),
    )
    result = service.ask("Question", filters=filters)
    assert result.status == "insufficient_evidence"
    assert result.applied_filters == filters
    assert any("không xác nhận" in warning for warning in result.warnings)
