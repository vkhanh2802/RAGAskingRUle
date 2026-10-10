import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pymupdf

from regularag.ingestion.manifest import load_manifest
from regularag.ingestion.ocr import OcrConfig, TesseractOcr


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render and OCR source PDFs for visual comparison."
    )
    parser.add_argument("--document-id", action="append", default=[])
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/documents.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/ocr-probe"))
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--psm", type=int, default=3)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    engine = TesseractOcr(OcrConfig(enabled=True, dpi=args.dpi, page_segmentation_mode=args.psm))
    for document_id in args.document_id or ["uit_1393_2023", "uit_43_2020"]:
        row = manifest[document_id]
        output = args.output_dir / document_id
        with pymupdf.open(row["local_path"]) as document:
            for page in document:
                result = engine.recognize(page, output)
                (output / f"page-{page.number + 1:03d}.json").write_text(
                    json.dumps(asdict(result), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(
                    json.dumps(
                        {
                            "document_id": document_id,
                            "pdf_page": page.number + 1,
                            "mean_confidence": result.mean_confidence,
                            "low_confidence_ratio": result.low_confidence_ratio,
                            "word_count": result.word_count,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    main()
