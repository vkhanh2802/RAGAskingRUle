import argparse
import json
from dataclasses import asdict
from pathlib import Path

from regularag.ingestion.pipeline import process_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse and chunk text-layer UIT PDFs.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/documents.csv"),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/ingestion/baseline.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/baseline"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/manifests/baseline_parse_summary.csv"),
    )
    args = parser.parse_args()

    workspace_root = Path.cwd()
    stats = process_manifest(
        manifest_path=args.manifest,
        config_path=args.config,
        output_root=args.output_dir,
        summary_path=args.summary,
        workspace_root=workspace_root,
    )
    print(json.dumps([asdict(item) for item in stats], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
