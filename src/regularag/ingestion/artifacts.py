import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def fingerprint(payload: object) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(serialized.encode("utf-8")).hexdigest()


class ChunkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    document_id: str
    chunk_id: str
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    token_count: int = Field(gt=0)
    pdf_page_start: int = Field(gt=0)
    pdf_page_end: int = Field(gt=0)
    printed_page_start: int | None
    printed_page_end: int | None
    source_pdf_pages: list[int] = Field(min_length=1)
    source_printed_pages: list[int]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chapter: str | None = None
    article: str | None = None
    clauses: list[str] = Field(default_factory=list)
    heading: str = ""
    part_index: int = Field(default=0, ge=0)
    extraction_methods: list[str] = Field(default_factory=lambda: ["pymupdf_text"])
    quality_flags: list[str] = Field(default_factory=list)
    source_spans: list[dict] = Field(default_factory=list)
    quality_status: Literal["approved", "review_required"] = "approved"

    @model_validator(mode="after")
    def validate_provenance(self) -> "ChunkRecord":
        if self.source_pdf_pages != sorted(set(self.source_pdf_pages)):
            raise ValueError("source PDF pages must be unique and ordered")
        if self.pdf_page_start != min(self.source_pdf_pages):
            raise ValueError("invalid chunk start page")
        if self.pdf_page_end != max(self.source_pdf_pages):
            raise ValueError("invalid chunk end page")
        if any(page <= 0 for page in self.source_pdf_pages):
            raise ValueError("source PDF pages must be positive")
        if sha256(self.text.encode("utf-8")).hexdigest() != self.content_sha256:
            raise ValueError(f"Processed chunk hash mismatch: {self.chunk_id}")
        if self.source_printed_pages:
            if (
                any(page <= 0 for page in self.source_printed_pages)
                or self.printed_page_start != self.source_printed_pages[0]
                or self.printed_page_end != self.source_printed_pages[-1]
            ):
                raise ValueError("invalid printed page provenance")
        elif self.printed_page_start is not None or self.printed_page_end is not None:
            raise ValueError("printed page bounds require detected source printed pages")
        return self


@dataclass(frozen=True, slots=True)
class PreparedDocument:
    chunks: list[dict]
    chunking_config: dict
    artifact_path: Path
    quality: dict


class QualityReviewRequired(ValueError):
    """Processed output exists but cannot be published before page/layout review."""


def load_processed(document: dict[str, str], directory: Path) -> PreparedDocument:
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    document_id = document["document_id"]
    if metadata["document"]["document_id"] != document_id:
        raise ValueError(f"Processed document identity mismatch: {document_id}")
    if metadata["document"]["sha256"] != document["sha256"]:
        raise ValueError(f"Processed source hash does not match manifest: {document_id}")
    config = metadata["config"]
    quality = metadata.get(
        "quality", {"publication_ready": True, "coverage_status": "full", "excluded_pdf_pages": []}
    )
    if not quality["publication_ready"]:
        raise QualityReviewRequired(f"Unreviewed page/layout content remains in {document_id}")
    if not config.get("pipeline_version"):
        raise ValueError("processed metadata is missing its chunking pipeline version")

    chunks = []
    for index, line in enumerate(
        (directory / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    ):
        chunk = ChunkRecord.model_validate_json(line)
        if chunk.quality_status != "approved":
            raise QualityReviewRequired("Review-required chunks cannot enter the active index")
        if (
            chunk.document_id != document_id
            or chunk.chunk_index != index
            or chunk.chunk_id != f"{document_id}:chunk:{index:04d}"
        ):
            raise ValueError(f"Invalid chunk identity: {document_id}, index {index}")
        chunks.append(chunk.model_dump())
    if not chunks:
        raise ValueError(f"No chunks found for document: {document_id}")
    if document.get("pdf_type") == "scan" and any(
        "tesseract_ocr" not in chunk["extraction_methods"]
        or not chunk["source_spans"]
        or any(span.get("review_status") != "approved" for span in chunk["source_spans"])
        for chunk in chunks
    ):
        raise QualityReviewRequired("Scanned source requires approved OCR page provenance")
    return PreparedDocument(chunks, config, directory.resolve(), quality)
