from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import numpy as np
import psycopg

from regularag.core.config import Settings
from regularag.db.ingestion import LIFECYCLE_VERSION, DocumentSnapshot, IngestionRepository
from regularag.ingestion.artifacts import (
    PreparedDocument,
    QualityReviewRequired,
    fingerprint,
    load_processed,
)
from regularag.ingestion.page_quality import review_inputs
from regularag.ingestion.pipeline import BaselineIngestionConfig, process_document
from regularag.ingestion.tokenizer import HuggingFaceTokenizer, TextTokenizer
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.embedding import Embedder


class IngestionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class IngestionResult:
    document_id: str
    run_id: str
    status: Literal["ready", "failed"]
    outcome: Literal["ingested", "unchanged", "failed"]
    chunk_count: int = 0
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteResult:
    document_id: str
    run_id: str
    deleted: bool
    chunks_deleted: int
    error_code: str | None = None


class IngestionLifecycle:
    def __init__(
        self,
        settings: Settings,
        config: RagBaselineConfig,
        embedder: Embedder,
        ingestion_config: BaselineIngestionConfig | None = None,
        tokenizer: TextTokenizer | None = None,
    ) -> None:
        if embedder.dimension != config.embedding.dimension or embedder.dimension != 384:
            raise ValueError("the baseline schema requires 384-dimensional embeddings")
        self.config = config
        self.embedder = embedder
        self.ingestion_config = ingestion_config
        self.tokenizer = tokenizer
        self.repository = IngestionRepository(settings, config)

    def _pipeline_config(self, kind: str, document_id: str | None = None) -> dict:
        quality_inputs = {}
        ocr_identity = None
        config = self.ingestion_config
        if kind == "pdf" and config and config.parser_mode == "structured":
            quality_inputs = review_inputs(
                document_id or "", config.review_manifest, config.corrections_root
            )
            if config.ocr.enabled:
                from regularag.ingestion.ocr import TesseractOcr

                ocr_identity = TesseractOcr(config.ocr).runtime_identity()
        return {
            "lifecycle_version": LIFECYCLE_VERSION,
            "input_kind": kind,
            "chunking": self.ingestion_config.model_dump(mode="json")
            if self.ingestion_config
            else None,
            "parser_library": version("pymupdf") if kind == "pdf" else None,
            "embedding": self.config.embedding.model_dump(),
            "quality_inputs": quality_inputs,
            "ocr_runtime": ocr_identity,
        }

    def _fingerprint(self, pipeline: dict, prepared: PreparedDocument | None = None) -> str:
        return fingerprint(
            {
                "lifecycle_version": LIFECYCLE_VERSION,
                "input_kind": pipeline["input_kind"],
                "chunking": prepared.chunking_config if prepared else pipeline["chunking"],
                "parser_library": pipeline["parser_library"],
                "embedding_fingerprint": self.config.embedding.fingerprint,
                "quality_inputs": pipeline["quality_inputs"],
                "ocr_runtime": pipeline["ocr_runtime"],
                "chunks": prepared.chunks
                if prepared and pipeline["input_kind"] == "processed"
                else None,
                "quality": prepared.quality
                if prepared and pipeline["input_kind"] == "processed"
                else None,
            }
        )

    def _can_skip(self, snapshot: DocumentSnapshot | None, source_hash: str, digest: str) -> bool:
        return bool(
            snapshot
            and snapshot.ingestion_status == "ready"
            and snapshot.retrieval_status == "ready"
            and snapshot.source_sha256 == source_hash
            and snapshot.ingestion_fingerprint == digest
            and snapshot.indexed_chunk_count > 0
            and snapshot.indexed_chunk_count
            == snapshot.actual_chunk_count
            == snapshot.matching_chunk_count
        )

    def _check_approval(self, document: dict[str, str], input_kind: str) -> None:
        if (
            input_kind == "pdf"
            and document.get("pdf_type") == "scan"
            and not (
                self.ingestion_config
                and self.ingestion_config.parser_mode == "structured"
                and self.ingestion_config.ocr.enabled
            )
        ):
            raise IngestionError(
                "ocr_required", "Source is a scanned PDF and requires verified OCR"
            )
        if document["document_id"] not in self.config.retrieval.eligible_document_ids:
            raise IngestionError(
                "quality_not_approved", "Document is not in the approved retrieval allowlist"
            )

    def _prepare_pdf(
        self,
        document: dict[str, str],
        source: Path,
        output_root: Path,
        run_id: UUID,
    ) -> PreparedDocument:
        config = self.ingestion_config
        if config is None:
            raise ValueError("PDF ingestion requires a chunking config")
        if self.tokenizer is None:
            self.tokenizer = HuggingFaceTokenizer(config.tokenizer_model, config.tokenizer_revision)
        attempt_root = output_root / str(run_id)
        source_document = {**document, "local_path": str(source.resolve())}
        process_document(source_document, Path.cwd(), attempt_root, config, self.tokenizer)
        return load_processed(document, attempt_root / document["document_id"])

    def _error(self, exc: Exception) -> tuple[str, str]:
        if isinstance(exc, IngestionError):
            return exc.code, str(exc)
        if isinstance(exc, QualityReviewRequired):
            return "quality_review_required", str(exc)
        if isinstance(exc, FileNotFoundError):
            return "source_missing", "Source or processed artifact does not exist"
        if isinstance(exc, psycopg.Error):
            return "database_write_error", "Database rejected this document update"
        return "processing_error", f"{type(exc).__name__}: {str(exc)[:800]}"

    def ingest(
        self,
        document: dict[str, str],
        source: Path,
        *,
        input_kind: Literal["pdf", "processed"],
        output_root: Path | None = None,
        force: bool = False,
    ) -> IngestionResult:
        document_id = document["document_id"]
        run_id = uuid4()
        pipeline = self._pipeline_config(input_kind, document_id)
        source_path = str(source.resolve())
        with self.repository.session() as connection:
            acquired = self.repository.lock(connection, document_id)
            if not acquired:
                self.repository.rejected(
                    connection,
                    run_id,
                    document_id,
                    "ingest",
                    source_path,
                    document["sha256"],
                    pipeline,
                    "document_busy",
                    "Another worker owns this document",
                )
                return IngestionResult(
                    document_id, str(run_id), "failed", "failed", error_code="document_busy"
                )
            registered = False
            try:
                snapshot = self.repository.snapshot(connection, document_id)
                initial_digest = self._fingerprint(pipeline) if input_kind == "pdf" else None
                self.repository.begin(
                    connection, run_id, document, source_path, pipeline, initial_digest
                )
                registered = True
                self.repository.processing(connection, run_id, document_id)
                prepared = None
                if input_kind == "pdf":
                    actual_hash = sha256(source.read_bytes()).hexdigest()
                    self.repository.actual_hash(connection, run_id, actual_hash)
                    if actual_hash != document["sha256"]:
                        raise IngestionError(
                            "source_hash_mismatch", "Source hash does not match manifest"
                        )
                    if source.suffix.lower() != ".pdf":
                        raise IngestionError(
                            "unsupported_source_type", "Only PDF sources are supported"
                        )
                else:
                    prepared = load_processed(document, source)
                    actual_hash = document["sha256"]
                    self.repository.preparation(
                        connection,
                        run_id,
                        prepared.chunking_config,
                        self._fingerprint(pipeline, prepared),
                        str(prepared.artifact_path),
                    )
                self._check_approval(document, input_kind)
                digest = self._fingerprint(pipeline, prepared)

                if not force and self._can_skip(snapshot, actual_hash, digest):
                    with connection.transaction():
                        self.repository.ready(
                            connection,
                            run_id,
                            document,
                            digest,
                            snapshot.indexed_chunk_count,
                            "unchanged",
                            snapshot.artifact_path,
                            snapshot.quality,
                        )
                    return IngestionResult(
                        document_id,
                        str(run_id),
                        "ready",
                        "unchanged",
                        snapshot.indexed_chunk_count,
                    )

                if prepared is None:
                    if output_root is None:
                        raise ValueError("PDF ingestion requires an artifact output directory")
                    prepared = self._prepare_pdf(document, source, output_root, run_id)
                digest = self._fingerprint(pipeline, prepared)
                self.repository.preparation(
                    connection,
                    run_id,
                    prepared.chunking_config,
                    digest,
                    str(prepared.artifact_path),
                )
                embeddings = self.embedder.embed_documents(
                    [chunk["text"] for chunk in prepared.chunks]
                )
                if len(embeddings) != len(prepared.chunks) or any(
                    vector.shape != (self.config.embedding.dimension,)
                    or not np.isfinite(vector).all()
                    or np.linalg.norm(vector) == 0
                    for vector in embeddings
                ):
                    raise IngestionError(
                        "invalid_embedding", "Model returned invalid chunk vectors"
                    )

                with connection.transaction():
                    self.repository.replace_chunks(
                        connection,
                        run_id,
                        document_id,
                        prepared.chunks,
                        embeddings,
                        prepared.chunking_config["pipeline_version"],
                    )
                    self.repository.ready(
                        connection,
                        run_id,
                        document,
                        digest,
                        len(prepared.chunks),
                        "ingested",
                        str(prepared.artifact_path),
                        prepared.quality,
                    )
                return IngestionResult(
                    document_id, str(run_id), "ready", "ingested", len(prepared.chunks)
                )
            except Exception as exc:
                if isinstance(exc, psycopg.OperationalError):
                    raise
                code, message = self._error(exc)
                if registered:
                    self.repository.failed(connection, run_id, document_id, code, message)
                else:
                    self.repository.rejected(
                        connection,
                        run_id,
                        document_id,
                        "ingest",
                        source_path,
                        document["sha256"],
                        pipeline,
                        code,
                        message,
                    )
                return IngestionResult(
                    document_id,
                    str(run_id),
                    "failed",
                    "failed",
                    error_code=code,
                    error_message=message,
                )
            except (KeyboardInterrupt, SystemExit):
                if registered:
                    self.repository.failed(
                        connection, run_id, document_id, "interrupted", "Worker was interrupted"
                    )
                raise
            finally:
                if not connection.closed:
                    self.repository.unlock(connection, document_id)

    def reject_unregistered(self, source: Path) -> IngestionResult:
        run_id = uuid4()
        identity = "unregistered:" + fingerprint(str(source.resolve()))[:16]
        with self.repository.session() as connection:
            self.repository.rejected(
                connection,
                run_id,
                identity,
                "ingest",
                str(source.resolve()),
                None,
                self._pipeline_config("pdf"),
                "source_not_registered",
                "Source has no document metadata in manifest",
            )
        return IngestionResult(
            identity,
            str(run_id),
            "failed",
            "failed",
            error_code="source_not_registered",
            error_message="Source has no document metadata in manifest",
        )

    def delete(self, document_id: str) -> DeleteResult:
        run_id = uuid4()
        with self.repository.session() as connection:
            if not self.repository.lock(connection, document_id):
                self.repository.rejected(
                    connection,
                    run_id,
                    document_id,
                    "delete",
                    None,
                    None,
                    self._pipeline_config("delete"),
                    "document_busy",
                    "Another worker owns this document",
                )
                return DeleteResult(document_id, str(run_id), False, 0, "document_busy")
            try:
                removed = self.repository.delete(
                    connection, run_id, document_id, self._pipeline_config("delete")
                )
                return DeleteResult(document_id, str(run_id), removed is not None, removed or 0)
            finally:
                self.repository.unlock(connection, document_id)
