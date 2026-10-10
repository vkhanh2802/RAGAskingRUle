import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import pymupdf

from regularag.ingestion.manifest import load_manifest
from regularag.ingestion.page_quality import text_hash


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export per-page hashes, source text and layout images."
    )
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed/structured"))
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/documents.csv"))
    parser.add_argument(
        "--inventory", type=Path, default=Path("data/manifests/page_review_inventory.csv")
    )
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    records = []
    for path in sorted(args.input_dir.glob("*/pages.jsonl")):
        document_id = path.parent.name
        source = manifest[document_id]
        review_directory = path.parent / "review_pages"
        review_directory.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(source["local_path"]) as pdf:
            for line in path.read_text(encoding="utf-8").splitlines():
                page = json.loads(line)
                number = page["pdf_page_number"]
                records.append(
                    {
                        "document_id": document_id,
                        "pdf_page": number,
                        "source_sha256": source["sha256"],
                        "cleaned_text_sha256": text_hash(page["cleaned_text"]),
                        "extraction_method": page["extraction_method"],
                        "review_status": page["review_status"],
                        "quality_flags": ";".join(page["quality_flags"]),
                    }
                )
                (review_directory / f"page-{number:03d}.md").write_text(
                    f"# {document_id}, PDF page {number}\n\n"
                    f"Flags: {page['quality_flags']}\n\n" + page["cleaned_text"] + "\n",
                    encoding="utf-8",
                )
                if page["extraction_method"] == "pymupdf_text":
                    geometry = []
                    for block in pdf[number - 1].get_text("dict", sort=True)["blocks"]:
                        for entry in block.get("lines", []):
                            text = "".join(span["text"] for span in entry["spans"])
                            if text.strip().isdigit() or text.lower().strip().startswith("trang "):
                                geometry.append(
                                    {"block": block["number"], "bbox": entry["bbox"], "text": text}
                                )
                    (review_directory / f"page-{number:03d}.geometry.json").write_text(
                        json.dumps(
                            {
                                "rect": list(pdf[number - 1].rect),
                                "numeric_lines": geometry,
                                "numeric_blocks": [
                                    {
                                        "block": block[5],
                                        "bbox": list(block[:4]),
                                        "text": block[4],
                                        "type": block[6],
                                    }
                                    for block in pdf[number - 1].get_text("blocks", sort=True)
                                    if block[4].strip().isdigit()
                                ],
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                if page["quality_flags"] or page["removed_margins"]:
                    pdf[number - 1].get_pixmap(dpi=150, alpha=False).save(
                        review_directory / f"page-{number:03d}.png"
                    )
    args.inventory.parent.mkdir(parents=True, exist_ok=True)
    with args.inventory.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(
        json.dumps(
            {
                "pages": len(records),
                "extraction_methods": dict(Counter(row["extraction_method"] for row in records)),
                "review_status": dict(Counter(row["review_status"] for row in records)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
