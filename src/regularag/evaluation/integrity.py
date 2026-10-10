from hashlib import sha256
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from regularag.evaluation.dataset import (
    artifact_hash,
    canonical_hash,
    fetch_chunks,
    verify_answer_filters,
    verify_freeze,
    verify_spans,
)
from regularag.ingestion.manifest import load_manifest


def corpus_snapshot(settings):
    with psycopg.connect(str(settings.database_url), row_factory=dict_row) as connection:
        documents = connection.execute("""SELECT document_id,document_number,source_sha256,
            ingestion_status,retrieval_status,coverage_status,excluded_pdf_pages,domain,
            document_type,applies_to,cohort_from,cohort_to,effective_from_date::text,
            effective_to_date::text,legal_status,metadata FROM documents ORDER BY document_id
            """).fetchall()
        chunks = connection.execute("""SELECT chunk_id,document_id,content_sha256,source_pdf_pages,
            article,clauses,quality_status,embedding_model,embedding_revision,embedding_fingerprint
            FROM chunks ORDER BY chunk_id""").fetchall()
    return {"documents": documents, "chunks": chunks}


def verify_live_dataset(directory, settings, config):
    """Read-only pre/post-flight, including held-out integrity but never held-out inference."""
    cases, evidence, lock = verify_freeze(directory)
    snapshot = corpus_snapshot(settings)
    if canonical_hash(snapshot) != lock["corpus_sha256"]:
        raise ValueError("Frozen corpus metadata/model/quality binding drifted")
    if any(artifact_hash(Path(path)) != digest for path, digest in lock["exposure_files"].items()):
        raise ValueError("Frozen development exposure registry drifted")
    manifest = load_manifest(settings.source_manifest_path)
    if set(manifest) != set(config.retrieval.eligible_document_ids):
        raise ValueError("Eligible corpus differs from the frozen source manifest")
    for document in manifest.values():
        if artifact_hash(Path(document["local_path"])) != document["sha256"]:
            raise ValueError("Actual source PDF byte/hash drifted")
    chunks = fetch_chunks(settings, config, {row["chunk_id"] for row in snapshot["chunks"]})
    if any(
        sha256(row["text"].encode()).hexdigest() != row["content_sha256"] for row in chunks.values()
    ):
        raise ValueError("Published source content hash drifted")
    verify_spans(evidence, chunks)
    verify_answer_filters(settings, config, cases, evidence)
    return cases, evidence, chunks, lock
