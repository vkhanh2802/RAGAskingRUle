import csv
import json
import os
from hashlib import sha256
from pathlib import Path

import numpy as np
import psycopg
import pytest

from regularag.db.migrations import apply_migrations
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.indexer import index_baseline
from regularag.retrieval.keyword import KeywordRepository
from regularag.retrieval.repository import PgVectorRepository

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("REGULARAG_RUN_DB_TESTS") != "1",
        reason="Set REGULARAG_RUN_DB_TESTS=1 to run isolated PostgreSQL tests",
    ),
]

ROOT = Path(__file__).resolve().parents[2]


class SyntheticEmbedder:
    dimension = 384

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        vectors = []
        for text in texts:
            index = int(text.rsplit(" ", 1)[1])
            vector = np.zeros(384, dtype=np.float32)
            vector[index] = 1
            vectors.append(vector)
        return vectors


@pytest.fixture
def artifacts(tmp_path: Path):
    config = RagBaselineConfig.from_path(ROOT / "configs/rag/baseline.json")
    config.reranker.enabled = False
    config.freshness.enabled = False
    config.behaviour.enabled = False
    config.generation.response_policy = "verified_quotes"
    config.retrieval.eligible_document_ids = config.retrieval.eligible_document_ids[:3]
    rows = []
    processed = tmp_path / "processed"
    for index, document_id in enumerate(config.retrieval.eligible_document_ids):
        row = {
            "document_id": document_id,
            "document_number": f"test-{index}",
            "title": f"Test document {index}",
            "source_url": f"https://example.test/{index}",
            "sha256": str(index) * 64,
            "legal_status": "unknown",
            "document_role": "standalone",
            "related_document_number": "",
        }
        rows.append(row)
        text = f"Evidence document {index}"
        chunk = {
            "chunk_id": f"{document_id}:chunk:0000",
            "document_id": document_id,
            "chunk_index": 0,
            "text": text,
            "token_count": 3,
            "pdf_page_start": 1,
            "pdf_page_end": 1,
            "printed_page_start": None,
            "printed_page_end": None,
            "source_pdf_pages": [1],
            "source_printed_pages": [],
            "content_sha256": sha256(text.encode("utf-8")).hexdigest(),
        }
        document_directory = processed / document_id
        document_directory.mkdir(parents=True)
        (document_directory / "chunks.jsonl").write_text(json.dumps(chunk) + "\n", encoding="utf-8")
        (document_directory / "metadata.json").write_text(
            json.dumps({"document": row, "config": {"pipeline_version": "test-v1"}}),
            encoding="utf-8",
        )
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return config, manifest, processed


def test_index_twice_keeps_counts_and_search_returns_nearest_chunk(database_settings, artifacts):
    config, manifest, processed = artifacts
    for _ in range(2):
        index_baseline(database_settings, config, SyntheticEmbedder(), manifest, processed)

    with psycopg.connect(str(database_settings.database_url)) as connection:
        assert connection.execute("SELECT count(*) FROM documents").fetchone()[0] == 3
        assert connection.execute("SELECT count(*) FROM chunks").fetchone()[0] == 3
    query = np.zeros(384, dtype=np.float32)
    query[0] = 1
    hits = PgVectorRepository(database_settings, config).search(query, 3)

    assert hits[0].document_id == config.retrieval.eligible_document_ids[0]
    assert hits[0].score == pytest.approx(1)
    assert hits[0].pdf_page_start == 1


def test_search_excludes_blocked_revision_mismatch_and_unapproved_documents(
    database_settings, artifacts
):
    config, manifest, processed = artifacts
    index_baseline(database_settings, config, SyntheticEmbedder(), manifest, processed)
    ids = config.retrieval.eligible_document_ids
    with psycopg.connect(str(database_settings.database_url)) as connection:
        connection.execute(
            "UPDATE documents SET retrieval_status = 'blocked' WHERE document_id = %s", (ids[0],)
        )
        connection.execute(
            "UPDATE chunks SET embedding_revision = %s WHERE document_id = %s", ("f" * 40, ids[1])
        )
    config.retrieval.eligible_document_ids = ids[:2]
    query = np.ones(384, dtype=np.float32)

    assert PgVectorRepository(database_settings, config).search(query, 5) == []


