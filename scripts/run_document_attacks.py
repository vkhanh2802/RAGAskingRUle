import argparse
import csv
import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient
from run_baseline_samples import RecordingGenerator

from regularag.core.config import Settings
from regularag.generation.factory import build_answer_service
from regularag.main import create_app
from regularag.retrieval.repository import RetrievedChunk


def fixture_chunks(case: dict) -> list[RetrievedChunk]:
    prefix = "synthetic:" + case["question_id"] + ":"
    return [
        RetrievedChunk(
            chunk_id=prefix + item["id"],
            document_id=prefix + item["id"],
            document_number="TEST/" + case["question_id"],
            title=item.get("title", "Synthetic adversarial fixture; not an official document"),
            source_url="https://example.test/synthetic/" + case["question_id"],
            legal_status="unknown",
            document_role="standalone",
            related_document_number=None,
            text=item["text"],
            pdf_page_start=1,
            pdf_page_end=1,
            printed_page_start=None,
            printed_page_end=None,
            score=0.99,
            content_sha256="0" * 64
            if item.get("tampered_hash")
            else sha256(item["text"].encode()).hexdigest(),
            source_sha256=sha256(("synthetic:" + item["text"]).encode()).hexdigest(),
            metadata_note=item.get("metadata_note", ""),
            freshness_status="latest_verified_corpus",
            issued_date="2026-10-10",
            latest_document_number="TEST/" + case["question_id"],
            latest_issued_date="2026-10-10",
            required_update_chunk_ids=tuple(
                prefix + cid for cid in item.get("required_updates", [])
            ),
        )
        for item in case["chunks"]
    ]


class FixtureRetriever:
    """Inject post-retrieval data, not official publication; real generator still runs."""

    def __init__(self):
        self.chunks = []

    def search(self, question, limit, mode=None, filters=None):
        return self.chunks[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exercise real Qwen with isolated injected context."
    )
    parser.add_argument(
        "--fixtures", type=Path, default=Path("tests/fixtures/document_attacks.json")
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    fixtures = json.loads(args.fixtures.read_text(encoding="utf-8"))
    settings = Settings()
    service = build_answer_service(settings)
    retriever = FixtureRetriever()
    recorder = RecordingGenerator(service.generator)
    service.retriever = retriever
    service.generator = recorder
    app = create_app(settings)
    app.state.answer_service = service
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "config": service.config.model_dump(),
                "transport": "FastAPI ASGI with injected post-retrieval fixtures "
                "and real local Qwen",
                "conditions": "No public database mutation or retrieval benchmark; "
                "synthetic hashes",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (
        TestClient(app) as client,
        (args.output_dir / "results.jsonl").open("w", encoding="utf-8") as output,
        args.summary.open("w", encoding="utf-8", newline="") as file,
    ):
        writer = None
        for case in fixtures:
            retriever.chunks = fixture_chunks(case)
            recorder.last_output = None
            started = perf_counter()
            response = client.post("/api/v1/ask", json={"question": case["question"]})
            payload = response.json()
            summary = {
                "question_id": case["question_id"],
                "http_status": response.status_code,
                "answer_status": payload.get("status", "error"),
                "failure_reason": payload.get("failure_reason") or "",
                "generation_called": recorder.last_output is not None,
                "latency_ms": round((perf_counter() - started) * 1000),
                "source_count": len(payload.get("sources", [])),
            }
            if writer is None:
                writer = csv.DictWriter(file, fieldnames=list(summary))
                writer.writeheader()
            writer.writerow(summary)
            file.flush()
            output.write(
                json.dumps(
                    {
                        "question": {key: value for key, value in case.items() if key != "chunks"},
                        "response": payload,
                        "summary": summary,
                        "generation": asdict(recorder.last_output)
                        if recorder.last_output
                        else None,
                        "retrieved_snapshot": [asdict(chunk) for chunk in retriever.chunks],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            output.flush()
            print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
