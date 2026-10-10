import csv
import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from regularag.ingestion.chunker import chunk_pages
from regularag.ingestion.models import Chunk, ParsedPage
from regularag.ingestion.ocr import OcrConfig
from regularag.ingestion.parser import parse_pdf
from regularag.ingestion.tokenizer import HuggingFaceTokenizer, TextTokenizer


class BaselineIngestionConfig(BaseModel):
    pipeline_version: str
    tokenizer_model: str
    tokenizer_revision: str
    chunk_size_tokens: int = Field(ge=500, le=800)
    minimum_chunk_tokens: int = Field(ge=1, le=800)
    maximum_chunk_tokens: int = Field(ge=500, le=800)
    chunk_overlap_tokens: int = Field(ge=80, le=120)
    minimum_page_text_chars: int = Field(ge=1)
    parser_mode: Literal["baseline", "structured"] = "baseline"
    ocr: OcrConfig = Field(default_factory=OcrConfig)
    review_manifest: Path | None = None
    corrections_root: Path | None = None
    remove_repeated_margins: bool = False

    @model_validator(mode="after")
    def validate_overlap(self) -> "BaselineIngestionConfig":
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError("chunk overlap must be smaller than chunk size")
        if self.minimum_chunk_tokens > self.chunk_size_tokens:
            raise ValueError("minimum chunk size cannot exceed target chunk size")
        if self.maximum_chunk_tokens < self.chunk_size_tokens:
            raise ValueError("maximum chunk size cannot be smaller than target chunk size")
        return self

    @classmethod
    def from_path(cls, path: Path) -> "BaselineIngestionConfig":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class DocumentStats:
    document_id: str
    document_number: str
    pdf_pages: int
    pages_with_text: int
    raw_text_chars: int
    cleaned_text_chars: int
    printed_pages_detected: int
    chunks: int
    minimum_chunk_tokens: int
    maximum_chunk_tokens: int
    average_chunk_tokens: float


def _write_jsonl(path: Path, records: list[ParsedPage] | list[Chunk]) -> None:
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")


def _verify_source(pdf_path: Path, expected_sha256: str) -> None:
    actual_sha256 = sha256(pdf_path.read_bytes()).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError(f"Source hash mismatch: {pdf_path}")


def process_document(
    manifest_row: dict[str, str],
    workspace_root: Path,
    output_root: Path,
    config: BaselineIngestionConfig,
    tokenizer: TextTokenizer,
) -> DocumentStats:
    document_id = manifest_row["document_id"]
    pdf_path = workspace_root / manifest_row["local_path"]
    _verify_source(pdf_path, manifest_row["sha256"])

    document_output = output_root / document_id
    document_output.mkdir(parents=True, exist_ok=True)
    if config.parser_mode == "structured":
        from dataclasses import replace

        from regularag.ingestion.structured_chunker import structured_chunks
        from regularag.ingestion.structured_parser import parse_structured_pdf

        pages = parse_structured_pdf(
            manifest_row,
            pdf_path,
            document_output,
            config.minimum_page_text_chars,
            config.ocr,
            config.remove_repeated_margins,
            config.review_manifest,
            config.corrections_root,
        )
        chunks = structured_chunks(
            document_id,
            pages,
            tokenizer,
            config.chunk_size_tokens,
            config.maximum_chunk_tokens,
            config.chunk_overlap_tokens,
        )
        candidates = structured_chunks(
            document_id,
            [
                replace(page, publishable=True) if page.review_status == "pending" else page
                for page in pages
            ],
            tokenizer,
            config.chunk_size_tokens,
            config.maximum_chunk_tokens,
            config.chunk_overlap_tokens,
        )
        _write_jsonl(document_output / "candidate_chunks.jsonl", candidates)
        for chunk in candidates:
            review_directory = document_output / "review_chunks"
            review_directory.mkdir(parents=True, exist_ok=True)
            (review_directory / f"chunk-{chunk.chunk_index:04d}.md").write_text(
                f"# {chunk.chunk_id}\n\n"
                f"PDF pages: {chunk.source_pdf_pages}; chapter={chunk.chapter}; "
                f"article={chunk.article}; clauses={chunk.clauses}; tokens={chunk.token_count}; "
                f"quality={chunk.quality_status}\n\n" + chunk.text + "\n",
                encoding="utf-8",
            )
        required = [page.pdf_page_number for page in pages if page.review_status == "pending"]
        excluded = [page.pdf_page_number for page in pages if page.review_status == "excluded"]
        omitted_layouts = [
            page.pdf_page_number for page in pages if "partial_layout_omitted" in page.quality_flags
        ]
        quality = {
            "publication_ready": not required and bool(chunks),
            "coverage_status": "unreviewed"
            if required
            else ("partial" if excluded or omitted_layouts else "full"),
            "review_required_pdf_pages": required,
            "excluded_pdf_pages": excluded,
            "omitted_layout_pdf_pages": omitted_layouts,
            "page_text_sha256": {
                str(page.pdf_page_number): sha256(page.cleaned_text.encode("utf-8")).hexdigest()
                for page in pages
            },
        }
    else:
        pages = parse_pdf(document_id, pdf_path)
        chunks = chunk_pages(
            document_id,
            pages,
            tokenizer,
            config.chunk_size_tokens,
            config.chunk_overlap_tokens,
            config.minimum_chunk_tokens,
            config.maximum_chunk_tokens,
        )
        quality = {
            "publication_ready": bool(chunks),
            "coverage_status": "full",
            "excluded_pdf_pages": [],
        }
    if not any(len(page.cleaned_text) >= config.minimum_page_text_chars for page in pages):
        raise ValueError(f"Document has no usable text layer: {document_id}")
    _write_jsonl(document_output / "pages.jsonl", pages)
    _write_jsonl(document_output / "chunks.jsonl", chunks)
    (document_output / "metadata.json").write_text(
        json.dumps(
            {
                "document": manifest_row,
                "config": config.model_dump(mode="json"),
                "quality": quality,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    token_counts = [chunk.token_count for chunk in chunks]
    return DocumentStats(
        document_id=document_id,
        document_number=manifest_row["document_number"],
        pdf_pages=len(pages),
        pages_with_text=sum(bool(page.cleaned_text) for page in pages),
        raw_text_chars=sum(len(page.raw_text) for page in pages),
        cleaned_text_chars=sum(len(page.cleaned_text) for page in pages),
        printed_pages_detected=sum(page.printed_page_number is not None for page in pages),
        chunks=len(chunks),
        minimum_chunk_tokens=min(token_counts, default=0),
        maximum_chunk_tokens=max(token_counts, default=0),
        average_chunk_tokens=round(sum(token_counts) / max(1, len(token_counts)), 2),
    )


def process_manifest(
    manifest_path: Path,
    config_path: Path,
    output_root: Path,
    summary_path: Path,
    workspace_root: Path,
) -> list[DocumentStats]:
    config = BaselineIngestionConfig.from_path(config_path)
    tokenizer = HuggingFaceTokenizer(config.tokenizer_model, config.tokenizer_revision)
    with manifest_path.open(encoding="utf-8", newline="") as manifest_file:
        manifest_rows = [row for row in csv.DictReader(manifest_file) if row["pdf_type"] == "text"]

    stats = [
        process_document(row, workspace_root, output_root, config, tokenizer)
        for row in manifest_rows
    ]
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8", newline="") as summary_file:
        writer = csv.DictWriter(summary_file, fieldnames=list(asdict(stats[0])))
        writer.writeheader()
        writer.writerows(asdict(document_stats) for document_stats in stats)
    return stats
