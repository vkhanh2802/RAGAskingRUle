import json
import os
import platform
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient

from regularag.evaluation.dataset import canonical_hash
from regularag.evaluation.instrumentation import RecordingGenerator, RecordingRetriever
from regularag.evaluation.integrity import verify_live_dataset
from regularag.evaluation.metrics import (
    EVALUATOR_VERSION,
    AnswerReview,
    answer_aggregate,
    operation_aggregate,
    retrieval_aggregate,
    score_case,
)
from regularag.generation.factory import build_answer_service
from regularag.main import create_app


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def runtime_metadata(config, lock, split, cases):
    root = Path.cwd()
    paths = sorted((root / "src/regularag").rglob("*.py"))
    paths.append(root / "scripts/run_evaluation.py")
    from hashlib import sha256

    source_hashes = {
        path.relative_to(root).as_posix(): sha256(path.read_bytes()).hexdigest() for path in paths
    }
    try:
        from psutil import virtual_memory

        ram_bytes = virtual_memory().total
    except ImportError:
        ram_bytes = None
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "started_at": datetime.now(UTC).isoformat(),
        "split": split,
        "question_ids": [case.question_id for case in cases],
        "dataset_sha256": lock["dataset_sha256"],
        "corpus_sha256": lock["corpus_sha256"],
        "held_out_sha256": lock["held_out_sha256"],
        "config": config.model_dump(mode="json"),
        "config_sha256": canonical_hash(config.model_dump(mode="json")),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "git_status": subprocess.check_output(["git", "status", "--porcelain"], text=True),
        "runtime_source_sha256": canonical_hash(source_hashes),
        "runtime_source_files": source_hashes,
        "hardware": {
            "os": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "ram_total_bytes": ram_bytes,
            "python": platform.python_version(),
        },
        "packages": {
            name: version(name)
            for name in ("torch", "transformers", "sentence-transformers", "llama-cpp-python")
        },
        "concurrency": 1,
        "offline_cache_flags": {
            key: os.getenv(key) for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
        },
        "warm_cold": "No warmup; first process request cold, subsequent OS/HF cache warm; "
        "low-memory per-request model release/reload enabled according to config",
        "transport": "Real FastAPI ASGI TestClient, PostgreSQL and pinned local models",
        "answer_top_k": config.retrieval.top_k,
        "retrieval_metric_top_k": 10,
        "rank_capture": "Same real ordered pool; companion reservation at10 for metrics, "
        "original top-k/context/budget for answers; no second inference",
        "judge": "Manual required-fact/quote-block review, response-hash-bound; no LLM judge",
        "held_out_inference_requests": len(cases) if split == "test" else 0,
        "state": "running",
    }


def load_reviews(path):
    if path is None:
        return {}
    values = [
        AnswerReview.model_validate(row) for row in json.loads(path.read_text(encoding="utf-8"))
    ]
    if len({row.question_id for row in values}) != len(values):
        raise ValueError("Duplicate manual review question")
    return {row.question_id: row for row in values}


def export_review_packet(directory, cases, predictions, evidence):
    lines = ["# Actual development/test answer review", "", "No gold was sent to the models."]
    for case, prediction in zip(cases, predictions, strict=True):
        response = prediction["response"]
        lines.extend(
            [
                "",
                "## " + case.question_id + " — " + case.category,
                case.question,
                "Expected: " + case.expected_status,
                "Actual: "
                + response.get("status", "error")
                + " / "
                + str(response.get("failure_reason")),
                "Response SHA: " + canonical_hash(response),
                "Required facts:",
                *[f"- {fact.fact_id}: {fact.statement}" for fact in case.required_facts],
                "Required clarification: " + ", ".join(case.required_clarifications),
                "Must not claim: " + "; ".join(case.must_not_claim),
                "Answer:",
                response.get("answer", ""),
                "Cited blocks:",
            ]
        )
        for p in response.get("evidence_passages", []):
            if p["cited"]:
                lines.append(
                    f"- {p['passage_id']} / {p['source_id']} / {p['chunk_id']} "
                    f"{p['char_start']}:{p['char_end']}"
                )
        fields = (response.get("clarification") or {}).get("required_fields", [])
        lines.append("Actual clarification fields: " + ", ".join(fields))
        lines.append("Gold locators:")
        for eid in case.support_evidence_ids:
            span = evidence[eid]
            lines.append(
                f"- {eid}: {span.chunk_id} {span.char_start}:{span.char_end}; " + span.locator
            )
        lines.extend(["Gold reference: " + case.reference_answer, ""])
    (directory / "review_packet.md").write_text("\n\n".join(lines), encoding="utf-8")


