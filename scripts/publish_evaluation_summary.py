import argparse
import json
from pathlib import Path

from regularag.evaluation.dataset import canonical_hash


def main():
    parser = argparse.ArgumentParser(description="Publish aggregate/ID-only evaluation evidence.")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    directory = args.run_dir
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    answers = json.loads((directory / "answer_metrics.json").read_text(encoding="utf-8"))
    predictions = [
        json.loads(line)
        for line in (directory / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if (
        config["state"] != "completed"
        or not config["postflight_integrity"]
        or canonical_hash(predictions) != config["predictions_sha256"]
        or answers["overall"]["reviewed"] != len(predictions)
    ):
        raise ValueError("Publish only complete, unchanged, manually reviewed runs")
    payload = {
        "run_id": directory.name,
        **{
            key: config[key]
            for key in (
                "evaluator_version",
                "split",
                "question_ids",
                "dataset_sha256",
                "corpus_sha256",
                "config_sha256",
                "config",
                "git_commit",
                "runtime_source_sha256",
                "predictions_sha256",
                "hardware",
                "concurrency",
                "warm_cold",
                "started_at",
                "finished_at",
                "postflight_integrity",
                "held_out_inference_requests",
            )
        },
        "runtime_worktree_dirty": bool(config["git_status"]),
        **(
            {key: config[key] for key in ("release_freeze", "held_out_ledger")}
            if config["split"] == "test"
            else {}
        ),
        "review_sha256": answers["review_sha256"],
        "retrieval": json.loads((directory / "retrieval_metrics.json").read_text(encoding="utf-8")),
        "answers": {key: answers[key] for key in ("overall", "by_category", "per_case")},
        "operations": json.loads(
            (directory / "operational_metrics.json").read_text(encoding="utf-8")
        ),
        "conditions": "Assistant manual required-fact/atomic-quote-block review, not independent "
        "human review. "
        + (
            "Development results do not estimate held-out accuracy. "
            if config["split"] == "development"
            else "One complete held-out run after code/config release freeze; no test tuning. "
        )
        + "Full answers, source text and model traces are Git ignored.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "questions": len(predictions),
                "reviewed": answers["overall"]["reviewed"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