def test_corrupt_processed_text_cannot_replace_an_existing_index(database_settings, artifacts):
    config, manifest, processed = artifacts
    index_baseline(database_settings, config, SyntheticEmbedder(), manifest, processed)
    path = processed / config.retrieval.eligible_document_ids[0] / "chunks.jsonl"
    chunk = json.loads(path.read_text(encoding="utf-8"))
    chunk["text"] = "corrupt replacement without updating hash"
    path.write_text(json.dumps(chunk) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        index_baseline(database_settings, config, SyntheticEmbedder(), manifest, processed)
    with psycopg.connect(str(database_settings.database_url)) as connection:
        assert connection.execute("SELECT count(*) FROM chunks").fetchone()[0] == 3


def test_migrations_are_idempotent(database_settings):
    result = apply_migrations(database_settings, ROOT / "scripts/db/migrations")

    assert result.applied == ()
    assert result.skipped == (
        "001_vector_baseline",
        "002_embedding_fingerprint",
        "003_ingestion_lifecycle",
        "004_structure_quality",
        "005_keyword_search",
        "006_metadata_filters",
    )


def test_review_required_artifacts_cannot_be_published(database_settings, artifacts):
    config, manifest, processed = artifacts
    document_id = config.retrieval.eligible_document_ids[0]
    metadata_path = processed / document_id / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["quality"] = {"publication_ready": False, "review_required_pdf_pages": [1]}
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ValueError, match="Unreviewed"):
        index_baseline(database_settings, config, SyntheticEmbedder(), manifest, processed)
    with psycopg.connect(str(database_settings.database_url)) as connection:
        state = connection.execute(
            "SELECT ingestion_status,retrieval_status FROM documents WHERE document_id=%s",
            (document_id,),
        ).fetchone()
    assert state == ("failed", "blocked")


