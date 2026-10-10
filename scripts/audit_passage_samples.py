import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import psycopg
from psycopg.rows import dict_row

from regularag.core.config import get_settings
from regularag.generation.clarification import QuestionScope
from regularag.generation.passages import EvidencePassage, PreparedPassages, resolve_passages
from regularag.retrieval.filters import RetrievalFilters


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit and export recorded passage-selection answers."
    )
    parser.add_argument(
        "--input-dir", type=Path, default=Path("data/processed/t3-2-acceptance-api")
    )
    parser.add_argument(
        "--summary", type=Path, default=Path("data/manifests/t3_2_acceptance_audit.json")
    )
    args = parser.parse_args()
    records = [
        json.loads(line)
        for line in (args.input_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    ids = {s["chunk_id"] for r in records for s in r["response"].get("sources", [])}
    with psycopg.connect(str(get_settings().database_url), row_factory=dict_row) as connection:
        stored = {
            r["chunk_id"]: r
            for r in connection.execute(
                "SELECT c.chunk_id,c.document_id,c.text,c.content_sha256,d.source_sha256 "
                "FROM chunks c JOIN documents d ON d.document_id=c.document_id "
                "WHERE c.chunk_id=ANY(%s)",
                (sorted(ids),),
            ).fetchall()
        }
    errors = {
        "span_binding_errors": 0,
        "citation_errors": 0,
        "support_errors": 0,
        "expected_behaviour_errors": 0,
        "filter_preservation_errors": 0,
    }
    failed_cases = []
    review = ["# Recorded answer review", ""]
    for record in records:
        before = errors.copy()
        response = record["response"]
        requested = RetrievalFilters.model_validate(
            json.loads(record["question"].get("filters_json") or "{}")
        )
        applied = RetrievalFilters.model_validate(response.get("applied_filters", {}))
        if any(
            value is not None and value != () and getattr(applied, key) != value
            for key, value in (
                (key, getattr(requested, key)) for key in RetrievalFilters.model_fields
            )
        ):
            errors["filter_preservation_errors"] += 1
        expected_status = record["question"].get("expected_status")
        expected_reason = record["question"].get("expected_reason")
        if expected_status and response.get("status") not in expected_status.split("|"):
            errors["expected_behaviour_errors"] += 1
        if expected_reason and response.get("failure_reason") != expected_reason:
            errors["expected_behaviour_errors"] += 1
        sources = response.get("sources", [])
        chunks = []
        for source in sources:
            row = stored[source["chunk_id"]]
            if row["content_sha256"] != sha256(row["text"].encode()).hexdigest():
                errors["span_binding_errors"] += 1
            chunks.append(
                SimpleNamespace(
                    chunk_id=source["chunk_id"],
                    text=row["text"],
                    content_sha256=row["content_sha256"],
                    evidence_char_ranges=tuple(
                        tuple(pair) for pair in source.get("evidence_char_ranges", [])
                    ),
                )
            )
        passages = tuple(
            EvidencePassage(**{**p, "required_passage_ids": tuple(p["required_passage_ids"])})
            for p in response.get("evidence_passages", [])
        )
        if response.get("status") != "answered" and (
            any(s["cited"] for s in sources) or any(p.cited for p in passages)
        ):
            errors["citation_errors"] += 1
        for passage in passages:
            source = next((s for s in sources if s["source_id"] == passage.source_id), None)
            row = stored.get(passage.chunk_id)
            if (
                source is None
                or source["chunk_id"] != passage.chunk_id
                or row is None
                or not 0 <= passage.char_start < passage.char_end <= len(row["text"])
                or row["text"][passage.char_start : passage.char_end] != passage.text
                or sha256(passage.text.encode()).hexdigest() != passage.text_sha256
            ):
                errors["span_binding_errors"] += 1
        if response.get("status") == "answered":
            prepared = PreparedPassages("", tuple(chunks), passages, response["input_tokens"])
            selected_ids = tuple(p.passage_id for p in passages if p.cited)
            _, reason = resolve_passages(
                record["question"]["question"],
                selected_ids,
                prepared,
                scope=QuestionScope.model_validate(response.get("resolved_scope", {})),
            )
            if reason:
                errors["support_errors"] += 1
            # Identity/citation fidelity and semantic support are separate audit axes.
            selected = sorted((p for p in passages if p.cited), key=lambda p: int(p.passage_id[1:]))
            expected = "\n\n".join(f"“{p.text}” [{p.source_id}]" for p in selected)
            if expected != response["answer"] or {
                s["source_id"] for s in sources if s["cited"]
            } != {p.source_id for p in selected}:
                errors["citation_errors"] += 1
        if problems := [key for key in errors if errors[key] != before[key]]:
            failed_cases.append(
                {"question_id": record["question"]["question_id"], "errors": problems}
            )
        path = args.input_dir / f"{record['question']['question_id']}-response.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        review.extend(
            [
                "## " + record["question"]["question_id"],
                record["question"]["question"],
                "Reference: "
                + record["question"].get("answer", record["question"].get("verification_note", "")),
                "Status: " + response.get("status", "error"),
                response.get("answer", ""),
                "",
            ]
        )
    (args.input_dir / "manual-review.md").write_text("\n\n".join(review), encoding="utf-8")
    result = {
        "audited_at": datetime.now(UTC).isoformat(),
        "requests": len(records),
        "answered": sum(r["response"].get("status") == "answered" for r in records),
        "needs_clarification": sum(
            r["response"].get("status") == "needs_clarification" for r in records
        ),
        "insufficient_evidence": sum(
            r["response"].get("status") == "insufficient_evidence" for r in records
        ),
        "p50_ms": float(np.median([r["summary"]["latency_ms"] for r in records])),
        "p95_ms": float(np.percentile([r["summary"]["latency_ms"] for r in records], 95)),
        **errors,
        "failed_cases": failed_cases,
        "conditions": "Recorded real API against current bound database text; "
        "automatic identity/support-facet audit, manual relevance review still required",
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if any(errors.values()):
        raise ValueError("Recorded passage identity/citation/support audit failed")


if __name__ == "__main__":
    main()
