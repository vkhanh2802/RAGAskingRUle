import csv
import json
from hashlib import sha256
from pathlib import Path

import pymupdf

from regularag.ingestion.ocr import OcrConfig, OcrResult
from regularag.ingestion.page_quality import text_hash
from regularag.ingestion.pipeline import BaselineIngestionConfig, process_document
from regularag.ingestion.structured_parser import parse_structured_pdf


class FakeOcr:
    def __init__(self) -> None:
        self.pages = []

    def recognize(self, page, output_directory):
        self.pages.append(page.number + 1)
        return OcrResult(
            "OCR evidence with a threshold of 12 credits and an exception. " * 4,
            95,
            0,
            40,
            {"engine": "test_ocr", "engine_version": "test"},
        )


def _document(path: Path) -> dict[str, str]:
    return {"document_id": "doc", "sha256": sha256(path.read_bytes()).hexdigest()}


def test_ocr_runs_only_for_missing_text_and_high_confidence_does_not_auto_approve(
    tmp_path: Path,
) -> None:
    path = tmp_path / "mixed.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 100), "Native evidence sentence with a condition.\n" * 5)
        pdf.new_page()
        pdf.save(path)
    engine = FakeOcr()

    pages = parse_structured_pdf(
        _document(path), path, tmp_path, 100, OcrConfig(enabled=True), engine=engine
    )

    assert engine.pages == [2]
    assert pages[0].extraction_method == "pymupdf_text" and pages[0].publishable
    assert pages[1].extraction_method == "tesseract_ocr"
    assert pages[1].native_text == ""
    assert pages[1].review_status == "pending" and not pages[1].publishable


def test_geometry_margin_removal_preserves_identical_text_in_the_body(tmp_path: Path) -> None:
    path = tmp_path / "margins.pdf"
    with pymupdf.open() as pdf:
        for _ in range(3):
            page = pdf.new_page()
            page.insert_text((72, 100), "Evidence sentence with a condition.\n" * 5)
            page.insert_text((72, 240), "7")
            page.insert_text((280, 805), "7")
        pdf.save(path)

    pages = parse_structured_pdf(_document(path), path, tmp_path, 100, OcrConfig())

    assert all("7" in page.cleaned_text for page in pages)
    assert all(page.removed_margins == ("7",) for page in pages)


def test_forced_ocr_preserves_the_garbled_native_layer_for_comparison(tmp_path: Path) -> None:
    path = tmp_path / "garbled.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 100), "Garbled native text with incorrect encoding.\n" * 5)
        pdf.save(path)
    engine = FakeOcr()
    config = OcrConfig(enabled=True, force_document_ids=["doc"])

    pages = parse_structured_pdf(_document(path), path, tmp_path, 100, config, engine=engine)

    assert engine.pages == [1]
    assert "Garbled" in pages[0].native_text
    assert "OCR evidence" in pages[0].raw_text


def test_reviewed_body_with_omitted_diagram_never_claims_full_coverage(tmp_path, monkeypatch):
    path = tmp_path / "partial.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page()
        pdf.save(path)
    raw = "Verified text plus interleaved diagram labels. " * 5
    corrected = "Verified text with the complete numerical condition. " * 5
    corrections = tmp_path / "corrections" / "doc"
    corrections.mkdir(parents=True)
    (corrections / "page-001.json").write_text(
        json.dumps(
            {
                "document_id": "doc",
                "source_sha256": _document(path)["sha256"],
                "pdf_page": 1,
                "expected_ocr_text_sha256": text_hash(raw),
                "reviewed_text": corrected.strip(),
                "review_method": "visual_comparison",
                "omitted_layout": True,
            }
        ),
        encoding="utf-8",
    )
    review = tmp_path / "reviews.csv"
    row = {
        "document_id": "doc",
        "pdf_page": "1",
        "source_sha256": _document(path)["sha256"],
        "cleaned_text_sha256": text_hash(corrected.strip()),
        "decision": "approved",
        "layout_checked": "true",
        "review_method": "visual_comparison",
    }
    with review.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    class Engine:
        def recognize(self, page, output_directory):
            return OcrResult(raw, 95, 0, 40, {"engine": "test"})

    monkeypatch.setattr(
        "regularag.ingestion.structured_parser.TesseractOcr", lambda config: Engine()
    )
    config = BaselineIngestionConfig.model_validate(
        {
            "pipeline_version": "test",
            "parser_mode": "structured",
            "tokenizer_model": "test",
            "tokenizer_revision": "a" * 40,
            "chunk_size_tokens": 700,
            "minimum_chunk_tokens": 1,
            "maximum_chunk_tokens": 800,
            "chunk_overlap_tokens": 100,
            "minimum_page_text_chars": 100,
            "ocr": {"enabled": True},
            "review_manifest": review,
            "corrections_root": tmp_path / "corrections",
        }
    )

    class Tokenizer:
        def count(self, text):
            return len(text.split())

    document = {**_document(path), "document_number": "1/QD", "local_path": str(path)}
    process_document(document, tmp_path, tmp_path / "output", config, Tokenizer())
    metadata = json.loads((tmp_path / "output/doc/metadata.json").read_text(encoding="utf-8"))
    assert metadata["quality"]["publication_ready"] is True
    assert metadata["quality"]["coverage_status"] == "partial"
    assert metadata["quality"]["omitted_layout_pdf_pages"] == [1]
