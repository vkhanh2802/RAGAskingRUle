import csv
import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from regularag.ingestion.models import ParsedPage


def text_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def review_inputs(document_id: str, manifest: Path | None, corrections_root: Path | None) -> dict:
    rows = []
    if manifest and manifest.is_file():
        with manifest.open(encoding="utf-8", newline="") as file:
            rows = [row for row in csv.DictReader(file) if row["document_id"] == document_id]
    corrections = {}
    if corrections_root:
        for path in sorted((corrections_root / document_id).glob("page-*.json")):
            corrections[path.name] = sha256(path.read_bytes()).hexdigest()
    return {"page_reviews": rows, "correction_sha256": corrections}


def corrected_ocr_text(
    document_id: str,
    source_hash: str,
    pdf_page: int,
    ocr_text: str,
    root: Path | None,
) -> tuple[str, dict | None]:
    if root is None:
        return ocr_text, None
    path = root / document_id / f"page-{pdf_page:03d}.json"
    if not path.is_file():
        return ocr_text, None
    correction = json.loads(path.read_text(encoding="utf-8"))
    if (
        correction["document_id"] != document_id
        or correction["source_sha256"] != source_hash
        or correction["pdf_page"] != pdf_page
        or correction["expected_ocr_text_sha256"] != text_hash(ocr_text)
    ):
        raise ValueError("OCR correction is not bound to the current source/page/OCR text")
    text = correction["reviewed_text"]
    if not isinstance(text, str) or not text.strip() or not correction.get("review_method"):
        raise ValueError("OCR correction is missing reviewed text or visual review provenance")
    return text, {
        "review_method": correction["review_method"],
        "correction_file_sha256": sha256(path.read_bytes()).hexdigest(),
        "original_ocr_text_sha256": text_hash(ocr_text),
        "reviewed_text_sha256": text_hash(text),
        "note": correction.get("note", ""),
        "omitted_layout": correction.get("omitted_layout", False),
    }


def apply_page_reviews(pages: list[ParsedPage], source_hash: str, inputs: dict) -> list[ParsedPage]:
    reviews = {int(row["pdf_page"]): row for row in inputs["page_reviews"]}
    if len(reviews) != len(inputs["page_reviews"]):
        raise ValueError("Duplicate page reviews are ambiguous")
    result = []
    for page in pages:
        if page.review_status == "excluded":
            result.append(page)
            continue
        row = reviews.get(page.pdf_page_number)
        if row:
            if row["source_sha256"] != source_hash or row["cleaned_text_sha256"] != text_hash(
                page.cleaned_text
            ):
                raise ValueError(
                    f"Page review hash mismatch: {page.document_id}, page {page.pdf_page_number}"
                )
            if row["decision"] not in ("approved", "excluded"):
                raise ValueError("Page review decision must be approved or excluded")
            if not row.get("review_method"):
                raise ValueError("Page review is missing its recorded review method")
            if (
                "table_requires_review" in page.quality_flags
                and row.get("layout_checked") != "true"
            ):
                raise ValueError("A table page requires a recorded layout comparison")
            result.append(
                replace(
                    page,
                    review_status=row["decision"],
                    publishable=row["decision"] == "approved",
                )
            )
        else:
            result.append(page)
    return result
