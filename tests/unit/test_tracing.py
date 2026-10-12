import json
from dataclasses import replace
from time import sleep

import pytest

from regularag.core.tracing import MAX_ROWS, MAX_SPANS, current_trace, request_trace, stage
from regularag.generation.local import GeneratedAnswer
from regularag.generation.service import AnswerService
from regularag.retrieval.pipeline import RetrievalPipeline
from tests.unit.generation.test_service import FakeEmbedder, FakeGenerator, _chunk, _config


def make_service(selection=("P2",), usage=(512, 8)):
    config = _config()
    config.retrieval.mode = "hybrid"
    config.reranker.enabled = True
    config.generation.response_policy = "verified_passages"
    chunks = [
        replace(
            _chunk(), chunk_id="doc:effect", text="Điều 2. Có hiệu lực từ ngày ký. SOURCE_CANARY"
        ),
        replace(
            _chunk(),
            chunk_id="doc:signature",
            text="ngày 29 tháng 12 năm 2023",
            issued_date="2023-12-29",
        ),
    ]

    class Dense:
        calls = 0

        def search(self, embedding, limit):
            self.calls += 1
            return chunks

    class Keyword:
        calls = 0

        def search(self, question, limit):
            self.calls += 1
            return []

    class Reranker:
        calls = 0

        def rerank(self, question, pool):
            self.calls += 1
            return [
                replace(hit, rerank_rank=i, rerank_score=float(10 - i), rerank_windows=1)
                for i, hit in enumerate(reversed(pool), 1)
            ]

    dense, keyword, rerank = Dense(), Keyword(), Reranker()
    pipeline = RetrievalPipeline(config, FakeEmbedder(), dense, keyword, reranker=rerank)
    generated = GeneratedAnswer(
        "answered",
        "ANSWER_CANARY",
        (),
        "MODEL_CANARY",
        passage_ids=selection,
        attempts=2,
        usage_input_tokens=usage[0],
        usage_output_tokens=usage[1],
    )
    service = AnswerService(config, FakeEmbedder(), pipeline, FakeGenerator(generated))
    return service, (dense, keyword, rerank)


def test_wrong_model_selection_can_be_traced_through_real_pipeline_without_retrieving_twice():
    service, delegates = make_service()
    with request_trace() as trace:
        result = service.ask("Quyết định có hiệu lực từ ngày nào? QUESTION_CANARY")
    payload = trace.payload()
    assert result.failure_reason == "incomplete_passage_support"
    assert [delegate.calls for delegate in delegates] == [1, 1, 1]
    stages = {s["name"]: s for s in payload["spans"]}
    rerank = stages["rerank"]["attributes"]
    assert [c["chunk_id"] for c in rerank["input_chunks"]] == ["doc:effect", "doc:signature"]
    assert [c["chunk_id"] for c in rerank["output_chunks"]] == ["doc:signature", "doc:effect"]
    prepare = stages["context.prepare"]["attributes"]
    assert prepare["required_support"] == ["effective_date", "signature_date"]
    assert prepare["passages"][0]["required_passage_ids"] == ["P2"]
    assert stages["generate"]["attributes"]["selected_passage_ids"] == ["P2"]
    assert stages["evidence.resolve"]["attributes"]["failure_reason"] == result.failure_reason
    assert payload["usage"] == {"generation_called": True, "input_tokens": 512, "output_tokens": 8}
    assert payload["result"]["cited_passage_ids"] == []
    assert payload["api_cost"]["total"] == 0
    assert payload["hosting_compute_cost"] is None
    assert "CANARY" not in json.dumps(payload)
    assert current_trace() is None


def test_tracing_does_not_change_model_inputs_selection_or_backend_answer():
    service, _ = make_service(selection=("P1",))
    without = service.ask("Quyết định có hiệu lực từ ngày nào?")
    with request_trace() as trace:
        observed = service.ask("Quyết định có hiệu lực từ ngày nào?")
    assert without.status == observed.status == "answered"
    assert without.answer == observed.answer
    assert without.sources == observed.sources
    assert without.evidence_passages == observed.evidence_passages
    assert trace.result["cited_passage_ids"] == ["P1", "P2"]


def test_provider_unknown_usage_is_distinct_from_no_generation():
    service, _ = make_service(usage=(None, None))
    with request_trace() as trace:
        service.ask("Quyết định có hiệu lực từ ngày nào?")
    assert trace.usage["generation_called"] is True
    assert trace.usage["input_tokens"] is None and trace.usage["output_tokens"] is None
    service.config.behaviour.enabled = True
    with request_trace() as skipped:
        service.ask("Viết hàm Python quicksort.")
    assert skipped.usage == {"generation_called": False, "input_tokens": 0, "output_tokens": 0}
    assert next(s for s in skipped.spans if s.name == "generate").status == "skipped"


def test_nested_failed_spans_retain_latency_type_and_parent_without_exception_message():
    with (
        request_trace() as trace,
        stage("outer") as parent,
        pytest.raises(OSError),
        stage("generate") as child,
    ):
        sleep(0.005)
        raise OSError("password=EXCEPTION_CANARY private connection string")
    assert child.parent_span_id == parent.span_id
    assert child.status == "failed" and child.error_type == "OSError"
    assert child.duration_ms >= 4
    assert "CANARY" not in json.dumps(trace.payload())


def test_trace_allowlist_bounds_and_disabled_mode():
    with request_trace() as trace:
        for _ in range(MAX_SPANS + 3):
            with stage("metadata") as span:
                span.fields(
                    question="QUESTION_CANARY", prompt="MODEL_CANARY", headers="AUTH_CANARY"
                )
                span.chunks("input_chunks", [_chunk()] * (MAX_ROWS + 2))
    assert len(trace.spans) == MAX_SPANS and trace.omitted_spans == 3
    attrs = trace.spans[0].attributes
    assert attrs["input_chunks_omitted"] == 2 and len(attrs["input_chunks"]) == MAX_ROWS
    assert "CANARY" not in json.dumps(trace.payload())
    with request_trace(enabled=False) as disabled, stage("generate"):
        pass
    assert disabled.spans == []
