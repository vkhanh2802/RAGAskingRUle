import argparse
import csv
from datetime import UTC, datetime
from pathlib import Path

from regularag.core.config import Settings
from regularag.evaluation.ablation import compare_matrix, load_json
from regularag.evaluation.runner import write_json


def ratio(answer, key):
    value = answer[key]
    return f"{value['numerator']}/{value['denominator']}"


def main():
    parser = argparse.ArgumentParser(
        description="Seal the reviewed development retrieval selection."
    )
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--config-output", type=Path, required=True)
    parser.add_argument("--record-output", type=Path, required=True)
    parser.add_argument("--table-output", type=Path, required=True)
    args = parser.parse_args()
    recorded = load_json(args.comparison)
    labels = [row["label"] for row in recorded["variants"]]
    current = compare_matrix(
        Path(recorded["matrix_root"]), Path("data/evaluation/v1"), Settings(), labels, True
    )
    if current != recorded:
        raise ValueError("Selection requires the actual unchanged reviewed comparison")
    chosen = next(row for row in current["variants"] if row["label"] == current["selected_label"])
    for path in (args.config_output, args.record_output, args.table_output):
        if path.exists():
            raise ValueError("Selection artifact exists; preserve the prior decision")
        path.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.config_output, chosen["config"])
    write_json(
        args.record_output,
        {
            "selected_at": datetime.now(UTC).isoformat(),
            "stage": "T4.3 development retrieval selection; final release freeze after T4.4 fixes",
            "selected_label": chosen["label"],
            "config_path": args.config_output.as_posix(),
            "config_sha256": chosen["config_sha256"],
            "selection_rule": current["selection_rule"],
            "dataset_sha256": current["dataset_sha256"],
            "corpus_sha256": current["corpus_sha256"],
            "runtime_source_sha256": current["runtime_source_sha256"],
            "predictions_sha256": chosen["predictions_sha256"],
            "review_sha256": chosen["review_sha256"],
            "quality": chosen["answer"],
            "operations": chosen["operations"],
            "held_out_inference_requests": 0,
            "conditions": "Top-k4/8/12 have identical reviewed claim bundles and token counts. "
            "Selected by the predeclared measured p95/p50 tie-break; single-pass latency variation "
            "does not establish a causal speedup. No held-out tuning or inference.",
        },
    )
    with args.table_output.open("x", encoding="utf-8", newline="") as file:
        fields = (
            "variant",
            "recall_at_5",
            "recall_at_10",
            "mrr_at_10",
            "correct_answers",
            "required_facts",
            "citation_support",
            "correct_rejection",
            "false_rejection",
            "p50_ms",
            "p95_ms",
            "input_tokens",
            "output_tokens",
            "api_cost_vnd",
        )
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in current["variants"]:
            answer, ops = row["answer"], row["operations"]

            writer.writerow(
                {
                    "variant": row["label"],
                    **{
                        key: row["retrieval"][key]
                        for key in ("recall_at_5", "recall_at_10", "mrr_at_10")
                    },
                    "correct_answers": ratio(answer, "correctness"),
                    "required_facts": ratio(answer, "required_fact_recall"),
                    "citation_support": ratio(answer, "citation_support_precision"),
                    "correct_rejection": ratio(answer, "correct_rejection"),
                    "false_rejection": ratio(answer, "false_rejection"),
                    "p50_ms": ops["stages"]["end_to_end_ms"]["p50"],
                    "p95_ms": ops["stages"]["end_to_end_ms"]["p95"],
                    "input_tokens": ops["tokens"]["input_tokens"]["sum_known"],
                    "output_tokens": ops["tokens"]["output_tokens"]["sum_known"],
                    "api_cost_vnd": ops["api_cost"]["total"],
                }
            )
    print({"selected_label": chosen["label"], "config_sha256": chosen["config_sha256"]})


if __name__ == "__main__":
    main()
