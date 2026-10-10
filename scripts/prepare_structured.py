import argparse
import csv
from dataclasses import asdict
from pathlib import Path

from regularag.ingestion.manifest import load_manifest
from regularag.ingestion.pipeline import BaselineIngestionConfig, process_document
from regularag.ingestion.tokenizer import HuggingFaceTokenizer


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare structural/OCR artifacts before publication."
    )
    parser.add_argument("--document-id", action="append", default=[])
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/documents.csv"))
    parser.add_argument("--config", type=Path, default=Path("configs/ingestion/structured.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/structured"))
    parser.add_argument(
        "--summary", type=Path, default=Path("data/manifests/structured_parse_summary.csv")
    )
    parser.add_argument("--ignore-page-reviews", action="store_true")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    config = BaselineIngestionConfig.from_path(args.config)
    if args.ignore_page_reviews:
        config = config.model_copy(update={"review_manifest": None})
    tokenizer = HuggingFaceTokenizer(config.tokenizer_model, config.tokenizer_revision)
    summaries = []
    for document_id in args.document_id or list(manifest):
        print(f"Preparing {document_id}", flush=True)
        stats = process_document(
            manifest[document_id], Path.cwd(), args.output_dir, config, tokenizer
        )
        summaries.append(asdict(stats))
        print(
            f"{document_id}: pages={stats.pdf_pages}, published_chunks={stats.chunks}", flush=True
        )
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    with args.summary.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)


if __name__ == "__main__":
    main()
