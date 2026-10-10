ALTER TABLE documents
    ADD COLUMN coverage_status TEXT NOT NULL DEFAULT 'full'
        CHECK (coverage_status IN ('full', 'partial', 'unreviewed')),
    ADD COLUMN excluded_pdf_pages INTEGER[] NOT NULL DEFAULT '{}';

ALTER TABLE chunks
    ADD COLUMN chapter TEXT,
    ADD COLUMN article TEXT,
    ADD COLUMN clauses JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN heading TEXT NOT NULL DEFAULT '',
    ADD COLUMN part_index INTEGER NOT NULL DEFAULT 0 CHECK (part_index >= 0),
    ADD COLUMN extraction_methods JSONB NOT NULL DEFAULT '["pymupdf_text"]',
    ADD COLUMN quality_flags JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN source_spans JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN quality_status TEXT NOT NULL DEFAULT 'approved'
        CHECK (quality_status IN ('approved', 'review_required'));

CREATE INDEX chunks_article_idx ON chunks(document_id, article);
COMMENT ON COLUMN chunks.source_spans IS
    'Page/extraction/review provenance for body text and repeated heading context.';
COMMENT ON COLUMN documents.coverage_status IS
    'Partial documents exclude known untrusted pages; an amendment must have full coverage to satisfy a base companion gate.';
