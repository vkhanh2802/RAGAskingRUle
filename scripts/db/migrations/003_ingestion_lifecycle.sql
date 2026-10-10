ALTER TABLE documents
    ADD COLUMN ingestion_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (ingestion_status IN ('pending', 'processing', 'ready', 'failed')),
    ADD COLUMN ingestion_fingerprint CHAR(64),
    ADD COLUMN ingestion_pipeline_version TEXT,
    ADD COLUMN indexed_chunk_count INTEGER NOT NULL DEFAULT 0 CHECK (indexed_chunk_count >= 0),
    ADD COLUMN last_error JSONB,
    ADD COLUMN last_ingestion_run_id UUID;

-- Preserve the already verified M1 index during this migration.
UPDATE documents AS d
SET ingestion_status = CASE WHEN d.retrieval_status = 'ready' THEN 'ready' ELSE 'pending' END,
    indexed_chunk_count = (SELECT COUNT(*) FROM chunks AS c WHERE c.document_id = d.document_id);

CREATE TABLE ingestion_runs (
    run_id UUID PRIMARY KEY,
    document_id TEXT REFERENCES documents(document_id) ON DELETE SET NULL,
    document_id_snapshot TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('ingest', 'delete')),
    source_path TEXT,
    requested_source_sha256 CHAR(64),
    actual_source_sha256 CHAR(64),
    pipeline_version TEXT NOT NULL,
    pipeline_config JSONB NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_revision CHAR(40) NOT NULL,
    embedding_fingerprint CHAR(64) NOT NULL,
    ingestion_fingerprint CHAR(64),
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
    outcome TEXT CHECK (outcome IN ('ingested', 'unchanged', 'failed', 'deleted', 'not_found')),
    chunk_count INTEGER NOT NULL DEFAULT 0 CHECK (chunk_count >= 0),
    artifact_path TEXT,
    error_code TEXT,
    error_message TEXT,
    queued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    CHECK ((status IN ('ready', 'failed')) = (finished_at IS NOT NULL))
);

ALTER TABLE documents ADD CONSTRAINT documents_last_ingestion_run_fk
    FOREIGN KEY (last_ingestion_run_id) REFERENCES ingestion_runs(run_id) ON DELETE SET NULL;
ALTER TABLE chunks ADD COLUMN ingestion_run_id UUID
    REFERENCES ingestion_runs(run_id) ON DELETE SET NULL;

CREATE INDEX ingestion_runs_document_history_idx
    ON ingestion_runs(document_id_snapshot, queued_at DESC);
CREATE INDEX ingestion_runs_status_idx ON ingestion_runs(status);
CREATE INDEX documents_ingestion_status_idx ON documents(ingestion_status);

COMMENT ON COLUMN documents.retrieval_status IS
    'Publication gate; retrieval also requires ingestion_status=ready and the current model fingerprint.';
COMMENT ON COLUMN ingestion_runs.document_id_snapshot IS
    'Stable identity for audit history, retained after deletion of the document and its chunks.';