def test_structure_and_partial_coverage_survive_an_unchanged_processed_run(
    database_settings, artifacts
):
    config, manifest, processed = artifacts
    document_id = config.retrieval.eligible_document_ids[0]
    path = processed / document_id
    chunk = json.loads((path / "chunks.jsonl").read_text(encoding="utf-8"))
    chunk.update(
        {"chapter": "I", "article": "14", "clauses": ["1"], "extraction_methods": ["tesseract_ocr"]}
    )
    (path / "chunks.jsonl").write_text(json.dumps(chunk) + "\n", encoding="utf-8")
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    metadata["quality"] = {
        "publication_ready": True,
        "coverage_status": "partial",
        "excluded_pdf_pages": [2],
    }
    (path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    for _ in range(2):
        index_baseline(database_settings, config, SyntheticEmbedder(), manifest, processed)
    query = np.zeros(384, dtype=np.float32)
    query[0] = 1
    hit = PgVectorRepository(database_settings, config).search(query, 1)[0]

    assert hit.article == "14" and hit.chapter == "I"
    assert hit.clauses == ["1"]
    assert hit.coverage_status == "partial" and hit.excluded_pdf_pages == [2]
    assert hit.extraction_methods == ["tesseract_ocr"]


def _seed_keyword_documents(settings, artifacts):
    config, manifest, processed = artifacts
    index_baseline(settings, config, SyntheticEmbedder(), manifest, processed)
    ids = config.retrieval.eligible_document_ids
    text = "Điều 1. Học kỳ hè tối đa 12 tín chỉ. Khoản 1 Điều 14 về đăng ký học phần."
    with psycopg.connect(str(settings.database_url)) as connection:
        connection.execute(
            "UPDATE documents SET document_number=%s,title=%s WHERE document_id=%s",
            ("1393/QĐ-ĐHCNTT", "Quyết định cập nhật quy chế đào tạo", ids[0]),
        )
        connection.execute(
            "UPDATE chunks SET text=%s,content_sha256=%s,article='1' WHERE document_id=%s",
            (text, sha256(text.encode("utf-8")).hexdigest(), ids[0]),
        )
    return config, ids


def test_keyword_accent_fold_document_number_and_article_references(database_settings, artifacts):
    config, ids = _seed_keyword_documents(database_settings, artifacts)
    repository = KeywordRepository(database_settings, config)

    accented = repository.search("1393/QĐ-ĐHCNTT Điều 1 học kỳ hè", 5)
    plain = repository.search("1393/QD-DHCNTT Dieu 1 hoc ky he", 5)

    assert [hit.chunk_id for hit in accented] == [hit.chunk_id for hit in plain]
    assert accented[0].document_id == ids[0]
    assert accented[0].score_kind == "ts_rank_cd"
    assert accented[0].keyword_rank == 1 and accented[0].keyword_score > 0
    assert repository.search("Quyết định 1393 Điều 14", 5)[0].document_id == ids[0]
    assert repository.search("Quyết định 1393 Điều 99", 5) == []


def test_dense_document_reference_gate_applies_before_candidate_limit(database_settings, artifacts):
    config, ids = _seed_keyword_documents(database_settings, artifacts)
    query = np.zeros(384, dtype=np.float32)
    query[1] = 1  # Globally nearest source is unrelated to the requested document number.
    repository = PgVectorRepository(database_settings, config)
    assert repository.search(query, 1)[0].document_id == ids[1]
    hits = repository.search(query, 1, document_codes=("1393",))
    assert len(hits) == 1 and hits[0].document_id == ids[0]


@pytest.mark.parametrize(
    "gate",
    [
        "pending",
        "processing",
        "failed",
        "blocked",
        "quality",
        "revision",
        "fingerprint",
        "allowlist",
    ],
)
def test_keyword_uses_the_same_publication_quality_model_gates(database_settings, artifacts, gate):
    config, ids = _seed_keyword_documents(database_settings, artifacts)
    with psycopg.connect(str(database_settings.database_url)) as connection:
        if gate in ("pending", "processing", "failed"):
            connection.execute(
                "UPDATE documents SET ingestion_status=%s WHERE document_id=%s", (gate, ids[0])
            )
        elif gate == "blocked":
            connection.execute(
                "UPDATE documents SET retrieval_status='blocked' WHERE document_id=%s", (ids[0],)
            )
        elif gate == "quality":
            connection.execute(
                "UPDATE chunks SET quality_status='review_required' WHERE document_id=%s", (ids[0],)
            )
        elif gate == "revision":
            connection.execute(
                "UPDATE chunks SET embedding_revision=%s WHERE document_id=%s", ("f" * 40, ids[0])
            )
        elif gate == "fingerprint":
            connection.execute(
                "UPDATE chunks SET embedding_fingerprint=%s WHERE document_id=%s",
                ("f" * 64, ids[0]),
            )
        else:
            config.retrieval.eligible_document_ids = ids[1:]

    assert KeywordRepository(database_settings, config).search("Quyết định 1393 học kỳ hè", 5) == []


def test_keyword_index_tracks_content_metadata_updates_and_deletion(database_settings, artifacts):
    config, ids = _seed_keyword_documents(database_settings, artifacts)
    repository = KeywordRepository(database_settings, config)
    with psycopg.connect(str(database_settings.database_url)) as connection:
        connection.execute("UPDATE chunks SET text='NewUniqueTerm' WHERE document_id=%s", (ids[0],))

    assert repository.search("NewUniqueTerm", 5)[0].document_id == ids[0]
    assert repository.search("học kỳ hè", 5) == []
    with psycopg.connect(str(database_settings.database_url)) as connection:
        connection.execute(
            "UPDATE documents SET title='MetadataOnlyTerm' WHERE document_id=%s", (ids[0],)
        )

    assert repository.search("MetadataOnlyTerm", 5)[0].document_id == ids[0]
    with psycopg.connect(str(database_settings.database_url)) as connection:
        connection.execute("DELETE FROM documents WHERE document_id=%s", (ids[0],))

    assert repository.search("MetadataOnlyTerm", 5) == []
