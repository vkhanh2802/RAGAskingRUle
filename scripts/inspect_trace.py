import argparse
import json
from pathlib import Path
from uuid import UUID

from regularag.core.tracing import TRACE_VERSION


def load_trace(path, identifier):
    identifier = str(UUID(identifier))
    matches = []
    with path.open(encoding="utf-8") as file:
        for line in file:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # Uvicorn startup lines may share the local stderr log.
            if not isinstance(record, dict) or not isinstance(record.get("trace"), dict):
                continue
            trace = record["trace"]
            if (
                record.get("logger") == "regularag.trace"
                and trace.get("request_id") == identifier
                and trace.get("trace_version") == TRACE_VERSION
            ):
                matches.append(trace)
    if len(matches) != 1:
        raise ValueError("Expected exactly one complete request trace; found " + str(len(matches)))
    return matches[0]


def summarize(trace):
    parents = {s["parent_span_id"] for s in trace["spans"]}
    leaves = [s for s in trace["spans"] if s["span_id"] not in parents and s["status"] != "skipped"]
    bottleneck = max(leaves, key=lambda s: s["duration_ms"]) if leaves else None
    timeline = []
    for span in trace["spans"]:
        attrs = span["attributes"]
        row = {
            key: span[key]
            for key in (
                "name",
                "span_id",
                "parent_span_id",
                "start_ms",
                "duration_ms",
                "status",
                "error_type",
            )
        }
        for key in (
            "input_chunks",
            "output_chunks",
            "first_stage_chunks",
            "returned_chunks",
            "eligible_chunks",
            "context_chunks",
        ):
            if key in attrs:
                row[key] = [
                    {
                        field: hit.get(field)
                        for field in (
                            "chunk_id",
                            "order",
                            "first_stage_rank",
                            "rerank_rank",
                            "freshness_failure",
                        )
                    }
                    for hit in attrs[key]
                ]
                row[key + "_omitted"] = attrs[key + "_omitted"]
        row.update(
            {
                key: attrs[key]
                for key in (
                    "passages",
                    "required_support",
                    "selected_passage_ids",
                    "resolved_passage_ids",
                    "budget_input_tokens",
                    "budget_limit",
                    "failure_reason",
                    "reason",
                    "http_status",
                    "required_fields",
                    "attempts",
                )
                if key in attrs
            }
        )
        timeline.append(row)
    return {
        "request_id": trace["request_id"],
        "trace_version": trace["trace_version"],
        "duration_ms": trace["duration_ms"],
        "metadata": trace["metadata"],
        "result": trace["result"],
        "usage": trace["usage"],
        "api_cost": trace["api_cost"],
        "hosting_compute_cost": trace["hosting_compute_cost"],
        "largest_observed_leaf_stage": {
            "name": bottleneck["name"],
            "duration_ms": bottleneck["duration_ms"],
        }
        if bottleneck
        else None,
        "omitted_spans": trace["omitted_spans"],
        "timeline": timeline,
        "conditions": "Metadata-only diagnosis; parents include children, not additive. "
        "Trace identifies execution/selection, not semantic correctness or confidence.",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Inspect a single API request trace by its returned ID."
    )
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summarize(load_trace(args.log, args.request_id))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as file:
            file.write(rendered)
    else:
        print(rendered)


if __name__ == "__main__":
    main()
