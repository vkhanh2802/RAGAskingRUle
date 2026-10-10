"""Export local text bundles and a hash-bound decision template for visual review."""

import argparse
import csv
import json
from pathlib import Path
from textwrap import fill

from regularag.ingestion.page_quality import text_hash


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed/structured-final"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/m2-review-bundles"))
    parser.add_argument("--document-id", action="append", required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for document_id in args.document_id:
        directory = args.input_dir / document_id
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        pages = [
            json.loads(line)
            for line in (directory / "pages.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        lines = []
        for page in pages:
            number = page["pdf_page_number"]
            lines.extend([f"## PDF {number}", f"Flags: {page['quality_flags']}", ""])
            lines.extend(fill(line, width=100) for line in page["cleaned_text"].splitlines())
            lines.extend(["", "---", ""])
            records.append(
                {
                    "document_id": document_id,
                    "pdf_page": number,
                    "source_sha256": metadata["document"]["sha256"],
                    "expected_cleaned_text_sha256": text_hash(page["cleaned_text"]),
                    "decision": "pending",
                    "layout_checked": "false",
                    "review_note": "",
                }
            )
        (args.output_dir / f"{document_id}.md").write_text("\n".join(lines), encoding="utf-8")
    with (args.output_dir / "decisions.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(f"Exported {len(records)} page texts; template decisions remain pending")


if __name__ == "__main__":
    main()
