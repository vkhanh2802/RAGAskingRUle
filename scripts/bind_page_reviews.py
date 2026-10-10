"""Bind explicit visual-review decisions and optional post-edits to prepared pages."""

import argparse
import csv
import json
from pathlib import Path

from regularag.ingestion.cleaner import clean_text_block
from regularag.ingestion.manifest import load_manifest
from regularag.ingestion.page_quality import text_hash


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed/structured-final"))
    parser.add_argument("--postedit-dir", type=Path, default=Path("data/processed/m2-reviewed"))
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/documents.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/manifests/page_reviews.csv"))
    parser.add_argument(
        "--corrections-root", type=Path, default=Path("data/processed/ocr-corrections")
    )
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    with args.decisions.open(encoding="utf-8", newline="") as file:
        decisions = list(csv.DictReader(file))
    records = {}
    if args.output.is_file():
        with args.output.open(encoding="utf-8", newline="") as file:
            records = {
                (row["document_id"], int(row["pdf_page"])): row for row in csv.DictReader(file)
            }
    pages_by_document = {}
    updates = []
    seen = set()
    for decision in decisions:
        document_id = decision["document_id"]
        number = int(decision["pdf_page"])
        if (document_id, number) in seen:
            raise ValueError("Duplicate review decisions")
        seen.add((document_id, number))
        source = manifest[document_id]
        if document_id not in pages_by_document:
            directory = args.input_dir / document_id
            metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
            if metadata["document"]["sha256"] != source["sha256"]:
                raise ValueError("Prepared source differs from review source")
            pages_by_document[document_id] = {
                page["pdf_page_number"]: page
                for page in (
                    json.loads(line)
                    for line in (directory / "pages.jsonl").read_text(encoding="utf-8").splitlines()
                )
            }
        page = pages_by_document[document_id][number]
        if decision["source_sha256"] != source["sha256"] or decision[
            "expected_cleaned_text_sha256"
        ] != text_hash(page["cleaned_text"]):
            raise ValueError("Review decision does not match the inspected source/text snapshot")
        if decision["decision"] not in ("approved", "excluded") or not decision["review_note"]:
            raise ValueError("Review requires an explicit decision and note")
        reviewed = args.postedit_dir / document_id / f"page-{number:03d}.txt"
        cleaned = page["cleaned_text"]
        correction = None
        if reviewed.is_file():
            if page["extraction_method"] != "tesseract_ocr":
                raise ValueError("Post-edit input is limited to OCR pages")
            text = reviewed.read_text(encoding="utf-8").strip()
            if not text:
                raise ValueError("Post-edit cannot be empty")
            cleaned = "\n\n".join(
                clean_text_block(block) for block in text.split("\n\n") if block.strip()
            )
            raw = page["ocr_provenance"]["raw_ocr_text"]
            correction = {
                "document_id": document_id,
                "source_sha256": source["sha256"],
                "pdf_page": number,
                "expected_ocr_text_sha256": text_hash(raw),
                "reviewed_text": text,
                "review_method": "assistant_visual_comparison_150dpi_postedit",
                "note": decision["review_note"],
                "omitted_layout": decision.get("omitted_layout") == "true",
            }
        row = {
            "document_id": document_id,
            "pdf_page": number,
            "source_sha256": source["sha256"],
            "cleaned_text_sha256": text_hash(cleaned),
            "decision": decision["decision"],
            "layout_checked": decision["layout_checked"],
            "review_method": "assistant_visual_comparison_150dpi"
            + ("_postedit" if correction else ""),
            "review_note": decision["review_note"],
        }
        updates.append((row, correction))
    # Validate the entire decision batch before changing the shared review manifest.
    for row, correction in updates:
        if correction:
            path = args.corrections_root / row["document_id"] / f"page-{row['pdf_page']:03d}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(correction, ensure_ascii=False, indent=2), encoding="utf-8")
        records[(row["document_id"], int(row["pdf_page"]))] = row
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(updates[0][0]))
        writer.writeheader()
        writer.writerows(records[key] for key in sorted(records))
    print(
        f"Bound {len(updates)} explicit page reviews; {sum(bool(c) for _, c in updates)} post-edits"
    )


if __name__ == "__main__":
    main()
