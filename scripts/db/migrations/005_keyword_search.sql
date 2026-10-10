CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;

CREATE FUNCTION regularag_normalize(value TEXT) RETURNS TEXT
LANGUAGE SQL STABLE STRICT PARALLEL SAFE AS $$
    SELECT lower(public.unaccent('public.unaccent'::regdictionary, value));
$$;

ALTER TABLE chunks
    ADD COLUMN search_text TEXT NOT NULL DEFAULT '',
    ADD COLUMN search_vector TSVECTOR NOT NULL DEFAULT ''::tsvector;

CREATE FUNCTION regularag_chunk_search_update() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE
    metadata_text TEXT;
    structure_text TEXT;
BEGIN
    SELECT d.document_number || ' ' || d.title INTO metadata_text
    FROM documents d WHERE d.document_id = NEW.document_id;
    structure_text := coalesce(NEW.heading, '') || ' ' ||
        CASE WHEN NEW.article IS NULL THEN '' ELSE 'Điều ' || NEW.article END || ' ' ||
        coalesce(NEW.clauses::text, '');
    NEW.search_text := regularag_normalize(
        coalesce(metadata_text, '') || ' ' || structure_text || ' ' || NEW.text
    );
    NEW.search_vector :=
        setweight(to_tsvector('simple', regularag_normalize(coalesce(metadata_text, ''))), 'A') ||
        setweight(to_tsvector('simple', regularag_normalize(structure_text)), 'B') ||
        setweight(to_tsvector('simple', regularag_normalize(NEW.text)), 'C');
    RETURN NEW;
END;
$$;

CREATE TRIGGER chunks_search_update
BEFORE INSERT OR UPDATE OF text, heading, article, clauses, document_id ON chunks
FOR EACH ROW EXECUTE FUNCTION regularag_chunk_search_update();

CREATE FUNCTION regularag_document_search_update() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE chunks SET text = text WHERE document_id = NEW.document_id;
    RETURN NEW;
END;
$$;

CREATE TRIGGER documents_search_update
AFTER UPDATE OF document_number, title ON documents
FOR EACH ROW WHEN (
    OLD.document_number IS DISTINCT FROM NEW.document_number OR
    OLD.title IS DISTINCT FROM NEW.title
) EXECUTE FUNCTION regularag_document_search_update();

UPDATE chunks SET text = text;
CREATE INDEX chunks_search_vector_gin_idx ON chunks USING gin(search_vector);

COMMENT ON COLUMN chunks.search_vector IS
    'Weighted simple/unaccent PostgreSQL full-text index; ts_rank_cd is not BM25.';
