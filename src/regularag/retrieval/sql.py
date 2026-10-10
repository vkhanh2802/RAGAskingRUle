from regularag.retrieval.config import RagBaselineConfig

CHUNK_COLUMNS = """
    c.chunk_id, c.document_id, d.document_number, d.title, d.source_url,
    d.legal_status, d.document_role, d.related_document_number,
    d.coverage_status, d.excluded_pdf_pages,
    COALESCE(d.metadata->'_ingestion_quality'->'omitted_layout_pdf_pages', '[]'::jsonb)
        AS omitted_layout_pdf_pages,
    c.chapter, c.article, c.clauses, c.extraction_methods,
    d.domain, d.document_type, d.applies_to, d.cohort_from, d.cohort_to,
    d.effective_from_date::text AS effective_from_date,
    d.effective_to_date::text AS effective_to_date,
    COALESCE(d.metadata->>'cohort_scope', '') AS cohort_scope,
    COALESCE(d.metadata->>'effective_from', '') AS effective_from,
    COALESCE(d.metadata->>'metadata_note', '') AS metadata_note,
    d.source_sha256, c.content_sha256,
    NULLIF(d.metadata->>'issued_date', '') AS issued_date,
    NULLIF(d.metadata->>'source_checked_at', '') AS source_checked_at,
    COALESCE(d.metadata->>'source_check_status', 'unchecked') AS source_check_status,
    EXISTS (
        SELECT 1 FROM documents AS related
        WHERE related.document_number = d.related_document_number
          AND related.retrieval_status = 'ready' AND related.ingestion_status = 'ready'
          AND related.coverage_status = 'full'
          AND related.document_id = ANY(%(eligible_ids)s)
          AND EXISTS (
              SELECT 1 FROM chunks AS related_chunk
              WHERE related_chunk.document_id = related.document_id
                AND related_chunk.embedding_fingerprint = %(fingerprint)s
                AND related_chunk.quality_status = 'approved'
          )
    ) AS related_document_ready,
    c.text, c.pdf_page_start, c.pdf_page_end, c.printed_page_start, c.printed_page_end
"""

READY_FILTER = """
    d.retrieval_status = 'ready' AND d.ingestion_status = 'ready'
    AND d.document_id = ANY(%(eligible_ids)s)
    AND c.embedding_model = %(model)s AND c.embedding_revision = %(revision)s
    AND c.embedding_fingerprint = %(fingerprint)s AND c.quality_status = 'approved'
"""


def retrieval_parameters(config: RagBaselineConfig) -> dict:
    return {
        "model": config.embedding.model_name,
        "revision": config.embedding.model_revision,
        "fingerprint": config.embedding.fingerprint,
        "eligible_ids": config.retrieval.eligible_document_ids,
    }
