from dataclasses import dataclass, replace
from typing import Literal

import numpy as np
import psycopg
from numpy.typing import NDArray
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from regularag.core.config import Settings
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.filters import METADATA_FILTER, RetrievalFilters, filter_parameters
from regularag.retrieval.sql import CHUNK_COLUMNS, READY_FILTER, retrieval_parameters


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_number: str
    title: str
    source_url: str
    legal_status: str
    document_role: str
    related_document_number: str | None
    text: str
    pdf_page_start: int
    pdf_page_end: int
    printed_page_start: int | None
    printed_page_end: int | None
    score: float
    related_document_ready: bool = False
    cohort_scope: str = ""
    effective_from: str = ""
    chapter: str | None = None
    article: str | None = None
    clauses: tuple[str, ...] = ()
    extraction_methods: tuple[str, ...] = ("pymupdf_text",)
    coverage_status: str = "full"
    excluded_pdf_pages: tuple[int, ...] = ()
    omitted_layout_pdf_pages: tuple[int, ...] = ()
    score_kind: Literal["cosine_similarity", "ts_rank_cd", "rrf", "freshness_dependency"] = (
        "cosine_similarity"
    )
    retrieval_branches: tuple[str, ...] = ()
    rank: int = 0
    dense_rank: int | None = None
    keyword_rank: int | None = None
    dense_score: float | None = None
    keyword_score: float | None = None
    rrf_score: float | None = None
    domain: str = ""
    document_type: str = ""
    applies_to: str = ""
    cohort_from: int | None = None
    cohort_to: int | None = None
    effective_from_date: str | None = None
    effective_to_date: str | None = None
    metadata_note: str = ""
    source_sha256: str = ""
    content_sha256: str = ""
    issued_date: str | None = None
    source_checked_at: str | None = None
    source_check_status: str = "unchecked"
    first_stage_rank: int | None = None
    rerank_rank: int | None = None
    rerank_score: float | None = None
    rerank_windows: int = 0
    freshness_status: str = "unchecked"
    latest_document_number: str | None = None
    latest_issued_date: str | None = None
    required_update_chunk_ids: tuple[str, ...] = ()
    freshness_failure: str | None = None
    amendment_required: bool = True
    evidence_char_ranges: tuple[tuple[int, int], ...] = ()


class PgVectorRepository:
    def __init__(self, settings: Settings, config: RagBaselineConfig) -> None:
        self.settings = settings
        self.config = config

    def search(
        self,
        query_embedding: NDArray,
        limit: int,
        filters: RetrievalFilters | None = None,
        document_codes: tuple[str, ...] = (),
    ) -> list[RetrievedChunk]:
        if not 1 <= limit <= 100:
            raise ValueError("candidate retrieval limit must be between 1 and 100")
        if query_embedding.shape != (self.config.embedding.dimension,):
            raise ValueError("query embedding has the wrong dimension")
        if not np.isfinite(query_embedding).all() or np.linalg.norm(query_embedding) == 0:
            raise ValueError("query embedding must be finite and nonzero")

        with psycopg.connect(
            str(self.settings.database_url),
            connect_timeout=self.settings.database_connect_timeout_seconds,
            row_factory=dict_row,
        ) as connection:
            register_vector(connection)
            rows = connection.execute(
                f"""
                SELECT {CHUNK_COLUMNS}, 1 - (c.embedding <=> %(embedding)s) AS score
                FROM chunks AS c
                JOIN documents AS d ON d.document_id = c.document_id
                WHERE {READY_FILTER} AND {METADATA_FILTER}
                  AND (%(query_codes)s::text[] = '{{}}'
                       OR split_part(d.document_number, '/', 1) = ANY(%(query_codes)s))
                ORDER BY c.embedding <=> %(embedding)s
                LIMIT %(limit)s
                """,
                {
                    "embedding": query_embedding,
                    **retrieval_parameters(self.config),
                    **filter_parameters(filters),
                    "limit": limit,
                    "query_codes": list(document_codes),
                },
            ).fetchall()

        return [
            replace(
                RetrievedChunk(**row),
                rank=rank,
                dense_rank=rank,
                dense_score=float(row["score"]),
                retrieval_branches=("vector",),
            )
            for rank, row in enumerate(rows, start=1)
        ]
