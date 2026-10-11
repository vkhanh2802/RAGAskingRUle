import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from regularag.core.config import Settings
from regularag.evaluation.runner import rescore, run_evaluation
from regularag.retrieval.config import RagBaselineConfig


def main():
    parser = argparse.ArgumentParser(description="Frozen, source-bound evaluation in one command.")
    parser.add_argument("--config", type=Path, default=Path("configs/rag/baseline.json"))
    parser.add_argument("--dataset", type=Path, default=Path("data/evaluation/v1"))
    parser.add_argument("--split", choices=("development", "test"), default="development")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--question-id", action="append", default=[])
    parser.add_argument("--release-freeze", type=Path)
    parser.add_argument("--retrieval-mode", choices=("vector", "keyword", "hybrid"))
    parser.add_argument("--no-reranker", action="store_true")
    parser.add_argument(
        "--score-only", action="store_true", help="No model calls; apply manual review"
    )
    review_args = parser.add_mutually_exclusive_group()
    review_args.add_argument("--review", type=Path)
    review_args.add_argument("--review-decisions", type=Path)
    args = parser.parse_args()
    if args.score_only and not args.run_dir:
        parser.error("--score-only needs --run-dir")
    if (args.review or args.review_decisions) and not args.score_only:
        parser.error("Review existing predictions with --score-only")
    config = RagBaselineConfig.from_path(args.config)
    if args.retrieval_mode:
        config.retrieval.mode = args.retrieval_mode
    if args.no_reranker:
        config.reranker.enabled = False
    output = args.run_dir or Path("evals/results") / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    settings = Settings(rag_config_path=args.config)
    if args.score_only:
        result = rescore(settings, config, args.dataset, output, args.review, args.review_decisions)
    else:
        result = run_evaluation(
            settings,
            config,
            args.dataset,
            output,
            args.split,
            args.limit,
            set(args.question_id),
            args.release_freeze,
        )
    print(json.dumps({"output": output.as_posix(), **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