def write_reports(directory, cases, predictions, evidence, chunks, review_path=None):
    reviews = load_reviews(review_path)
    if not set(reviews).issubset(case.question_id for case in cases):
        raise ValueError("Review contains questions outside the selected run")
    if len(predictions) != len(cases) or [p["question_id"] for p in predictions] != [
        c.question_id for c in cases
    ]:
        raise ValueError("Missing/duplicate/out-of-order predictions; do not hide failed cases")
    rows = [
        score_case(c, p, evidence, chunks, reviews.get(c.question_id))
        for c, p in zip(cases, predictions, strict=True)
    ]
    categories = sorted({row["category"] for row in rows})
    retrieval = {
        "evaluator_version": EVALUATOR_VERSION,
        "overall": retrieval_aggregate(rows),
        "by_category": {
            category: retrieval_aggregate([r for r in rows if r["category"] == category])
            for category in categories
        },
        "definition": "Macro support-chunk recall/MRR for expected answered cases only; "
        "deduplicate IDs; blocked evidence is not usable gold; contrasts/context excluded",
    }
    answers = {
        "evaluator_version": EVALUATOR_VERSION,
        "overall": answer_aggregate(rows),
        "by_category": {
            category: answer_aggregate([r for r in rows if r["category"] == category])
            for category in categories
        },
        "per_case": rows,
        "review_path": review_path.as_posix() if review_path else None,
        "review_sha256": canonical_hash([r.model_dump() for r in reviews.values()]),
        "fact_proxy_note": "Located gold-span coverage is diagnostic only; not semantic "
        "correctness. Manual covered fact IDs assess actors, conditions and exceptions.",
    }
    operations = operation_aggregate(predictions)
    write_json(directory / "retrieval_metrics.json", retrieval)
    write_json(directory / "answer_metrics.json", answers)
    write_json(directory / "operational_metrics.json", operations)
    if reviews:
        write_json(directory / "answer_reviews.json", [r.model_dump() for r in reviews.values()])
    report = [
        "# RegulaRAG evaluation",
        "",
        "Evaluator: " + EVALUATOR_VERSION,
        f"Questions: {len(rows)}; reviewed: {answers['overall']['reviewed']}",
        "",
        "## Retrieval",
        "```json",
        json.dumps(retrieval["overall"], indent=2),
        "```",
        "",
        "## Answer quality",
        "```json",
        json.dumps(answers["overall"], indent=2),
        "```",
        "",
        "## Operations",
        "```json",
        json.dumps(operations, indent=2),
        "```",
        "",
        "## Failures / pending review",
        *[
            f"- {r['question_id']}: {r['actual_status']} / {r['failure_reason']}; "
            f"correct={r['correct']}; status_match={r['status_match']}"
            for r in rows
            if r["correct"] is not True
        ],
        "",
        "## Category metrics",
        "See retrieval_metrics.json and answer_metrics.json.",
        "Manual pending metrics are null, not invented zeros or perfect accuracy.",
        "Quote binding/faithfulness, factual completeness and relevance are distinct axes.",
        "No held-out inference occurs in a development run. Raw quotes/traces remain local.",
    ]
    (directory / "summary.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    export_review_packet(directory, cases, predictions, evidence)
    return {
        "questions": len(rows),
        "reviewed": answers["overall"]["reviewed"],
        "retrieval": retrieval["overall"],
        "answer": answers["overall"],
    }


def run_evaluation(settings, config, dataset_directory, output, split="development", limit=None):
    if output.exists():
        raise ValueError("Run directory exists; choose a new run ID, never overwrite predictions")
    output.mkdir(parents=True)
    try:
        all_cases, evidence, chunks, lock = verify_live_dataset(dataset_directory, settings, config)
        cases = [c for c in all_cases if c.split == split]
        if split not in ("development", "test") or not cases or (limit is not None and limit < 1):
            raise ValueError("Invalid split/limit")
        cases = cases[:limit] if limit else cases
        if config.generation.response_policy != "verified_passages":
            raise ValueError("Evaluatorv1 uses verified passage claim units")
        metadata = runtime_metadata(config, lock, split, cases)
        write_json(output / "config.json", metadata)
        service = build_answer_service(settings, config)
        retriever = RecordingRetriever(service.retriever)
        generator = RecordingGenerator(service.generator)
        service.retriever, service.generator = retriever, generator
        app = create_app(settings)
        app.state.answer_service = service
        predictions = []
        with (
            TestClient(app, raise_server_exceptions=False) as client,
            (output / "predictions.jsonl").open("x", encoding="utf-8") as file,
        ):
            for case in cases:
                retriever.reset()
                generator.reset()
                request = {
                    "question": case.question,
                    "filters": case.filters.model_dump(mode="json"),
                    "scope": case.scope.model_dump(mode="json"),
                }
                started = perf_counter()
                response = client.post("/api/v1/ask", json=request)
                elapsed = (perf_counter() - started) * 1000
                try:
                    payload = response.json()
                except ValueError:
                    payload = {"status": "error", "failure_reason": response.text}
                generated = generator.output
                prediction = {
                    "question_id": case.question_id,
                    "split": split,
                    "request": request,
                    "http_status": response.status_code,
                    "response": payload,
                    "retrieved": retriever.hits,
                    "generation": asdict(generated) if generated else None,
                    "timing": {
                        **retriever.timings,
                        "llm_ms": round(generator.elapsed_ms, 3),
                        "generation_stage_ms": payload.get("generation_ms", 0.0),
                        "end_to_end_ms": round(elapsed, 3),
                    },
                    "usage": {
                        "input_tokens": generated.usage_input_tokens
                        if generated
                        else None
                        if generator.called
                        else 0,
                        "output_tokens": generated.usage_output_tokens
                        if generated
                        else None
                        if generator.called
                        else 0,
                        "generation_called": generator.called,
                    },
                }
                predictions.append(prediction)
                file.write(json.dumps(prediction, ensure_ascii=False) + "\n")
                file.flush()
                print(
                    json.dumps(
                        {
                            "question_id": case.question_id,
                            "status": payload.get("status", "error"),
                            "end_to_end_ms": round(elapsed, 3),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
        verify_live_dataset(dataset_directory, settings, config)
        result = write_reports(output, cases, predictions, evidence, chunks)
        metadata.update(
            {
                "state": "completed",
                "finished_at": datetime.now(UTC).isoformat(),
                "postflight_integrity": True,
                "completed_requests": len(predictions),
                "predictions_sha256": canonical_hash(predictions),
            }
        )
        write_json(output / "config.json", metadata)
        return result
    except Exception as error:
        write_json(
            output / "failure.json",
            {
                "failed_at": datetime.now(UTC).isoformat(),
                "type": type(error).__name__,
                "reason": str(error),
            },
        )
        raise


def rescore(settings, config, dataset_directory, output, review_path=None, decisions_path=None):
    metadata = json.loads((output / "config.json").read_text(encoding="utf-8"))
    if (
        metadata["state"] != "completed"
        or canonical_hash(config.model_dump(mode="json")) != metadata["config_sha256"]
    ):
        raise ValueError("Run incomplete or config changed; use recorded config, not new tuning")
    all_cases, evidence, chunks, lock = verify_live_dataset(dataset_directory, settings, config)
    if lock["dataset_sha256"] != metadata["dataset_sha256"]:
        raise ValueError("Cannot re-score against changed gold")
    lookup = {c.question_id: c for c in all_cases if c.split == metadata["split"]}
    cases = [lookup[qid] for qid in metadata["question_ids"]]
    predictions = [
        json.loads(line)
        for line in (output / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if canonical_hash(predictions) != metadata["predictions_sha256"]:
        raise ValueError("Recorded predictions drifted; never silently rebind review")
    if decisions_path:
        decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
        if decisions["predictions_sha256"] != metadata["predictions_sha256"]:
            raise ValueError("Manual decisions refer to different predictions")
        lookup = {p["question_id"]: p for p in predictions}
        bound = []
        for qid, values in decisions["reviews"].items():
            if qid not in lookup:
                raise ValueError("Manual decisions contain a question outside this run")
            if "question_id" in values or "response_sha256" in values:
                raise ValueError("Review identities must come from the bound prediction")
            bound.append(
                {
                    "question_id": qid,
                    "response_sha256": canonical_hash(lookup[qid]["response"]),
                    **values,
                }
            )
        review_path = output / "bound_manual_review.json"
        write_json(review_path, bound)
    return write_reports(output, cases, predictions, evidence, chunks, review_path)
