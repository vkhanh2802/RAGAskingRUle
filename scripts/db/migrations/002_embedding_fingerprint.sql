ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding_fingerprint CHAR(64);

COMMENT ON COLUMN chunks.embedding_fingerprint IS
    'SHA-256 of embedding model/revision, prefixes, token window and pooling configuration. '
    'Legacy NULL rows are excluded from retrieval until reindexed.';
