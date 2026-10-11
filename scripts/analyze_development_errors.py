import argparse
import csv
import json
from pathlib import Path

from regularag.core.config import Settings
from regularag.evaluation.dataset import canonical_hash
from regularag.evaluation.integrity import verify_live_dataset
from regularag.evaluation.metrics import span_covered
from regularag.evaluation.runner import write_json
from regularag.generation.passages import support_facets
from regularag.retrieval.config import RagBaselineConfig


def main():
    parser = argparse.ArgumentParser(
        description="Locate frozen development failures without inference."
    )
    parser.add_argument("--matrix", type=Path, default=Path("evals/results/t4-3-ablation"))
    parser.add_argument("--cases", type=Path, default=Path("data/manifests/t4_4_error_cases.csv"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = RagBaselineConfig.from_path(Path("configs/rag/t4_3_selected.json"))
    cases, evidence, _, lock = verify_live_dataset(Path("data/evaluation/v1"), Settings(), config)
    cases = {case.question_id: case for case in cases if case.split == "development"}
    with args.cases.open(encoding="utf-8", newline="") as file:
        inventory = list(csv.DictReader(file))
    records = {}
    output = []
    for item in inventory:
        variant = item["variant"]
        if variant not in records:
            path = args.matrix / variant
            meta = json.loads((path / "config.json").read_text(encoding="utf-8"))
            values = [
                json.loads(line)
                for line in (path / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            if canonical_hash(values) != meta["predictions_sha256"]:
                raise ValueError("Baseline predictions drifted")
            records[variant] = ({value["question_id"]: value for value in values}, meta)
        case = cases[item["question_id"]]
        values, meta = records[variant]
        prediction = values[case.question_id]
        response = prediction["response"]
        gold = {evidence[eid].chunk_id for eid in case.support_evidence_ids}
        ranking = [hit["chunk_id"] for hit in prediction["retrieved"]]
        context = {source["chunk_id"] for source in response.get("sources", [])}
        registry = response.get("evidence_passages", [])
        cited = [p for p in registry if p["cited"]]
        output.append(
            {
                **item,
                "expected_status": case.expected_status,
                "actual_status": response.get("status"),
                "failure_reason": response.get("failure_reason"),
                "gold_ranks": {
                    cid: ranking.index(cid) + 1 if cid in ranking else None for cid in gold
                },
                "gold_in_response_context": sorted(gold & context),
                "facts_with_full_span_in_registry": [
                    fact.fact_id
                    for fact in case.required_facts
                    if all(span_covered(evidence[eid], registry) for eid in fact.evidence_ids)
                ],
                "facts_with_full_span_cited": [
                    fact.fact_id
                    for fact in case.required_facts
                    if all(span_covered(evidence[eid], cited) for eid in fact.evidence_ids)
                ],
                "model_selected_pids": (prediction.get("generation") or {}).get("passage_ids", []),
                "final_cited_pids": [p["passage_id"] for p in cited],
                "support_facets_at_analysis": support_facets(case.question),
                "baseline_predictions_sha256": meta["predictions_sha256"],
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        args.output,
        {
            "error_cases": len(output),
            "distinct_development_questions": len({row["question_id"] for row in output}),
            "dataset_sha256": lock["dataset_sha256"],
            "records": output,
            "conditions": "Spancoverage diagnostics, not semanticcorrectness; "
            "no held-out input or model calls; inventory includes precision-only "
            "and variant failures",
        },
    )
    print({"error_cases": len(output), "output": args.output.as_posix()})


if __name__ == "__main__":
    main()
