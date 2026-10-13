"""Explicit pinned cache bootstrap/check. This is never run by image build or API startup."""

import argparse
import json
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download, try_to_load_from_cache

from regularag.ingestion.pipeline import BaselineIngestionConfig
from regularag.retrieval.config import RagBaselineConfig

_MODEL_FILES = ["*.json", "*.txt", "*.model", "model*.safetensors", "pytorch_model*.bin"]


def specifications(config, ingestion):
    return [
        {
            "component": "tokenizer",
            "repo": ingestion.tokenizer_model,
            "revision": ingestion.tokenizer_revision,
            "patterns": [
                "config.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "special_tokens_map.json",
                "sentencepiece.bpe.model",
            ],
            "required": [["tokenizer.json"]],
        },
        *[
            {
                "component": name,
                "repo": getattr(config, name).model_name,
                "revision": getattr(config, name).model_revision,
                "patterns": _MODEL_FILES,
                "required": [
                    ["config.json"],
                    ["tokenizer.json"],
                    ["model.safetensors", "pytorch_model.bin"],
                ],
            }
            for name in ("embedding", "reranker")
        ],
        {
            "component": "generation",
            "repo": config.generation.model_name,
            "revision": config.generation.model_revision,
            "filename": config.generation.gguf_filename,
            "required": [[config.generation.gguf_filename]],
        },
    ]


def main():
    parser = argparse.ArgumentParser(description="Download or check exact pinned model cache.")
    parser.add_argument("--config", type=Path, default=Path("configs/rag/final.json"))
    parser.add_argument(
        "--ingestion-config", type=Path, default=Path("configs/ingestion/baseline.json")
    )
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument(
        "--component", action="append", choices=("tokenizer", "embedding", "reranker", "generation")
    )
    args = parser.parse_args()
    config = RagBaselineConfig.from_path(args.config)
    ingestion = BaselineIngestionConfig.from_path(args.ingestion_config)
    if config.generation.backend != "llama_cpp":
        raise ValueError("This bootstrap matches the measured GGUF/local CPU configuration")
    rows = []
    for spec in specifications(config, ingestion):
        if args.component and spec["component"] not in args.component:
            continue
        if not args.check_only:
            if "filename" in spec:
                hf_hub_download(
                    repo_id=spec["repo"], filename=spec["filename"], revision=spec["revision"]
                )
            else:
                snapshot_download(
                    repo_id=spec["repo"], revision=spec["revision"], allow_patterns=spec["patterns"]
                )
        missing = []
        for alternatives in spec["required"]:
            if not any(
                isinstance(
                    try_to_load_from_cache(spec["repo"], name, revision=spec["revision"]), str
                )
                for name in alternatives
            ):
                missing.append(alternatives)
        row = {
            "component": spec["component"],
            "repo": spec["repo"],
            "revision": spec["revision"],
            "ready": not missing,
            "missing_required_files": missing,
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
    return int(any(not row["ready"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
