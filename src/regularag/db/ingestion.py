from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from regularag.core.config import Settings
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.embedding import FloatVector

LIFECYCLE_VERSION = "lifecycle-v1"


@dataclass(frozen=True, slots=True)
class DocumentSnapshot:
    source_sha256: str
    ingestion_status: str
    retrieval_status: str
    ingestion_fingerprint: str | None
    indexed_chunk_count: int
    actual_chunk_count: int
    matching_chunk_count: int
    artifact_path: str | None
    quality: dict


class IngestionRepository:
    def __init__(self, settings: Settings, config: RagBaselineConfig) -> None:
        self.settings = settings
        self.config = config

    @contextmanager
    def session(self):
        with psycopg.connect(
            str(self.settings.database_url),
            connect_timeout=self.settings.database_connect_timeout_seconds,
            autocommit=True,
            row_factory=dict_row,
        ) as connection:
            yield connection

    def _lock_key(self, connection, document_id: str) -> str:
        schema = connection.execute("SELECT current_schema() AS schema").fetchone()["schema"]
        return f"{schema}:regularag:document:{document_id}"

    def lock(self, connection, document_id: str) -> bool:
        row = connection.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS acquired",
            (self._lock_key(connection, document_id),),
        ).fetchone()
        return row["acquired"]

    def unlock(self, connection, document_id: str) -> None:
        connection.execute(
            "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
            (self._lock_key(connection, document_id),),
        )

    def snapshot(self, connection, document_id: str) -> DocumentSnapshot | None:
        row = connection.execute(
            """
            SELECT d.source_sha256, d.ingestion_status, d.retrieval_status,
                   d.ingestion_fingerprint, d.indexed_chunk_count,
                   COALESCE(d.metadata->'_ingestion_quality', '{}'::jsonb) AS quality,
                   (SELECT artifact_path FROM ingestion_runs r
                        WHERE r.run_id = d.last_ingestion_run_id) AS artifact_path,
                   (SELECT COUNT(*) FROM chunks c WHERE c.document_id = d.document_id)
                       AS actual_chunk_count,
                   (SELECT COUNT(*) FROM chunks c WHERE c.document_id = d.document_id
                        AND c.embedding_fingerprint = %s) AS matching_chunk_count
            FROM documents d WHERE d.document_id = %s
            """,
            (self.config.embedding.fingerprint, document_id),
        ).fetchone()
        return DocumentSnapshot(**row) if row else None

    def _insert_run(
        self,
        connection,
        run_id: UUID,
        document_id: str,
        operation: str,
        source_path: str | None,
        requested_hash: str | None,
        pipeline_config: dict,
        fingerprint: str | None,
        linked: bool,
    ) -> None:
        connection.execute(
            """
            INSERT INTO ingestion_runs (
                run_id, document_id, document_id_snapshot, operation, source_path,
                requested_source_sha256, pipeline_version, pipeline_config,
                embedding_model, embedding_revision, embedding_fingerprint,
                ingestion_fingerprint, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            """,
            (
                run_id,
                document_id if linked else None,
                document_id,
                operation,
                source_path,
                requested_hash,
                LIFECYCLE_VERSION,
                Jsonb(pipeline_config),
                self.config.embedding.model_name,
                self.config.embedding.model_revision,
                self.config.embedding.fingerprint,
                fingerprint,
            ),
        )

    def begin(
        self,
        connection,
        run_id: UUID,
        document: dict[str, str],
        source_path: str,
        pipeline_config: dict,
        fingerprint: str | None,
    ) -> None:
        document_id = document["document_id"]
        with connection.transaction():
            self.recover_interrupted(connection, document_id)
            connection.execute(
                """
                INSERT INTO documents (
                    document_id, document_number, title, source_url, source_sha256,
                    legal_status, document_role, related_document_number,
                    retrieval_status, ingestion_status, metadata, coverage_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'blocked', 'pending', %s, 'unreviewed')
                ON CONFLICT (document_id) DO UPDATE SET
                    ingestion_status = 'pending', retrieval_status = 'blocked',
                    last_error = NULL, updated_at = CURRENT_TIMESTAMP
                """,
                (
                    document_id,
                    document["document_number"],
                    document["title"],
                    document["source_url"],
                    document["sha256"],
                    document["legal_status"],
                    document["document_role"],
                    document["related_document_number"] or None,
                    Jsonb(document),
                ),
            )
            self._insert_run(
                connection,
                run_id,
                document_id,
                "ingest",
                source_path,
                document["sha256"],
                pipeline_config,
                fingerprint,
                linked=True,
            )
            connection.execute(
                "UPDATE documents SET last_ingestion_run_id = %s WHERE document_id = %s",
                (run_id, document_id),
            )

    def recover_interrupted(self, connection, document_id: str) -> None:
        # The caller owns the session lock, so no older attempt can still have a live worker.
        connection.execute(
            """
            UPDATE ingestion_runs SET status = 'failed', outcome = 'failed',
                error_code = 'interrupted',
                error_message = 'Previous worker stopped before completion',
                finished_at = CURRENT_TIMESTAMP
            WHERE document_id_snapshot = %s AND status IN ('pending', 'processing')
            """,
            (document_id,),
        )

    def processing(self, connection, run_id: UUID, document_id: str) -> None:
        with connection.transaction():
            connection.execute(
                "UPDATE ingestion_runs SET status = 'processing', started_at = CURRENT_TIMESTAMP "
                "WHERE run_id = %s AND status = 'pending'",
                (run_id,),
            )
            connection.execute(
                "UPDATE documents SET ingestion_status = 'processing', "
                "updated_at = CURRENT_TIMESTAMP "
                "WHERE document_id = %s AND last_ingestion_run_id = %s",
                (document_id, run_id),
            )

    def actual_hash(self, connection, run_id: UUID, source_hash: str) -> None:
        connection.execute(
            "UPDATE ingestion_runs SET actual_source_sha256 = %s WHERE run_id = %s",
            (source_hash, run_id),
        )

    def preparation(
        self,
        connection,
        run_id: UUID,
        chunking_config: dict,
        fingerprint: str,
        artifact_path: str,
    ) -> None:
        connection.execute(
            """
            UPDATE ingestion_runs
            SET pipeline_config = jsonb_set(pipeline_config, '{chunking}', %s),
                ingestion_fingerprint = %s, artifact_path = %s WHERE run_id = %s
            """,
            (Jsonb(chunking_config), fingerprint, artifact_path, run_id),
        )

    def failed(self, connection, run_id: UUID, document_id: str, code: str, message: str) -> None:
        with connection.transaction():
            connection.execute(
                """
                UPDATE ingestion_runs SET status = 'failed', outcome = 'failed', error_code = %s,
                    error_message = %s, finished_at = CURRENT_TIMESTAMP WHERE run_id = %s
                """,
                (code, message, run_id),
            )
            connection.execute(
                """
                UPDATE documents SET ingestion_status = 'failed', retrieval_status = 'blocked',
                    last_error = %s, updated_at = CURRENT_TIMESTAMP,
                    coverage_status = CASE WHEN indexed_chunk_count = 0 THEN 'unreviewed'
                        ELSE coverage_status END
                WHERE document_id = %s AND last_ingestion_run_id = %s
                """,
                (Jsonb({"code": code, "message": message}), document_id, run_id),
            )

    def rejected(
        self,
        connection,
        run_id: UUID,
        document_id: str,
        operation: str,
        source_path: str | None,
        requested_hash: str | None,
        pipeline_config: dict,
        code: str,
        message: str,
    ) -> None:
        # No document link/state change for an unregistered source or a busy document.
        with connection.transaction():
            self._insert_run(
                connection,
                run_id,
                document_id,
                operation,
                source_path,
                requested_hash,
                pipeline_config,
                None,
                linked=False,
            )
            connection.execute(
                """
                UPDATE ingestion_runs SET status = 'failed', outcome = 'failed', error_code = %s,
                    error_message = %s, finished_at = CURRENT_TIMESTAMP WHERE run_id = %s
                """,
                (code, message, run_id),
            )

    def ready(
        self,
        connection,
        run_id: UUID,
        document: dict[str, str],
        fingerprint: str,
        chunk_count: int,
        outcome: Literal["ingested", "unchanged"],
        artifact_path: str | None,
        quality: dict | None = None,
    ) -> None:
        quality = quality or {"coverage_status": "full", "excluded_pdf_pages": []}
        metadata = {**document, "_ingestion_quality": quality}
        connection.execute(
            """
            UPDATE documents SET document_number = %s, title = %s, source_url = %s,
                source_sha256 = %s, legal_status = %s, document_role = %s,
                related_document_number = %s, metadata = %s, ingestion_status = 'ready',
                retrieval_status = 'ready', ingestion_fingerprint = %s,
                ingestion_pipeline_version = %s, indexed_chunk_count = %s,
                last_error = NULL, updated_at = CURRENT_TIMESTAMP,
                coverage_status = %s, excluded_pdf_pages = %s
            WHERE document_id = %s AND last_ingestion_run_id = %s
            """,
            (
                document["document_number"],
                document["title"],
                document["source_url"],
                document["sha256"],
                document["legal_status"],
                document["document_role"],
                document["related_document_number"] or None,
                Jsonb(metadata),
                fingerprint,
                LIFECYCLE_VERSION,
                chunk_count,
                quality["coverage_status"],
                quality["excluded_pdf_pages"],
                document["document_id"],
                run_id,
            ),
        )
        connection.execute(
            """
            UPDATE ingestion_runs SET status = 'ready', outcome = %s, chunk_count = %s,
                artifact_path = %s, ingestion_fingerprint = %s, finished_at = CURRENT_TIMESTAMP
            WHERE run_id = %s
            """,
            (outcome, chunk_count, artifact_path, fingerprint, run_id),
        )

    def replace_chunks(
        self,
        connection,
        run_id: UUID,
        document_id: str,
        chunks: list[dict],
        embeddings: list[FloatVector],
        chunking_version: str,
    ) -> None:
        register_vector(connection)
        connection.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO chunks (
                    chunk_id, document_id, chunk_index, text, token_count,
                    pdf_page_start, pdf_page_end, printed_page_start, printed_page_end,
                    source_pdf_pages, source_printed_pages, content_sha256,
                    chunking_pipeline_version, embedding_model, embedding_revision,
                    embedding_fingerprint, embedding, ingestion_run_id,
                    chapter, article, clauses, heading, part_index, extraction_methods,
                    quality_flags, source_spans, quality_status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                [
                    (
                        chunk["chunk_id"],
                        document_id,
                        chunk["chunk_index"],
                        chunk["text"],
                        chunk["token_count"],
                        chunk["pdf_page_start"],
                        chunk["pdf_page_end"],
                        chunk["printed_page_start"],
                        chunk["printed_page_end"],
                        chunk["source_pdf_pages"],
                        chunk["source_printed_pages"],
                        chunk["content_sha256"],
                        chunking_version,
                        self.config.embedding.model_name,
                        self.config.embedding.model_revision,
                        self.config.embedding.fingerprint,
                        embedding,
                        run_id,
                        chunk.get("chapter"),
                        chunk.get("article"),
                        Jsonb(chunk.get("clauses", [])),
                        chunk.get("heading", ""),
                        chunk.get("part_index", 0),
                        Jsonb(chunk.get("extraction_methods", ["pymupdf_text"])),
                        Jsonb(chunk.get("quality_flags", [])),
                        Jsonb(chunk.get("source_spans", [])),
                        chunk.get("quality_status", "approved"),
                    )
                    for chunk, embedding in zip(chunks, embeddings, strict=True)
                ],
            )

    def delete(
        self, connection, run_id: UUID, document_id: str, pipeline_config: dict
    ) -> int | None:
        snapshot = self.snapshot(connection, document_id)
        with connection.transaction():
            self.recover_interrupted(connection, document_id)
            self._insert_run(
                connection,
                run_id,
                document_id,
                "delete",
                None,
                None,
                pipeline_config,
                None,
                linked=snapshot is not None,
            )
            connection.execute(
                "UPDATE ingestion_runs SET status = 'processing', started_at = CURRENT_TIMESTAMP "
                "WHERE run_id = %s",
                (run_id,),
            )
            connection.execute("DELETE FROM documents WHERE document_id = %s", (document_id,))
            connection.execute(
                """
                UPDATE ingestion_runs SET status = 'ready', outcome = %s, chunk_count = %s,
                    finished_at = CURRENT_TIMESTAMP WHERE run_id = %s
                """,
                (
                    "deleted" if snapshot else "not_found",
                    snapshot.actual_chunk_count if snapshot else 0,
                    run_id,
                ),
            )
        return snapshot.actual_chunk_count if snapshot else None

    def status(self, document_id: str | None = None) -> list[dict]:
        with self.session() as connection:
            return connection.execute(
                """
                SELECT document_id, document_number, ingestion_status, retrieval_status,
                       indexed_chunk_count, ingestion_fingerprint, last_ingestion_run_id,
                       last_error, updated_at, coverage_status, excluded_pdf_pages
                FROM documents WHERE %s::text IS NULL OR document_id = %s ORDER BY document_id
                """,
                (document_id, document_id),
            ).fetchall()

    def history(self, document_id: str | None = None) -> list[dict]:
        with self.session() as connection:
            return connection.execute(
                """
                SELECT run_id, document_id, document_id_snapshot, operation, status, outcome,
                       requested_source_sha256, actual_source_sha256, pipeline_version,
                       pipeline_config,
                       embedding_model, embedding_revision, embedding_fingerprint,
                       ingestion_fingerprint, chunk_count, artifact_path, error_code, error_message,
                       queued_at, started_at, finished_at
                FROM ingestion_runs WHERE %s::text IS NULL OR document_id_snapshot = %s
                ORDER BY queued_at, run_id
                """,
                (document_id, document_id),
            ).fetchall()
