import argparse
import json
from hashlib import sha256
from pathlib import Path

from regularag.ingestion.artifacts import load_processed
from regularag.ingestion.manifest import load_manifest
from regularag.retrieval.config import RagBaselineConfig


def main():
    parser = argparse.ArgumentParser(
        description="Verify supplied PDFs and approved publication inputs before indexing."
    )
    parser.add_argument("--config", type=Path, default=Path("configs/rag/final.json"))
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/documents.csv"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/m2-publication"))
    args = parser.parse_args()
    config = RagBaselineConfig.from_path(args.config)
    manifest = load_manifest(args.manifest)
    rows = []
    for did in config.retrieval.eligible_document_ids:
        document = manifest[did]
        if sha256(Path(document["local_path"]).read_bytes()).hexdigest() != document["sha256"]:
            raise ValueError("Source PDF byte/hash drift: " + did)
        prepared = load_processed(document, args.processed_dir / did)
        rows.append(
            {
                "document_id": did,
                "chunks": len(prepared.chunks),
                "source_sha256": document["sha256"],
                "publication_ready": True,
                "coverage_status": prepared.quality["coverage_status"],
            }
        )
    print(
        json.dumps(
            {
                "valid": True,
                "documents": len(rows),
                "chunks": sum(r["chunks"] for r in rows),
                "rows": rows,
                "conditions": "Read-only approved inputs; no model calls or indexing.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
