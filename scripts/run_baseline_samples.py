import argparse
import csv
import json
import platform
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient

from regularag.core.config import Settings
from regularag.generation.factory import build_answer_service
from regularag.generation.local import GeneratedAnswer, Generator
from regularag.ingestion.manifest import load_manifest
from regularag.main import create_app
from regularag.retrieval.config import RagBaselineConfig


class RecordingGenerator:
    """Capture local diagnostics for evaluation without adding raw model output to the API."""

    def __init__(self, generator: Generator) -> None:
        self.generator = generator
        self.last_output: GeneratedAnswer | None = None

    @property
    def input_token_limit(self) -> int:
        return self.generator.input_token_limit

    def count_prompt_tokens(self, prompt: str) -> int:
        return self.generator.count_prompt_tokens(prompt)

    def generate(self, prompt: str) -> GeneratedAnswer:
        self.last_output = self.generator.generate(prompt)
        return self.last_output

    def release(self) -> None:
        release = getattr(self.generator, "release", None)
        if callable(release):
            release()


def run_samples(
    settings: Settings,
    questions_path: Path,
    output_directory: Path,
    summary_path: Path,
    limit: int,
    question_ids: set[str] | None = None,
    retrieval_mode: str | None = None,
) -> None:
    config = RagBaselineConfig.from_path(settings.rag_config_path)
    manifest = load_manifest(Path("data/manifests/documents.csv"))
    with questions_path.open(encoding="utf-8", newline="") as questions_file:
        questions = [
            row
            for row in csv.DictReader(questions_file)
            if not question_ids or row["question_id"] in question_ids
        ][:limit]
    if not questions:
        raise ValueError("No sample questions found")

    service = build_answer_service(settings)
    recorder = RecordingGenerator(service.generator)
    service.generator = recorder
    app = create_app(settings)
    app.state.answer_service = service
    output_directory.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    (output_directory / "run_metadata.json").write_text(
        json.dumps(
            {
                "started_at": datetime.now(UTC).isoformat(),
                "transport": "FastAPI ASGI TestClient with real database and models",
                "python": platform.python_version(),
                "config": config.model_dump(),
                "embedding_fingerprint": config.embedding.fingerprint,
                "questions_path": questions_path.as_posix(),
                "retrieval_mode_override": retrieval_mode,
                "packages": {
                    package: version(package)
                    for package in (
                        "torch",
                        "transformers",
                        "sentence-transformers",
                        "pgvector",
                        "llama-cpp-python",
                    )
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (
        TestClient(app) as client,
        (output_directory / "results.jsonl").open("w", encoding="utf-8") as results_file,
        summary_path.open("w", encoding="utf-8", newline="") as summary_file,
    ):
        writer = csv.DictWriter(
            summary_file,
            fieldnames=[
                "question_id",
                "http_status",
                "answer_status",
                "failure_reason",
                "latency_ms",
                "input_tokens",
                "source_count",
                "top_source_document",
                "top_source_pdf_pages",
                "document_hit_in_context",
                "generation_called",
                "passage_count",
                "retrieval_ms",
                "generation_ms",
                "selection_attempts",
            ],
        )
        writer.writeheader()
        for question in questions:
            recorder.last_output = None
            started = perf_counter()
            request = {"question": question["question"]}
            if question.get("filters_json"):
                request["filters"] = json.loads(question["filters_json"])
            if question.get("scope_json"):
                request["scope"] = json.loads(question["scope_json"])
            if retrieval_mode:
                request["retrieval_mode"] = retrieval_mode
            response = client.post("/api/v1/ask", json=request)
            latency_ms = round((perf_counter() - started) * 1000)
            payload = response.json()
            sources = payload.get("sources", [])
            top_source = sources[0] if sources else {}
            expected_documents = (
                set(question["candidate_document_numbers"].split(";"))
                if question.get("candidate_document_numbers")
                else {
                    manifest[chunk.split(":", 1)[0]]["document_number"]
                    for chunk in question.get("evidence_ids", "").split(";")
                    if chunk
                }
            )
            document_hit = any(
                source["document_number"] in expected_documents for source in sources
            )
            summary = {
                "question_id": question["question_id"],
                "http_status": response.status_code,
                "answer_status": payload.get("status", "error"),
                "failure_reason": payload.get("failure_reason") or "",
                "latency_ms": latency_ms,
                "input_tokens": payload.get("input_tokens", 0),
                "source_count": len(sources),
                "top_source_document": top_source.get("document_number", ""),
                "top_source_pdf_pages": (
                    f"{top_source['pdf_page_start']}-{top_source['pdf_page_end']}"
                    if top_source
                    else ""
                ),
                "document_hit_in_context": document_hit,
                "generation_called": recorder.last_output is not None,
                "passage_count": len(payload.get("evidence_passages", [])),
                "retrieval_ms": payload.get("retrieval_ms", 0),
                "generation_ms": payload.get("generation_ms", 0),
                "selection_attempts": payload.get("selection_attempts", 0),
            }
            writer.writerow(summary)
            summary_file.flush()
            results_file.write(
                json.dumps(
                    {
                        "question": question,
                        "response": payload,
                        "summary": summary,
                        "generation": asdict(recorder.last_output)
                        if recorder.last_output
                        else None,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            results_file.flush()
            if recorder.last_output is not None:
                (output_directory / f"{question['question_id']}-generation.json").write_text(
                    json.dumps(asdict(recorder.last_output), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            print(json.dumps(summary, ensure_ascii=False), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real sample questions through the ask API.")
    parser.add_argument("--config", type=Path, default=Path("configs/rag/baseline.json"))
    parser.add_argument(
        "--questions", type=Path, default=Path("data/manifests/question_sources.csv")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/rag-baseline-v8"))
    parser.add_argument(
        "--summary", type=Path, default=Path("data/manifests/rag_baseline_samples.csv")
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--question-id", action="append", default=[])
    parser.add_argument("--retrieval-mode", choices=("vector", "keyword", "hybrid"))
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    run_samples(
        Settings(rag_config_path=args.config),
        args.questions,
        args.output_dir,
        args.summary,
        args.limit,
        set(args.question_id),
        args.retrieval_mode,
    )


if __name__ == "__main__":
    main()
