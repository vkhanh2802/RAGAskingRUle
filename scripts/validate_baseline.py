import argparse
import json
from hashlib import sha256
from pathlib import Path

from regularag.ingestion.pipeline import BaselineIngestionConfig
from regularag.ingestion.tokenizer import HuggingFaceTokenizer


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def validate_output(output_root: Path, config_path: Path) -> dict[str, object]:
    config = BaselineIngestionConfig.from_path(config_path)
    tokenizer = HuggingFaceTokenizer(config.tokenizer_model, config.tokenizer_revision)
    document_directories = sorted(path.parent for path in output_root.glob("*/metadata.json"))
    if not document_directories:
        raise ValueError(f"No baseline outputs found under {output_root}")

    total_pages = 0
    total_chunks = 0
    token_counts: list[int] = []

    for document_directory in document_directories:
        pages = _read_jsonl(document_directory / "pages.jsonl")
        chunks = _read_jsonl(document_directory / "chunks.jsonl")
        page_lookup = {page["pdf_page_number"]: page for page in pages}
        known_pdf_pages = set(page_lookup)

        if list(page_lookup) != list(range(1, len(pages) + 1)):
            raise ValueError(f"Non-sequential pages in {document_directory.name}")

        for expected_index, chunk in enumerate(chunks):
            text = str(chunk["text"])
            source_pdf_pages = list(chunk["source_pdf_pages"])
            source_printed_pages = list(chunk["source_printed_pages"])
            actual_token_count = tokenizer.count(text)
            if chunk["chunk_index"] != expected_index:
                raise ValueError(f"Non-sequential chunk index in {document_directory.name}")
            expected_chunk_id = f"{document_directory.name}:chunk:{expected_index:04d}"
            if chunk["chunk_id"] != expected_chunk_id:
                raise ValueError(f"Incorrect chunk ID: {chunk['chunk_id']}")
            if actual_token_count != chunk["token_count"]:
                raise ValueError(f"Token count mismatch in {chunk['chunk_id']}")
            if actual_token_count > config.maximum_chunk_tokens:
                raise ValueError(f"Oversized chunk: {chunk['chunk_id']}")
            if sha256(text.encode("utf-8")).hexdigest() != chunk["content_sha256"]:
                raise ValueError(f"Content hash mismatch in {chunk['chunk_id']}")
            if not set(source_pdf_pages).issubset(known_pdf_pages):
                raise ValueError(f"Unknown source page in {chunk['chunk_id']}")
            if chunk["pdf_page_start"] != min(source_pdf_pages):
                raise ValueError(f"Incorrect start page in {chunk['chunk_id']}")
            if chunk["pdf_page_end"] != max(source_pdf_pages):
                raise ValueError(f"Incorrect end page in {chunk['chunk_id']}")
            expected_printed_pages = list(
                dict.fromkeys(
                    page_lookup[pdf_page]["printed_page_number"]
                    for pdf_page in source_pdf_pages
                    if page_lookup[pdf_page]["printed_page_number"] is not None
                )
            )
            if source_printed_pages != expected_printed_pages:
                raise ValueError(f"Incorrect printed page mapping in {chunk['chunk_id']}")
            token_counts.append(actual_token_count)

        total_pages += len(pages)
        total_chunks += len(chunks)

    return {
        "documents": len(document_directories),
        "pages": total_pages,
        "chunks": total_chunks,
        "minimum_chunk_tokens": min(token_counts),
        "maximum_chunk_tokens": max(token_counts),
        "chunks_below_minimum_tokens": sum(
            count < config.minimum_chunk_tokens for count in token_counts
        ),
        "tokenizer_model": config.tokenizer_model,
        "tokenizer_revision": config.tokenizer_revision,
        "status": "valid",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated baseline artifacts.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/baseline"),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/ingestion/baseline.json"),
    )
    args = parser.parse_args()
    print(json.dumps(validate_output(args.output_dir, args.config), indent=2))


if __name__ == "__main__":
    main()
