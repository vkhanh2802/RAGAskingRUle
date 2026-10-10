import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from regularag.core.config import get_settings
from regularag.evaluation.development import dataset_hash, fetch_evidence, load_questions
from regularag.retrieval.config import RagBaselineConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bind manually reviewed development facts to hashes."
    )
    parser.add_argument(
        "--questions", type=Path, default=Path("data/manifests/development_questions.csv")
    )
    parser.add_argument("--config", type=Path, default=Path("configs/rag/baseline.json"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/manifests/development_evidence.json")
    )
    args = parser.parse_args()
    questions = load_questions(args.questions)
    if len(questions) != 30:
        raise ValueError("T2.4 development set must contain exactly 30 questions")
    config = RagBaselineConfig.from_path(args.config)
    evidence = fetch_evidence(get_settings(), config, questions)
    payload = {
        "version": "development-evidence-v1",
        "bound_at": datetime.now(UTC).isoformat(),
        "dataset_sha256": dataset_hash(questions),
        "question_count": len(questions),
        "review_method": "Technical hash binding of supplied answers/locators; "
        "semantic support review is recorded separately, not performed by this script",
        "chunks": evidence,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Bound {len(questions)} development questions to {len(evidence)} approved chunks")


if __name__ == "__main__":
    main()
