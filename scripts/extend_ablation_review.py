import argparse
from pathlib import Path

from regularag.core.config import Settings
from regularag.evaluation.ablation import (
    VARIANTS,
    groups_signature,
    load_json,
    review_groups,
    validated_jobs,
)
from regularag.evaluation.runner import write_json


def main():
    parser = argparse.ArgumentParser(
        description="Extend reviewed exact semantic groups to top-k runs."
    )
    parser.add_argument("--root", type=Path, default=Path("evals/results/t4-3-ablation"))
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    matrix = load_json(args.root / "matrix.json")
    _, _, _, _, jobs = validated_jobs(
        args.root, Path("data/evaluation/v1"), Settings(), list(matrix["jobs"])
    )
    old_groups = review_groups({label: jobs[label] for label in VARIANTS})
    all_groups = review_groups(jobs)
    prior = load_json(args.prior)
    if prior["groups_sha256"] != groups_signature(old_groups):
        raise ValueError("Prior review is not bound to the core runs")
    if set(all_groups) != set(old_groups) or set(prior["reviews"]) != set(all_groups):
        raise ValueError("New semantic groups need manual review; no automatic fact labels")
    if any(
        all_groups[key]["semantic_sha256"] != old_groups[key]["semantic_sha256"]
        for key in all_groups
    ):
        raise ValueError("Different source/quote/scope semantics cannot inherit a review")
    result = {
        "groups_sha256": groups_signature(all_groups),
        "prior_core_groups_sha256": groups_signature(old_groups),
        "review_method": "Exact source/quote/condition/scope groups already manually reviewed; "
        "all new predictions/source bindings verified; every new response SHA/PID rebound. "
        "No review inheritance for changed semantics or unreviewed groups.",
        "reviews": prior["reviews"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(
        {
            "groups": len(all_groups),
            "predictions": sum(len(j["predictions"]) for j in jobs.values()),
        }
    )


if __name__ == "__main__":
    main()
