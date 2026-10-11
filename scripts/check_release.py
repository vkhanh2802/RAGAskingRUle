import argparse
import json
from pathlib import Path

from regularag.core.config import Settings
from regularag.evaluation.integrity import verify_live_dataset
from regularag.evaluation.release import verify_release
from regularag.retrieval.config import RagBaselineConfig


def main():
    parser = argparse.ArgumentParser(description="Verify the frozen release read-only; no models.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    args = parser.parse_args()
    config = RagBaselineConfig.from_path(args.config)
    _, _, _, lock = verify_live_dataset(
        Path("data/evaluation/v1"), Settings(rag_config_path=args.config), config
    )
    release = verify_release(args.freeze, config, lock)
    print(
        json.dumps(
            {
                "valid": True,
                "frozen_at": release["frozen_at"],
                "config_sha256": release["config_sha256"],
                "runtime_source_sha256": release["runtime_source_sha256"],
                "held_out_inference_requests": 0,
                "conditions": "Read-only release/source/corpus check; no embedding/ranking/LLM",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
