from dataclasses import asdict, dataclass
from typing import Literal

PrintedPageSource = Literal["explicit_label", "margin_number"]


@dataclass(frozen=True, slots=True)
class ParsedPage:
    document_id: str
    pdf_page_number: int
    pdf_page_label: str
    printed_page_number: int | None
    printed_page_source: PrintedPageSource | None
    extraction_method: Literal["pymupdf_text", "tesseract_ocr"]
    raw_text: str
    cleaned_text: str
    blocks: tuple[str, ...]
    native_text: str | None = None
    ocr_provenance: dict | None = None
    quality_flags: tuple[str, ...] = ()
    review_status: Literal["native", "pending", "approved", "excluded"] = "native"
    publishable: bool = True
    removed_margins: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Chunk:
    document_id: str
    chunk_id: str
    chunk_index: int
    text: str
    token_count: int
    pdf_page_start: int
    pdf_page_end: int
    printed_page_start: int | None
    printed_page_end: int | None
    source_pdf_pages: tuple[int, ...]
    source_printed_pages: tuple[int, ...]
    content_sha256: str
    chapter: str | None = None
    article: str | None = None
    clauses: tuple[str, ...] = ()
    heading: str = ""
    part_index: int = 0
    extraction_methods: tuple[str, ...] = ("pymupdf_text",)
    quality_flags: tuple[str, ...] = ()
    source_spans: tuple[dict, ...] = ()
    quality_status: Literal["approved", "review_required"] = "approved"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
