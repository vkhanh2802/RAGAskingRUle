-- Dates are accepted only with explicit source evidence; academic years are not dates.
CREATE FUNCTION regularag_evidence_date(value TEXT, evidence TEXT) RETURNS DATE
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF coalesce(trim(evidence), '') = '' OR value IS NULL
       OR value !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN
        RETURN NULL;
    END IF;
    BEGIN
        RETURN value::date;
    EXCEPTION WHEN datetime_field_overflow OR invalid_datetime_format THEN
        RETURN NULL;
    END;
END;
$$;

CREATE FUNCTION regularag_evidence_cohort(value TEXT, evidence TEXT) RETURNS INTEGER
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF coalesce(trim(evidence), '') = '' OR value IS NULL
       OR value !~ '^[0-9]{4}$' THEN
        RETURN NULL;
    END IF;
    RETURN CASE WHEN value::integer BETWEEN 1980 AND 2100 THEN value::integer ELSE NULL END;
END;
$$;

ALTER TABLE documents
    ADD COLUMN domain TEXT NOT NULL DEFAULT '',
    ADD COLUMN document_type TEXT NOT NULL DEFAULT '',
    ADD COLUMN applies_to TEXT NOT NULL DEFAULT '',
    ADD COLUMN effective_from_date DATE,
    ADD COLUMN effective_to_date DATE,
    ADD COLUMN cohort_from INTEGER,
    ADD COLUMN cohort_to INTEGER;

CREATE FUNCTION regularag_document_scope_update() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    NEW.domain := coalesce(NEW.metadata->>'domain', '');
    NEW.document_type := coalesce(NEW.metadata->>'document_type', '');
    NEW.applies_to := coalesce(NEW.metadata->>'applies_to', '');
    NEW.effective_from_date := regularag_evidence_date(
        NEW.metadata->>'effective_from', NEW.metadata->>'effective_evidence');
    NEW.effective_to_date := regularag_evidence_date(
        NEW.metadata->>'effective_to', NEW.metadata->>'effective_to_evidence');
    NEW.cohort_from := regularag_evidence_cohort(
        NEW.metadata->>'cohort_from', NEW.metadata->>'cohort_evidence');
    NEW.cohort_to := regularag_evidence_cohort(
        NEW.metadata->>'cohort_to', NEW.metadata->>'cohort_evidence');
    IF NEW.cohort_from > NEW.cohort_to THEN
        NEW.cohort_from := NULL;
        NEW.cohort_to := NULL;
    END IF;
    IF NEW.effective_from_date > NEW.effective_to_date THEN
        NEW.effective_from_date := NULL;
        NEW.effective_to_date := NULL;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER documents_scope_update
BEFORE INSERT OR UPDATE OF metadata ON documents
FOR EACH ROW EXECUTE FUNCTION regularag_document_scope_update();

UPDATE documents SET metadata = metadata;
CREATE INDEX documents_scope_idx ON documents (domain, document_type, applies_to);
CREATE INDEX documents_effective_from_idx ON documents (effective_from_date);

COMMENT ON COLUMN documents.effective_from_date IS
    'Source-declared start with evidence; not certification of current legal status.';
COMMENT ON COLUMN documents.cohort_from IS
    'Explicit evidence-bound cohort range; missing bounds mean unknown, not all cohorts.';
