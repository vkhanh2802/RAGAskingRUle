import argparse
import csv
import json
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import psycopg
from evaluate_development import matches_filters
from psycopg.rows import dict_row

from regularag.core.config import get_settings
from regularag.ingestion.manifest import load_manifest
from regularag.retrieval.filters import RetrievalFilters
from regularag.retrieval.freshness import _unmodified_regular_subitem, metadata_json


def verified_unmodified_view(record, source, stored, relation):
    original = SimpleNamespace(
        document_number=source["document_number"],
        article=stored["article"],
        clauses=tuple(stored["clauses"]),
        text=stored["text"],
    )
    view = _unmodified_regular_subitem(original, relation, record["question"]["question"])
    declared = tuple(tuple(pair) for pair in source.get("evidence_char_ranges", []))
    cited = [
        p
        for p in record["response"].get("evidence_passages", [])
        if p["cited"] and p["source_id"] == source["source_id"]
    ]
    return bool(
        view
        and declared == (view,)
        and cited
        and all(view[0] <= p["char_start"] < p["char_end"] <= view[1] for p in cited)
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit recorded real API provenance and citations."
    )
    parser.add_argument(
        "--results", type=Path, default=Path("data/processed/t3-1-api-smoke/results.jsonl")
    )
    parser.add_argument(
        "--manual", type=Path, default=Path("data/manifests/t3_1_api_manual_review.csv")
    )
    parser.add_argument("--output", type=Path, default=Path("data/manifests/t3_1_api_audit.json"))
    args = parser.parse_args()
    records = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines()]
    with args.manual.open(encoding="utf-8", newline="") as file:
        manual = {row["question_id"]: row for row in csv.DictReader(file)}
    documents = load_manifest(Path("data/manifests/documents.csv"))
    numbers = {document["document_number"]: document for document in documents.values()}
    relations = [
        (document, relation)
        for document in documents.values()
        for relation in metadata_json(document, "_document_relations", [])
    ]
    chunk_ids = {
        source["chunk_id"] for record in records for source in record["response"]["sources"]
    }
    with psycopg.connect(str(get_settings().database_url), row_factory=dict_row) as connection:
        chunks = {
            row["chunk_id"]: row
            for row in connection.execute(
                "SELECT chunk_id,document_id,text,content_sha256,article,clauses "
                "FROM chunks WHERE chunk_id=ANY(%s)",
                (sorted(chunk_ids),),
            ).fetchall()
        }
    checks = {
        "provenance_mismatches": 0,
        "excerpt_mismatches": 0,
        "scope_violations": 0,
        "latest_anchor_mismatches": 0,
        "answered_missing_update_context": 0,
        "answered_quote_mismatches": 0,
        "answered_old_affected_clauses": 0,
    }
    for record in records:
        payload = record["response"]
        sources = payload["sources"]
        filters = RetrievalFilters.model_validate(payload["applied_filters"])
        cutoff = filters.as_of or date.today()
        ids = {source["chunk_id"] for source in sources}
        question_id = record["question"]["question_id"]
        if manual[question_id]["answer_status"] != payload["status"]:
            raise ValueError("Manual review does not match the recorded API status")
        for source in sources:
            document = documents[source["document_id"]]
            stored = chunks[source["chunk_id"]]
            if (
                source["document_number"] != document["document_number"]
                or source["source_url"] != document["source_url"]
                or source["issued_date"] != document["issued_date"]
                or source["source_checked_at"] != document.get("source_checked_at")
                or stored["document_id"] != document["document_id"]
                or source["article"] != stored["article"]
                or tuple(source["clauses"]) != tuple(stored["clauses"])
                or sha256(stored["text"].encode()).hexdigest() != stored["content_sha256"]
            ):
                checks["provenance_mismatches"] += 1
            if " ".join(source["excerpt"].split()) not in " ".join(stored["text"].split()):
                checks["excerpt_mismatches"] += 1
            checks["scope_violations"] += not matches_filters(SimpleNamespace(**source), filters)
            family = {document["document_number"]}
            active_updates = []
            changed = True
            while changed:
                changed = False
                for update, relation in relations:
                    number = update["document_number"]
                    if (
                        relation["target_document_number"] in family
                        and number not in family
                        and date.fromisoformat(update["issued_date"]) <= cutoff
                    ):
                        family.add(number)
                        active_updates.append((update, relation))
                        changed = True
            latest = max(
                (numbers[number] for number in family), key=lambda item: item["issued_date"]
            )
            if (
                source["latest_document_number"] != latest["document_number"]
                or source["latest_issued_date"] != latest["issued_date"]
            ):
                checks["latest_anchor_mismatches"] += 1
            if payload["status"] == "answered":
                checks["answered_missing_update_context"] += not set(
                    source["required_update_chunk_ids"]
                ).issubset(ids)
                if source["cited"]:
                    for _, relation in active_updates:
                        if relation["target_document_number"] != source["document_number"]:
                            continue
                        affected = relation["affected_clauses"]
                        clauses = affected.get(source["article"])
                        if (
                            relation["kind"] == "replaces"
                            or source["article"] is None
                            or clauses is not None
                            and (
                                not clauses
                                or not source["clauses"]
                                or set(clauses).intersection(source["clauses"])
                            )
                        ) and not verified_unmodified_view(record, source, stored, relation):
                            checks["answered_old_affected_clauses"] += 1
        if payload["status"] == "answered":
            lookup = {source["source_id"]: source for source in sources}
            for quote in record["generation"]["evidence_quotes"]:
                source = lookup.get(quote["source_id"])
                if source is None or " ".join(quote["quote"].split()) not in " ".join(
                    source["excerpt"].split()
                ):
                    checks["answered_quote_mismatches"] += 1
    latencies = [record["summary"]["latency_ms"] for record in records]
    payload = {
        "audited_at": datetime.now(UTC).isoformat(),
        "requests": len(records),
        "http_200": sum(record["summary"]["http_status"] == 200 for record in records),
        "generation_calls": sum(record["summary"]["generation_called"] for record in records),
        "answered": sum(record["response"]["status"] == "answered" for record in records),
        "manual_supported_answers": sum(
            row["manual_answer_supported"] == "True" for row in manual.values()
        ),
        "expected_stale_filter_abstentions": sum(
            record["response"].get("failure_reason") == "latest_excluded_by_filters"
            and manual[record["question"]["question_id"]]["verdict"] == "pass_abstention"
            for record in records
        ),
        "manual_abstentions": sum(row["verdict"] == "pass_abstention" for row in manual.values()),
        "end_to_end_p50_ms": float(np.median(latencies)),
        "end_to_end_p95_ms": float(np.percentile(latencies, 95)),
        **checks,
        "conditions": "Real ASGI API with local models; assistant manual source review; "
        "mixed cold/warm requests; no held-out answer-accuracy estimate; "
        "latest anchors verified against source-bound corpus metadata at recorded filters",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if any(checks.values()):
        raise ValueError("Recorded API provenance/freshness/citation audit failed")


if __name__ == "__main__":
    main()
