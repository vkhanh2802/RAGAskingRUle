import argparse
import csv
import json
from pathlib import Path

from regularag.evaluation.dataset import canonical_hash
from regularag.evaluation.metrics import AnswerReview


def main():
    parser = argparse.ArgumentParser(
        description="Bind explicit manual CSV judgments to predictions."
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads((args.run_dir / "config.json").read_text(encoding="utf-8"))
    predictions = [
        json.loads(line)
        for line in (args.run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if (
        metadata["state"] != "completed"
        or canonical_hash(predictions) != metadata["predictions_sha256"]
    ):
        raise ValueError("Incomplete or drifted predictions")
    with args.review_csv.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    if (
        len(rows) != len(predictions)
        or [r["question_id"] for r in rows] != metadata["question_ids"]
    ):
        raise ValueError("Manual review must cover the exact ordered run roster")
    reviews = []
    boolean = {"true": True, "false": False}
    for row, prediction in zip(rows, predictions, strict=True):
        reviews.append(
            AnswerReview(
                question_id=row["question_id"],
                response_sha256=canonical_hash(prediction["response"]),
                **{
                    field: row[field].split(";") if row[field] else []
                    for field in (
                        "covered_fact_ids",
                        "faithful_passage_ids",
                        "relevant_passage_ids",
                    )
                },
                forbidden_claims_present=boolean[row["forbidden_claims_present"]],
                behaviour_correct=boolean[row["behaviour_correct"]],
                reviewer="Assistant source-bound manual review; not independent/blind",
                note=row["note"],
            ).model_dump()
        )
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(reviews, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(json.dumps({"reviewed": len(reviews), "review_sha256": canonical_hash(reviews)}))


if __name__ == "__main__":
    main()
