import argparse
import json
import logging
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from inspect_trace import summarize

from regularag.core.config import Settings
from regularag.core.logging import JsonFormatter
from regularag.evaluation.runner import write_json
from regularag.generation.factory import build_answer_service
from regularag.generation.local import GeneratedAnswer
from regularag.main import create_app
from regularag.retrieval.config import RagBaselineConfig


class Capture(logging.Handler):
    def __init__(self, file):
        super().__init__()
        self.file = file
        self.traces = {}

    def emit(self, record):
        if hasattr(record, "trace"):
            self.traces[record.trace["request_id"]] = record.trace
            self.file.write(JsonFormatter().format(record) + "\n")
            self.file.flush()


class SignatureOnlySelector:
    """Declared fixture: fail a source-bound selection while using real retrieval/budgeting."""

    def __init__(self, delegate):
        self.delegate = delegate

    @property
    def input_token_limit(self):
        return self.delegate.input_token_limit

    def count_prompt_tokens(self, prompt):
        return self.delegate.count_prompt_tokens(prompt)

    def generate(self, prompt):
        passages = json.loads(prompt)["passages"]
        ids = tuple(p["passage_id"] for p in passages if "signature_date" in p["supports"])
        return GeneratedAnswer("answered", "", (), "fixture", passage_ids=ids)

    def release(self):
        self.delegate.release()


def main():
    parser = argparse.ArgumentParser(description="Real development-only observability acceptance.")
    parser.add_argument("--config", type=Path, default=Path("configs/rag/final.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() or args.summary.exists():
        raise ValueError("Choose new diagnostics paths; preserve completed/failed runs")
    args.output_dir.mkdir(parents=True)
    settings = Settings(rag_config_path=args.config, pipeline_tracing_enabled=True)
    config = RagBaselineConfig.from_path(args.config)
    app = create_app(settings)
    service = build_answer_service(settings, config)
    app.state.answer_service = service
    rows = []
    with (args.output_dir / "events.jsonl").open("x", encoding="utf-8") as file:
        capture = Capture(file)
        logger = logging.getLogger("regularag.trace")
        logger.addHandler(capture)
        logger.propagate = False
        try:
            with TestClient(app) as client:
                cases = [
                    (
                        "O01",
                        "real-positive-signature",
                        {"question": "Quyết định1393 có hiệu lực từ ngày nào?"},
                    ),
                    (
                        "O02",
                        "real-development-extra-probe",
                        {
                            "question": "Theo Quyết định159 một CBHD được hướng dẫn20đề tài "
                            "mỗi học kỳ phải không?"
                        },
                    ),
                    (
                        "O03",
                        "real-clarification",
                        {
                            "question": "Em chưa đạt chuẩn ngoại ngữ thì được đăng ký "
                            "bao nhiêu tín chỉ?"
                        },
                    ),
                    (
                        "O04",
                        "real-old-filter-guard",
                        {
                            "question": "Theo790 lớp đại cương tối thiểu bao nhiêu sinh viên?",
                            "filters": {"document_ids": ["uit_790_2022"]},
                        },
                    ),
                    (
                        "O05",
                        "fixture-wrong-selection-real-retrieval",
                        {"question": "Quyết định1393 có hiệu lực từ ngày nào?"},
                    ),
                    (
                        "O06",
                        "fixture-retrieval-unavailable",
                        {"question": "Học kỳ hè tối đa bao nhiêu tín chỉ?"},
                    ),
                    ("O07", "validation", {"question": "QUESTION_CANARY", "top_k": 999}),
                ]
                original_generator, original_retriever = service.generator, service.retriever
                for case_id, kind, request in cases:
                    service.generator, service.retriever = original_generator, original_retriever
                    if case_id == "O05":
                        service.generator = SignatureOnlySelector(original_generator)
                    if case_id == "O06":

                        class Unavailable:
                            def search(self, *args, **kwargs):
                                raise OSError("password=EXCEPTION_CANARY")

                            def release_models(self):
                                original_retriever.release_models()

                        service.retriever = Unavailable()
                    response = client.post(
                        "/api/v1/ask",
                        json=request,
                        headers={"Authorization": "AUTH_CANARY", "X-Request-ID": "HEADER_CANARY"},
                    )
                    identifier = response.headers["x-request-id"]
                    assert str(UUID(identifier)) == identifier
                    trace = capture.traces[identifier]
                    assert "CANARY" not in json.dumps(trace)
                    body = response.json()
                    if response.status_code == 200:
                        assert body["request_id"] == identifier
                    attrs = {s["name"]: s["attributes"] for s in trace["spans"]}
                    if case_id == "O01":
                        assert (
                            body["status"] == "answered"
                            and "29 tháng 12 năm 2023" in body["answer"]
                        )
                        assert (
                            trace["usage"]["generation_called"]
                            and trace["usage"]["input_tokens"] > 0
                        )
                        assert attrs["context.prepare"]["passages"]
                        assert attrs["generate"]["selected_passage_ids"]
                        assert attrs["evidence.resolve"]["resolved_passage_ids"] == ["P1", "P2"]
                        assert attrs["rerank"]["input_chunks"] and attrs["rerank"]["output_chunks"]
                    elif case_id == "O02":
                        assert body["status"] == "answered" and "10 đề tài" in body["answer"]
                    elif case_id in ("O03", "O04"):
                        expected = (
                            "needs_clarification" if case_id == "O03" else "insufficient_evidence"
                        )
                        assert body["status"] == expected
                        assert trace["usage"] == {
                            "generation_called": False,
                            "input_tokens": 0,
                            "output_tokens": 0,
                        }
                    elif case_id == "O05":
                        assert body["failure_reason"] == "incomplete_passage_support"
                        assert attrs["generate"]["selected_passage_ids"] == ["P2"]
                        assert trace["usage"]["input_tokens"] is None
                    elif case_id == "O06":
                        assert response.status_code == 503
                        assert (
                            next(s for s in trace["spans"] if s["name"] == "retrieve")["error_type"]
                            == "OSError"
                        )
                    else:
                        assert (
                            response.status_code == 422 and not trace["usage"]["generation_called"]
                        )
                    assert all(s["duration_ms"] >= 0 for s in trace["spans"])
                    write_json(args.output_dir / f"{case_id}-response.json", body)
                    diagnostic = summarize(trace)
                    write_json(args.output_dir / f"{case_id}-trace.json", diagnostic)
                    row = {
                        "case_id": case_id,
                        "kind": kind,
                        "request_id": identifier,
                        "http_status": response.status_code,
                        "status": body.get("status"),
                        "failure_reason": body.get("failure_reason"),
                        "trace_spans": len(trace["spans"]),
                        "usage": trace["usage"],
                        "largest_leaf_stage": diagnostic["largest_observed_leaf_stage"],
                        "cited_passage_ids": trace["result"].get("cited_passage_ids", []),
                        "passed": True,
                    }
                    rows.append(row)
                    print(json.dumps(row), flush=True)
        except Exception as error:
            write_json(args.output_dir / "failure.json", {"type": type(error).__name__})
            raise
        finally:
            logger.removeHandler(capture)
            logger.propagate = True
    write_json(
        args.summary,
        {
            "passed": True,
            "cases": rows,
            "config": config.model_dump(mode="json"),
            "held_out_inference_requests": 0,
            "conditions": "Four real development controls; one declared bad-selector fixture "
            "with real retrieval, one backend-error fixture and one validation case. "
            "Metadata-only trace privacy canaries. No held-out tuning/accuracy benchmark; "
            "raw responses/trace records ignored.",
        },
    )


if __name__ == "__main__":
    main()
