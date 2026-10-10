import re
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pymupdf

from regularag.ingestion.cleaner import clean_text_block
from regularag.ingestion.models import ParsedPage
from regularag.ingestion.ocr import OcrConfig, TesseractOcr
from regularag.ingestion.page_quality import apply_page_reviews, corrected_ocr_text, review_inputs
from regularag.ingestion.parser import _detect_printed_page_number

_PAGE_LABEL = re.compile(r"^(?:(?:trang|page)\s+)?\d{1,4}(?:\s*/\s*\d{1,4})?$", re.I)
_LEGAL_HEADING = re.compile(r"^(?:Điều|Chương)\s+\w+", re.I)


def _layout_pages(status: str) -> tuple[set[int], set[int]]:
    if "_on_pdf_pages_" not in status:
        return set(), set()
    numbers = {int(value) for value in re.findall(r"\d+", status.split("_on_pdf_pages_", 1)[1])}
    return (numbers, set()) if status.startswith("tables") else (set(), numbers)


def _native_margin_blocks(page: pymupdf.Page, blocks: list[tuple]) -> list[tuple[int, int, str]]:
    positioned = {
        block["number"]: block
        for block in page.get_text("dict", sort=True)["blocks"]
        if "lines" in block
    }
    margins = []
    for index, block in enumerate(blocks):
        lines = [
            (line_index, text)
            for line_index, text in enumerate(clean_text_block(block[4]).splitlines())
            if text.strip()
        ]
        geometry = [
            line
            for line in positioned.get(block[5], {}).get("lines", [])
            if "".join(span["text"] for span in line["spans"]).strip()
        ]
        if len(lines) != len(geometry):
            continue
        for (line_index, text), line in zip(lines, geometry, strict=True):
            bbox = line["bbox"]
            if bbox[3] <= page.rect.height * 0.08 or bbox[1] >= page.rect.height * 0.91:
                margins.append((index, line_index, text.strip()))
    return margins


def parse_structured_pdf(
    document: dict[str, str],
    pdf_path: Path,
    output_directory: Path,
    minimum_chars: int,
    ocr_config: OcrConfig,
    remove_margins: bool = True,
    review_manifest: Path | None = None,
    corrections_root: Path | None = None,
    engine=None,
) -> list[ParsedPage]:
    document_id = document["document_id"]
    table_pages, flowchart_pages = _layout_pages(document.get("table_status", ""))
    pages = []
    margins_by_page = []
    with pymupdf.open(pdf_path) as pdf:
        if not pdf.is_pdf:
            raise ValueError("Source is not a PDF")
        for page_index, page in enumerate(pdf):
            native = page.get_text("text", sort=True)
            forced = document_id in ocr_config.force_document_ids
            needs_ocr = len(native.strip()) < minimum_chars or forced
            provenance = None
            flags = []
            if needs_ocr:
                if not ocr_config.enabled:
                    raise ValueError("OCR is required for this page but is disabled")
                if engine is None:
                    engine = TesseractOcr(ocr_config)
                recognized = engine.recognize(page, output_directory / "ocr")
                raw_text, correction = corrected_ocr_text(
                    document_id,
                    document["sha256"],
                    page_index + 1,
                    recognized.text,
                    corrections_root,
                )
                provenance = {
                    **recognized.provenance,
                    "mean_confidence": recognized.mean_confidence,
                    "low_confidence_ratio": recognized.low_confidence_ratio,
                    "word_count": recognized.word_count,
                    "raw_ocr_text": recognized.text,
                    "correction": correction,
                }
                method = "tesseract_ocr"
                flags.append("ocr_requires_review")
                if correction and correction.get("omitted_layout"):
                    flags.append("partial_layout_omitted")
                if (
                    recognized.mean_confidence < ocr_config.minimum_mean_confidence
                    or recognized.low_confidence_ratio > ocr_config.maximum_low_confidence_ratio
                ):
                    flags.append("low_ocr_confidence")
                margins_by_page.append([])
                blocks = tuple(
                    clean_text_block(block) for block in raw_text.split("\n\n") if block.strip()
                )
            else:
                raw_text = native
                method = "pymupdf_text"
                native_blocks = [
                    block for block in page.get_text("blocks", sort=True) if block[6] == 0
                ]
                margins_by_page.append(_native_margin_blocks(page, native_blocks))
                blocks = tuple(clean_text_block(block[4]) for block in native_blocks)
            cleaned = "\n\n".join(blocks)
            if page_index + 1 in table_pages:
                flags.append("table_requires_review")
            if page_index + 1 in flowchart_pages:
                flags.append("flowchart_excluded")
            if len(re.findall(r"[.·…]{4,}", cleaned)) >= 5:
                flags.append("table_of_contents_excluded")
            if len(cleaned) < minimum_chars:
                flags.append("low_text_content")
            excluded = bool(set(flags) & {"flowchart_excluded", "table_of_contents_excluded"})
            review_status = "excluded" if excluded else ("pending" if flags else "native")
            printed_page, printed_source = _detect_printed_page_number(raw_text, len(pdf))
            pages.append(
                ParsedPage(
                    document_id,
                    page_index + 1,
                    page.get_label() or str(page_index + 1),
                    printed_page,
                    printed_source,
                    method,
                    raw_text,
                    cleaned,
                    blocks,
                    native_text=native,
                    ocr_provenance=provenance,
                    quality_flags=tuple(flags),
                    review_status=review_status,
                    publishable=review_status == "native",
                )
            )

    if remove_margins:
        frequencies = Counter(
            text for entries in margins_by_page for text in {text for _, _, text in entries}
        )
        repeated = {
            text
            for text, count in frequencies.items()
            if count >= max(3, len(pages) / 2)
            and len(text) <= 120
            and not _LEGAL_HEADING.match(text)
        }
        cleaned_pages = []
        for page, margin_blocks in zip(pages, margins_by_page, strict=True):
            removable = {
                (index, line_index)
                for index, line_index, text in margin_blocks
                if text in repeated or _PAGE_LABEL.fullmatch(text)
            }
            blocks = []
            removed = []
            for index, block in enumerate(page.blocks):
                kept = []
                for line_index, line in enumerate(block.splitlines()):
                    if (index, line_index) in removable:
                        removed.append(line)
                    else:
                        kept.append(line)
                if "\n".join(kept).strip():
                    blocks.append("\n".join(kept).strip())
            cleaned_pages.append(
                replace(
                    page,
                    blocks=tuple(blocks),
                    cleaned_text="\n\n".join(blocks),
                    removed_margins=tuple(removed),
                )
            )
        pages = cleaned_pages
    return apply_page_reviews(
        pages,
        document["sha256"],
        review_inputs(document_id, review_manifest, corrections_root),
    )
