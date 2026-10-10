"""Materialize explicit, source-reviewed edit plans; never infer approval from confidence."""

import argparse
import csv
import json
from pathlib import Path

from regularag.ingestion.page_quality import text_hash


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed/structured-final"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/m2-reviewed"))
    parser.add_argument("--decisions", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    rows = []
    postedits = []
    for document_id, document in plan.items():
        directory = args.input_dir / document_id
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        if metadata["document"]["sha256"] != document["source_sha256"]:
            raise ValueError("Review plan source hash mismatch")
        pages = {
            p["pdf_page_number"]: p
            for p in (
                json.loads(line)
                for line in (directory / "pages.jsonl").read_text(encoding="utf-8").splitlines()
            )
        }
        for number_text, decision in document["pages"].items():
            number = int(number_text)
            page = pages[number]
            if decision["decision"] not in ("approved", "excluded") or not decision.get("note"):
                raise ValueError("Every page needs an explicit visual-review decision and note")
            text = page["ocr_provenance"]["raw_ocr_text"]
            if decision.get("use_existing_postedit"):
                if not (args.output_dir / document_id / f"page-{number:03d}.txt").is_file():
                    raise ValueError("Explicit complete post-edit is missing")
            elif decision["decision"] == "approved":
                for old, new in document.get("replacements", []):
                    text = text.replace(old, new)
                for old, new in decision.get("edits", []):
                    if old not in text:
                        raise ValueError(f"Reviewed edit is absent: {document_id}/{number}: {old}")
                    text = text.replace(old, new)
                for start, end in decision.get("remove_between", []):
                    if text.count(start) != 1 or text.count(end) != 1:
                        raise ValueError("Ambiguous reviewed layout boundaries")
                    left, right = text.index(start), text.index(end)
                    if right <= left:
                        raise ValueError("Reversed reviewed layout boundaries")
                    text = text[:left] + text[right:]
                if "end_before" in decision:
                    marker = decision["end_before"]
                    if text.count(marker) != 1:
                        raise ValueError("Ambiguous reviewed footer boundary")
                    text = text.split(marker)[0]
                if text != page["ocr_provenance"]["raw_ocr_text"]:
                    postedits.append((document_id, number, text))
            rows.append(
                {
                    "document_id": document_id,
                    "pdf_page": number,
                    "source_sha256": document["source_sha256"],
                    "expected_cleaned_text_sha256": text_hash(page["cleaned_text"]),
                    "decision": decision["decision"],
                    "layout_checked": "true" if decision.get("layout_checked") else "false",
                    "omitted_layout": "true"
                    if decision.get("remove_between") or decision.get("omitted_layout")
                    else "false",
                    "review_note": decision["note"],
                }
            )
    for document_id, number, text in postedits:
        path = args.output_dir / document_id / f"page-{number:03d}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    args.decisions.parent.mkdir(parents=True, exist_ok=True)
    with args.decisions.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Materialized {len(rows)} explicit decisions and {len(postedits)} reviewed edits")


if __name__ == "__main__":
    main()
