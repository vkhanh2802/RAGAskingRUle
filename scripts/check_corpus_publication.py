import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from regularag.core.config import get_settings
from regularag.evaluation.development import fetch_evidence, load_questions, verify_evidence
from regularag.generation.guards import document_instruction
from regularag.ingestion.manifest import load_manifest
from regularag.retrieval.config import RagBaselineConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify whole-corpus publication, hashes and gold drift."
    )
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed/m2-publication"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/manifests/m2_publication_snapshot.json")
    )
    args = parser.parse_args()
    settings = get_settings()
    config = RagBaselineConfig.from_path(settings.rag_config_path)
    manifest = load_manifest(Path("data/manifests/documents.csv"))
    if set(config.retrieval.eligible_document_ids) != set(manifest):
        raise ValueError("M2 requires the reviewed corpus to match the eligible manifest")
    expected_chunks = {}
    page_status = Counter()
    for document_id, source in manifest.items():
        if sha256(Path(source["local_path"]).read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Actual source PDF differs from its reviewed hash")
        directory = args.input_dir / document_id
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        if not metadata["quality"]["publication_ready"]:
            raise ValueError("A corpus document still needs quality review")
        pages = [
            json.loads(line)
            for line in (directory / "pages.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        page_status.update(page["review_status"] for page in pages)
        for line in (directory / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
            chunk = json.loads(line)
            expected_chunks[chunk["chunk_id"]] = chunk["content_sha256"]
    with psycopg.connect(str(settings.database_url), row_factory=dict_row) as connection:
        documents = connection.execute("""
            SELECT document_id, document_number, ingestion_status, retrieval_status,
                   coverage_status, excluded_pdf_pages, indexed_chunk_count,
                   domain, applies_to, effective_from_date::text, legal_status,
                   COALESCE(metadata->'_ingestion_quality'->'omitted_layout_pdf_pages', '[]')
                       AS omitted_layout_pdf_pages,
                   (SELECT outcome FROM ingestion_runs r WHERE r.run_id=d.last_ingestion_run_id)
                       AS latest_outcome
            FROM documents d ORDER BY document_id
        """).fetchall()
        chunks = connection.execute("""
            SELECT chunk_id, text, content_sha256, embedding_fingerprint, quality_status,
                   search_vector <> ''::tsvector AS fts_populated FROM chunks ORDER BY chunk_id
        """).fetchall()
        unfinished = connection.execute(
            "SELECT count(*) AS n FROM ingestion_runs WHERE status IN ('pending','processing')"
        ).fetchone()["n"]
    if set(row["document_id"] for row in documents) != set(manifest) or any(
        row["ingestion_status"] != "ready" or row["retrieval_status"] != "ready"
        for row in documents
    ):
        raise ValueError("Not every registry document is publication-ready")
    actual = {row["chunk_id"]: row["content_sha256"] for row in chunks}
    if (
        len(actual) != len(chunks)
        or actual != expected_chunks
        or unfinished
        or page_status["pending"]
    ):
        raise ValueError("Corpus count/hash/unfinished-run check failed")
    if any(
        sha256(row["text"].encode("utf-8")).hexdigest() != row["content_sha256"]
        or row["embedding_fingerprint"] != config.embedding.fingerprint
        or row["quality_status"] != "approved"
        or not row["fts_populated"]
        for row in chunks
    ):
        raise ValueError("Published content/model/quality/FTS check failed")
    if any(document_instruction(row["text"]) for row in chunks):
        raise ValueError("A published chunk contains a declared assistant-control instruction")
    binding = json.loads(
        Path("data/manifests/development_evidence.json").read_text(encoding="utf-8")
    )
    questions = load_questions(Path("data/manifests/development_questions.csv"))
    verify_evidence(binding["chunks"], fetch_evidence(settings, config, questions))
    payload = {
        "verified_at": datetime.now(UTC).isoformat(),
        "documents_ready": len(documents),
        "chunks": len(chunks),
        "unique_chunk_ids": len(actual),
        "fts_populated": len(chunks),
        "unfinished_runs": unfinished,
        "page_review_status": dict(page_status),
        "latest_outcomes": dict(Counter(row["latest_outcome"] for row in documents)),
        "development_gold_chunks_unchanged": len(binding["chunks"]),
        "instruction_guard_rejections": 0,
        "documents": documents,
        "conditions": "Assistant-reviewed supported scope; partial layouts excluded; "
        "ready is technical status and does not establish current legal force",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in payload.items() if key != "documents"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
