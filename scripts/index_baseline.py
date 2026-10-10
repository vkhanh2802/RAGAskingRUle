import argparse
import json
from dataclasses import asdict
from pathlib import Path

from regularag.core.config import get_settings
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.embedding import SentenceTransformerEmbedder
from regularag.retrieval.indexer import index_baseline


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed and index approved baseline chunks.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/documents.csv"),
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path("data/processed/m2-publication"),
    )
    args = parser.parse_args()

    settings = get_settings()
    config = RagBaselineConfig.from_path(settings.rag_config_path)
    embedder = SentenceTransformerEmbedder(config.embedding)
    result = index_baseline(settings, config, embedder, args.manifest, args.processed_dir)
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
