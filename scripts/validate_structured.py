import argparse
import csv
import json
from hashlib import sha256
from pathlib import Path

from regularag.ingestion.artifacts import ChunkRecord
from regularag.ingestion.tokenizer import HuggingFaceTokenizer


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate structural chunk tokens, spans and quality gates."
    )
    parser.add_argument(
        "--input-dir", type=Path, default=Path("data/processed/structured-reviewed")
    )
    parser.add_argument(
        "--inventory", type=Path, default=Path("data/manifests/chunk_review_inventory.csv")
    )
    args = parser.parse_args()
    inventory = []
    tokenizer = None
    for metadata_path in sorted(args.input_dir.glob("*/metadata.json")):
        directory = metadata_path.parent
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        config = metadata["config"]
        if tokenizer is None:
            tokenizer = HuggingFaceTokenizer(
                config["tokenizer_model"], config["tokenizer_revision"]
            )
        pages = {
            page["pdf_page_number"]: page
            for line in (directory / "pages.jsonl").read_text(encoding="utf-8").splitlines()
            if (page := json.loads(line))
        }
        for index, line in enumerate(
            (directory / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
        ):
            chunk = ChunkRecord.model_validate_json(line)
            if chunk.chunk_index != index or chunk.token_count != tokenizer.count(chunk.text):
                raise ValueError(f"Token/index mismatch: {chunk.chunk_id}")
            if chunk.token_count > config["maximum_chunk_tokens"]:
                raise ValueError(f"Oversized chunk: {chunk.chunk_id}")
            for span in chunk.source_spans:
                source = pages[span["pdf_page"]]
                if not source["publishable"] or source["review_status"] == "pending":
                    raise ValueError(f"Unreviewed source span: {chunk.chunk_id}")
                if sha256(span["text"].encode("utf-8")).hexdigest() != span["text_sha256"]:
                    raise ValueError(f"Span hash mismatch: {chunk.chunk_id}")
                if " ".join(span["text"].split()) not in " ".join(source["cleaned_text"].split()):
                    raise ValueError(f"Span is not in its source page: {chunk.chunk_id}")
            inventory.append(
                {
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.chunk_id,
                    "chapter": chunk.chapter or "",
                    "article": chunk.article or "",
                    "clauses": ";".join(chunk.clauses),
                    "pdf_pages": ";".join(map(str, chunk.source_pdf_pages)),
                    "tokens": chunk.token_count,
                    "content_sha256": chunk.content_sha256,
                    "extraction_methods": ";".join(chunk.extraction_methods),
                    "quality_status": chunk.quality_status,
                }
            )
    if not inventory:
        raise ValueError("No publishable structural chunks found")
    args.inventory.parent.mkdir(parents=True, exist_ok=True)
    with args.inventory.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(inventory[0]))
        writer.writeheader()
        writer.writerows(inventory)
    print(f"Validated {len(inventory)} chunks; token/hash/page-span checks passed")


if __name__ == "__main__":
    main()
