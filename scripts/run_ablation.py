import argparse
import json
import subprocess
import sys
from pathlib import Path

from regularag.core.config import Settings
from regularag.evaluation.ablation import (
    VARIANTS,
    apply_matrix_reviews,
    compare_matrix,
    export_matrix_review,
    load_json,
    run_variant,
)
from regularag.evaluation.runner import write_json
from regularag.retrieval.config import RagBaselineConfig


def main():
    parser = argparse.ArgumentParser(description="Development-only controlled retrieval ablation.")
    parser.add_argument("action", choices=("run", "packet", "review", "compare"))
    parser.add_argument("--root", type=Path, default=Path("evals/results/t4-3-ablation"))
    parser.add_argument("--config", type=Path, default=Path("configs/rag/baseline.json"))
    parser.add_argument("--dataset", type=Path, default=Path("data/evaluation/v1"))
    parser.add_argument("--variant", choices=(*VARIANTS, "all"))
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--include-top-k", action="store_true")
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    base = RagBaselineConfig.from_path(args.config)
    settings = Settings(rag_config_path=args.config)
    if args.action == "run":
        if not args.variant:
            parser.error("run requires --variant")
        if args.variant == "all":
            for variant in VARIANTS:
                command = [
                    sys.executable,
                    __file__,
                    "run",
                    "--variant",
                    variant,
                    "--root",
                    str(args.root),
                    "--config",
                    str(args.config),
                    "--dataset",
                    str(args.dataset),
                ]
                if args.top_k is not None:
                    command.extend(["--top-k", str(args.top_k)])
                subprocess.run(command, check=True)
            return
        result = run_variant(args.root, args.dataset, settings, base, args.variant, args.top_k)
    else:
        matrix = load_json(args.root / "matrix.json")
        labels = list(matrix["jobs"]) if args.include_top_k else list(VARIANTS)
        if args.action == "packet":
            result = export_matrix_review(args.root, args.dataset, settings, labels)
        elif args.action == "review":
            if not args.decisions:
                parser.error("review requires --decisions")
            result = apply_matrix_reviews(args.root, args.dataset, settings, labels, args.decisions)
        else:
            result = compare_matrix(args.root, args.dataset, settings, labels, args.include_top_k)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
