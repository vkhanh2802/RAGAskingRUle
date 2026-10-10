import re
from pathlib import Path

import pymupdf

from regularag.ingestion.cleaner import clean_text_block
from regularag.ingestion.models import ParsedPage, PrintedPageSource

_EXPLICIT_PAGE_PATTERN = re.compile(r"^(?:trang|page)\s+(\d{1,4})(?:\s*/\s*\d{1,4})?$", re.I)
_MARGIN_PAGE_PATTERN = re.compile(r"^(\d{1,4})$")


def _detect_printed_page_number(
    raw_text: str,
    total_pdf_pages: int,
) -> tuple[int | None, PrintedPageSource | None]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    margin_lines = [*lines[:3], *lines[-3:]]

    for line in margin_lines:
        match = _EXPLICIT_PAGE_PATTERN.fullmatch(line)
        if match:
            return int(match.group(1)), "explicit_label"

    for line in margin_lines:
        match = _MARGIN_PAGE_PATTERN.fullmatch(line)
        if match:
            page_number = int(match.group(1))
            if 1 <= page_number <= total_pdf_pages + 20:
                return page_number, "margin_number"

    return None, None


def parse_pdf(document_id: str, pdf_path: Path) -> list[ParsedPage]:
    pages: list[ParsedPage] = []

    with pymupdf.open(pdf_path) as document:
        if not document.is_pdf:
            raise ValueError(f"Not a PDF: {pdf_path}")

        for page_index, page in enumerate(document):
            raw_text = page.get_text("text", sort=True)
            cleaned_blocks = tuple(
                cleaned
                for block in page.get_text("blocks", sort=True)
                if block[6] == 0
                if (cleaned := clean_text_block(block[4]))
            )
            cleaned_text = "\n\n".join(cleaned_blocks)
            printed_page_number, printed_page_source = _detect_printed_page_number(
                raw_text,
                len(document),
            )

            pages.append(
                ParsedPage(
                    document_id=document_id,
                    pdf_page_number=page_index + 1,
                    pdf_page_label=page.get_label() or str(page_index + 1),
                    printed_page_number=printed_page_number,
                    printed_page_source=printed_page_source,
                    extraction_method="pymupdf_text",
                    raw_text=raw_text,
                    cleaned_text=cleaned_text,
                    blocks=cleaned_blocks,
                )
            )

    return pages
