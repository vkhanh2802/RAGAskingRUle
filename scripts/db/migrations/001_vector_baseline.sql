CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    document_number TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    legal_status TEXT NOT NULL,
    document_role TEXT NOT NULL,
    related_document_number TEXT,
    retrieval_status TEXT NOT NULL CHECK (retrieval_status IN ('ready', 'blocked')),
    metadata JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    text TEXT NOT NULL,
    token_count INTEGER NOT NULL CHECK (token_count > 0),
    pdf_page_start INTEGER NOT NULL CHECK (pdf_page_start > 0),
    pdf_page_end INTEGER NOT NULL CHECK (pdf_page_end >= pdf_page_start),
    printed_page_start INTEGER,
    printed_page_end INTEGER,
    source_pdf_pages INTEGER[] NOT NULL,
    source_printed_pages INTEGER[] NOT NULL,
    content_sha256 CHAR(64) NOT NULL,
    chunking_pipeline_version TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_revision CHAR(40) NOT NULL,
    embedding VECTOR(384) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_id, chunk_index, chunking_pipeline_version, embedding_model, embedding_revision)
);

CREATE INDEX IF NOT EXISTS chunks_document_id_idx ON chunks(document_id);
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
