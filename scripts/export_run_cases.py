import argparse
import json
from pathlib import Path

from regularag.evaluation.dataset import canonical_hash
from regularag.evaluation.runner import write_json
from regularag.generation.clarification import QuestionScope
from regularag.generation.passages import scoped_facets


def main():
    parser = argparse.ArgumentParser(
        description="Export bound per-case selection diagnostics locally."
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--question-id", action="append", required=True)
    args = parser.parse_args()
    meta = json.loads((args.run_dir / "config.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (args.run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if canonical_hash(records) != meta["predictions_sha256"]:
        raise ValueError("Recorded selection trace drifted")
    for record in records:
        if record["question_id"] in args.question_id:
            write_json(
                args.run_dir / f"{record['question_id']}-diagnostics.json",
                {
                    "request": record["request"],
                    "generation": record.get("generation"),
                    "response_status": record["response"].get("status"),
                    "failure_reason": record["response"].get("failure_reason"),
                    "scoped_facets_at_diagnosis": scoped_facets(
                        record["request"]["question"],
                        QuestionScope.model_validate(record["response"].get("resolved_scope", {})),
                    ),
                    "source_chunk_ids": [
                        source["chunk_id"] for source in record["response"].get("sources", [])
                    ],
                    "evidence_passages": record["response"].get("evidence_passages", []),
                },
            )
            print(record["question_id"] + " exported")


if __name__ == "__main__":
    main()
