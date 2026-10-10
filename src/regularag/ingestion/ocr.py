import csv
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pymupdf
from pydantic import BaseModel, Field


class OcrConfig(BaseModel):
    enabled: bool = False
    language: str = "vie+eng"
    engine_version: str = "5.5.2"
    dpi: int = Field(default=300, ge=150, le=450)
    page_segmentation_mode: int = Field(default=3, ge=3, le=6)
    timeout_seconds: int = Field(default=120, ge=10)
    cpu_threads: int = Field(default=2, ge=1, le=4)
    force_document_ids: list[str] = Field(default_factory=list)
    minimum_mean_confidence: float = Field(default=70, ge=0, le=100)
    maximum_low_confidence_ratio: float = Field(default=0.25, ge=0, le=1)


@dataclass(frozen=True, slots=True)
class OcrResult:
    text: str
    mean_confidence: float
    low_confidence_ratio: float
    word_count: int
    provenance: dict


class TesseractOcr:
    def __init__(self, config: OcrConfig) -> None:
        self.config = config
        candidate = shutil.which("tesseract")
        self.executable = (
            Path(candidate) if candidate else Path(sys.prefix) / "Library/bin/tesseract.exe"
        )
        self.tessdata = Path(sys.prefix) / "share/tessdata"
        if not self.executable.is_file():
            raise RuntimeError("Tesseract executable is unavailable in this environment")
        output = subprocess.run(
            [str(self.executable), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=10,
        )
        self.version = (output.stdout or output.stderr).splitlines()[0].split()[1]
        if self.version != config.engine_version:
            raise ValueError(f"Expected Tesseract {config.engine_version}, found {self.version}")
        self.language_hashes = {}
        for language in config.language.split("+"):
            if not language.isalpha():
                raise ValueError("OCR language must use traineddata language identifiers")
            path = self.tessdata / f"{language}.traineddata"
            self.language_hashes[language] = sha256(path.read_bytes()).hexdigest()

    def recognize(self, page: pymupdf.Page, output_directory: Path) -> OcrResult:
        output_directory.mkdir(parents=True, exist_ok=True)
        image_path = output_directory / f"page-{page.number + 1:03d}.png"
        prefix = output_directory / f"page-{page.number + 1:03d}"
        pixmap = page.get_pixmap(dpi=self.config.dpi, colorspace=pymupdf.csRGB, alpha=False)
        pixmap.save(image_path)
        environment = {
            **os.environ,
            "OMP_THREAD_LIMIT": str(self.config.cpu_threads),
            "TESSDATA_PREFIX": str(self.tessdata),
        }
        subprocess.run(
            [
                str(self.executable),
                str(image_path),
                str(prefix),
                "--tessdata-dir",
                str(self.tessdata),
                "-l",
                self.config.language,
                "--dpi",
                str(self.config.dpi),
                "--psm",
                str(self.config.page_segmentation_mode),
                "--oem",
                "1",
                "txt",
                "tsv",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.config.timeout_seconds,
            env=environment,
        )
        text = prefix.with_suffix(".txt").read_text(encoding="utf-8")
        confidences = []
        with prefix.with_suffix(".tsv").open(encoding="utf-8", newline="") as tsv_file:
            for row in csv.DictReader(tsv_file, delimiter="\t"):
                confidence = float(row["conf"])
                if row.get("text", "").strip() and confidence >= 0:
                    confidences.append(confidence)
        mean = sum(confidences) / len(confidences) if confidences else 0
        low_ratio = (
            sum(value < 50 for value in confidences) / len(confidences) if confidences else 1
        )
        return OcrResult(
            text,
            round(mean, 3),
            round(low_ratio, 4),
            len(confidences),
            {
                "engine": "tesseract",
                "engine_version": self.version,
                "config": self.config.model_dump(),
                "traineddata_sha256": self.language_hashes,
                "image_sha256": sha256(image_path.read_bytes()).hexdigest(),
                "ocr_text_sha256": sha256(text.encode("utf-8")).hexdigest(),
                "image_path": str(image_path.resolve()),
                "tsv_path": str(prefix.with_suffix(".tsv").resolve()),
            },
        )

    def runtime_identity(self) -> dict:
        return {
            "engine": "tesseract",
            "engine_version": self.version,
            "traineddata_sha256": self.language_hashes,
        }
