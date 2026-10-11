import argparse
from pathlib import Path

from regularag.core.config import Settings
from regularag.evaluation.release import freeze_release
from regularag.retrieval.config import RagBaselineConfig


def main():
    parser = argparse.ArgumentParser(
        description="One-time reviewed development code/config freeze."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--development-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = RagBaselineConfig.from_path(args.config)
    release = freeze_release(
        Settings(rag_config_path=args.config),
        config,
        Path("data/evaluation/v1"),
        args.development_run,
        args.output,
    )
    print({"frozen_at": release["frozen_at"], "config_sha256": release["config_sha256"]})


if __name__ == "__main__":
    main()
