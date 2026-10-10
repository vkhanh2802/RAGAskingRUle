import argparse
import csv
import json
import re
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from regularag.generation.clarification import folded
from regularag.retrieval.filters import RetrievalFilters


def check_record(record: dict) -> list[str]:
    question = record["question"]
    response = record["response"]
    errors = []
    if record["summary"]["http_status"] != 200:
        return ["http_error"]
    status = response["status"]
    if status not in question["expected_status"].split("|"):
        errors.append("unexpected_status")
    answer = folded(response["answer"])
    if status == "answered":
        for pattern in question.get(
            "required_patterns", json.loads(question.get("required_patterns_json") or "[]")
        ):
            if not re.search(pattern, answer, re.S | re.I):
                errors.append("missing_required_fact:" + pattern)
    for pattern in question.get(
        "forbidden_patterns", json.loads(question.get("forbidden_patterns_json") or "[]")
    ):
        if re.search(pattern, answer, re.S | re.I):
            errors.append("forbidden_answer:" + pattern)
    sources = response.get("sources", [])
    cited_sources = {source["source_id"] for source in sources if source["cited"]}
    passages = [p for p in response.get("evidence_passages", []) if p["cited"]]
    if status == "answered":
        if not passages or cited_sources != {p["source_id"] for p in passages}:
            errors.append("missing_or_mismatched_citations")
        expected = "\n\n".join(f"“{p['text']}” [{p['source_id']}]" for p in passages)
        if expected != response["answer"]:
            errors.append("non_backend_answer_text")
        for passage in passages:
            source = next((s for s in sources if s["source_id"] == passage["source_id"]), None)
            if source is None or source["chunk_id"] != passage["chunk_id"]:
                errors.append("passage_source_mismatch")
            if record.get("retrieved_snapshot"):
                snapshot = {chunk["chunk_id"]: chunk for chunk in record["retrieved_snapshot"]}
                chunk = snapshot.get(passage["chunk_id"])
                if (
                    chunk is None
                    or not 0 <= passage["char_start"] < passage["char_end"] <= len(chunk["text"])
                    or chunk["text"][passage["char_start"] : passage["char_end"]] != passage["text"]
                ):
                    errors.append("synthetic_span_binding_mismatch")
                if chunk is not None and (
                    sha256(chunk["text"].encode()).hexdigest() != chunk["content_sha256"]
                    or source is None
                    or source["excerpt"] != chunk["text"]
                    or any(
                        source[key] != chunk[key]
                        for key in ("document_id", "source_url", "pdf_page_start", "pdf_page_end")
                    )
                ):
                    errors.append("synthetic_provenance_mismatch")
                if sha256(passage["text"].encode()).hexdigest() != passage["text_sha256"]:
                    errors.append("synthetic_span_hash_mismatch")
    elif cited_sources or passages:
        errors.append("citations_on_non_answer")
    requested = RetrievalFilters.model_validate(json.loads(question.get("filters_json") or "{}"))
    applied = RetrievalFilters.model_validate(response.get("applied_filters", {}))
    for key in RetrievalFilters.model_fields:
        value = getattr(requested, key)
        if value is not None and value != () and getattr(applied, key) != value:
            errors.append("filter_override:" + key)
    if (
        "513" in {s["document_number"].split("/", 1)[0] for s in sources}
        and applied.as_of
        and applied.as_of.isoformat() < "2026-05-08"
    ):
        errors.append("future_amendment_in_historical_context")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit declared adversarial behaviour contracts.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--expectations", type=Path)
    args = parser.parse_args()
    records = [
        json.loads(line)
        for line in (args.input_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    rows = []
    expectations = (
        {
            case["question_id"]: case
            for case in json.loads(args.expectations.read_text(encoding="utf-8"))
        }
        if args.expectations
        else {}
    )
    if not records:
        raise ValueError("No behavioural records to audit")
    for record in records:
        if expectations:
            expected = expectations[record["question"]["question_id"]]
            if any(
                record["question"][field] != expected[field]
                for field in ("question", "expected_status")
            ):
                raise ValueError("Expectation query/status drift; do not rebind to pass")
            # A fixture serialization correction may supply canonical pattern arrays;
            # keep recorded model inputs/outputs and declared query/status unchanged.
            record["question"] = {
                **record["question"],
                **{key: expected[key] for key in ("required_patterns", "forbidden_patterns")},
            }
            record["question"].pop("required_patterns_json", None)
            record["question"].pop("forbidden_patterns_json", None)
        errors = check_record(record)
        rows.append(
            {
                "question_id": record["question"]["question_id"],
                "category": record["question"]["category"],
                "answer_status": record["response"].get("status", "error"),
                "pass": not errors,
                "errors": ";".join(errors),
            }
        )
    args.cases.parent.mkdir(parents=True, exist_ok=True)
    with args.cases.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "audited_at": datetime.now(UTC).isoformat(),
        "requests": len(rows),
        "passed": sum(row["pass"] for row in rows),
        "failed": sum(not row["pass"] for row in rows),
        "status_counts": dict(Counter(row["answer_status"] for row in rows)),
        "failed_cases": [row for row in rows if not row["pass"]],
        "conditions": "Predeclared status/fact/citation/filter contracts; "
        "requires complementary source-binding audit and manual semantic review",
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.input_dir / "manual-review.md").write_text(
        "\n\n".join(
            f"## {r['question']['question_id']}\n\n{r['question']['question']}\n\n"
            f"Status: {r['response'].get('status', 'error')}\n\n{r['response'].get('answer', '')}"
            for r in records
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
