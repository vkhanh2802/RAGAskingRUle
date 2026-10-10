from pathlib import Path

import pymupdf

from regularag.ingestion.parser import parse_pdf


def _create_test_pdf(path: Path) -> None:
    document = pymupdf.open()
    first_page = document.new_page()
    first_page.insert_text((72, 72), "Trang 7/10\nArticle 1. First page evidence.")
    second_page = document.new_page()
    second_page.insert_text((72, 72), "8\nArticle 2. Second page evidence.")
    document.save(path)
    document.close()


def test_parse_pdf_preserves_raw_text_and_distinguishes_page_numbers(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _create_test_pdf(pdf_path)

    pages = parse_pdf("doc_test", pdf_path)

    assert len(pages) == 2
    assert pages[0].pdf_page_number == 1
    assert pages[0].printed_page_number == 7
    assert pages[0].printed_page_source == "explicit_label"
    assert pages[1].pdf_page_number == 2
    assert pages[1].printed_page_number == 8
    assert pages[1].printed_page_source == "margin_number"
    assert "First page evidence" in pages[0].raw_text
    assert "First page evidence" in pages[0].cleaned_text
    assert pages[0].extraction_method == "pymupdf_text"
