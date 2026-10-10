import json
from pathlib import Path

import pytest

from regularag.ingestion.page_quality import apply_page_reviews, corrected_ocr_text, text_hash
from tests.unit.ingestion.test_structured_chunker import _page


def test_page_approval_requires_the_exact_cleaned_text_and_source_hash() -> None:
    page = _page(1, "Evidence text.")
    review = {
        "document_id": "doc",
        "pdf_page": "1",
        "source_sha256": "a" * 64,
        "cleaned_text_sha256": text_hash("Different text."),
        "decision": "approved",
        "review_method": "visual_comparison",
    }

    with pytest.raises(ValueError, match="hash mismatch"):
        apply_page_reviews([page], "a" * 64, {"page_reviews": [review]})


def test_post_edited_ocr_keeps_original_hash_and_rejects_another_ocr_run(tmp_path: Path) -> None:
    directory = tmp_path / "doc"
    directory.mkdir()
    correction = {
        "document_id": "doc",
        "source_sha256": "a" * 64,
        "pdf_page": 1,
        "expected_ocr_text_sha256": text_hash("Trong vòng | tháng."),
        "reviewed_text": "Trong vòng 1 tháng.",
        "review_method": "visual_comparison",
    }
    (directory / "page-001.json").write_text(json.dumps(correction), encoding="utf-8")

    text, provenance = corrected_ocr_text("doc", "a" * 64, 1, "Trong vòng | tháng.", tmp_path)

    assert text == "Trong vòng 1 tháng."
    assert provenance["original_ocr_text_sha256"] == correction["expected_ocr_text_sha256"]
    with pytest.raises(ValueError, match="not bound"):
        corrected_ocr_text("doc", "a" * 64, 1, "Another OCR result.", tmp_path)
