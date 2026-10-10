import csv
import json
import os
from hashlib import sha256
from pathlib import Path

import numpy as np
import psycopg
import pymupdf
import pytest

from regularag.ingestion.cli import ingest_target
from regularag.ingestion.lifecycle import IngestionLifecycle
from regularag.ingestion.pipeline import BaselineIngestionConfig
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.repository import PgVectorRepository
from tests.unit.ingestion.fakes import WordTokenizer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("REGULARAG_RUN_DB_TESTS") != "1",
        reason="Set REGULARAG_RUN_DB_TESTS=1 to run isolated PostgreSQL tests",
    ),
]
ROOT = Path(__file__).resolve().parents[2]


class CountingEmbedder:
    dimension = 384

    def __init__(self) -> None:
        self.calls = 0
        self.callback = None

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        self.calls += 1
        if self.callback:
            self.callback()
        vectors = []
        for text in texts:
            vector = np.zeros(384, dtype=np.float32)
            vector[1 if "UPDATED" in text else 0] = 1
            vectors.append(vector)
        return vectors


def _query(index: int = 0) -> np.ndarray:
    vector = np.zeros(384, dtype=np.float32)
    vector[index] = 1
    return vector


def _pdf(path: Path, marker: str = "ORIGINAL") -> str:
    with pymupdf.open() as document:
        page = document.new_page()
        text = "\n".join(
            f"{marker} evidence line {index} contains a condition and its exception."
            for index in range(8)
        )
        page.insert_text((72, 72), text)
        document.save(path)
    return sha256(path.read_bytes()).hexdigest()


def _document(document_id: str, number: str, source: Path, source_hash: str) -> dict[str, str]:
    return {
        "document_id": document_id,
        "document_number": number,
        "title": f"Document {number}",
        "source_url": f"https://example.test/{number}",
        "local_path": str(source),
        "sha256": source_hash,
        "legal_status": "unknown",
        "document_role": "standalone",
        "related_document_number": "",
        "pdf_type": "text",
    }


@pytest.fixture
def environment(database_settings, tmp_path: Path):
    config = RagBaselineConfig.from_path(ROOT / "configs/rag/baseline.json")
    chunking = BaselineIngestionConfig.from_path(ROOT / "configs/ingestion/baseline.json")
    embedder = CountingEmbedder()
    lifecycle = IngestionLifecycle(database_settings, config, embedder, chunking, WordTokenizer())
    source = tmp_path / "source.pdf"
    document = _document(config.retrieval.eligible_document_ids[0], "test-0", source, _pdf(source))
    return lifecycle, config, embedder, document, source, tmp_path / "output"


def test_raw_ingest_twice_skips_embedding_and_preserves_audited_versions(environment):
    lifecycle, _, embedder, document, source, output = environment
    first = lifecycle.ingest(document, source, input_kind="pdf", output_root=output)
    second = lifecycle.ingest(document, source, input_kind="pdf", output_root=output)

    assert first.outcome == "ingested"
    assert second.outcome == "unchanged"
    assert first.chunk_count == second.chunk_count == 1
    assert embedder.calls == 1
    history = lifecycle.repository.history(document["document_id"])
    assert [run["outcome"] for run in history] == ["ingested", "unchanged"]
    assert all(run["status"] == "ready" for run in history)
    assert all(run["queued_at"] <= run["started_at"] <= run["finished_at"] for run in history)
    assert all(run["actual_source_sha256"] == document["sha256"] for run in history)
    assert all(
        run["embedding_revision"] == lifecycle.config.embedding.model_revision for run in history
    )
    assert all(
        run["pipeline_config"]["chunking"]["pipeline_version"] == "baseline-v1" for run in history
    )


def test_directory_batch_continues_after_a_registered_corrupt_pdf(
    database_settings, tmp_path: Path
):
    config = RagBaselineConfig.from_path(ROOT / "configs/rag/baseline.json")
    config.retrieval.eligible_document_ids = config.retrieval.eligible_document_ids[:3]
    chunking = BaselineIngestionConfig.from_path(ROOT / "configs/ingestion/baseline.json")
    lifecycle = IngestionLifecycle(
        database_settings, config, CountingEmbedder(), chunking, WordTokenizer()
    )
    sources = [tmp_path / "a.pdf", tmp_path / "b.pdf", tmp_path / "c.PDF"]
    hashes = [_pdf(sources[0])]
    sources[1].write_bytes(b"This is a corrupt PDF, not a text-layer document.")
    hashes.append(sha256(sources[1].read_bytes()).hexdigest())
    hashes.append(_pdf(sources[2]))
    documents = {
        document_id: _document(document_id, f"test-{index}", sources[index], hashes[index])
        for index, document_id in enumerate(config.retrieval.eligible_document_ids)
    }

    results = ingest_target(lifecycle, documents, tmp_path, tmp_path, tmp_path / "output")

    assert [result.status for result in results] == ["ready", "failed", "ready"]
    assert results[1].error_code == "processing_error"
    states = lifecycle.repository.status()
    assert sum(row["ingestion_status"] == "ready" for row in states) == 2
    assert len(lifecycle.repository.history()) == 3
    hits = PgVectorRepository(database_settings, config).search(_query(), 5)
    assert {hit.document_id for hit in hits} == {results[0].document_id, results[2].document_id}


def test_update_failure_and_retry_hide_stale_chunks_then_publish_new_content(
    environment, database_settings
):
    lifecycle, config, _, document, source, output = environment
    lifecycle.ingest(document, source, input_kind="pdf", output_root=output)
    replacement = source.parent / "replacement.pdf"
    updated = {**document, "sha256": _pdf(replacement, "UPDATED")}
    result = lifecycle.ingest(updated, replacement, input_kind="pdf", output_root=output)
    assert result.outcome == "ingested"
    hits = PgVectorRepository(database_settings, config).search(_query(1), 1)
    assert "UPDATED" in hits[0].text
    assert "ORIGINAL" not in hits[0].text

    replacement.write_bytes(b"broken update")
    broken = {**updated, "sha256": sha256(replacement.read_bytes()).hexdigest()}
    failure = lifecycle.ingest(broken, replacement, input_kind="pdf", output_root=output)
    assert failure.status == "failed"
    assert PgVectorRepository(database_settings, config).search(_query(1), 5) == []
    with psycopg.connect(str(database_settings.database_url)) as connection:
        assert "UPDATED" in connection.execute("SELECT text FROM chunks").fetchone()[0]

    recovered = {**updated, "sha256": _pdf(replacement, "UPDATED_RECOVERED")}
    retry = lifecycle.ingest(recovered, replacement, input_kind="pdf", output_root=output)
    assert retry.status == "ready"
    assert (
        "UPDATED_RECOVERED"
        in PgVectorRepository(database_settings, config).search(_query(1), 1)[0].text
    )
    assert [run["status"] for run in lifecycle.repository.history()] == [
        "ready",
        "ready",
        "failed",
        "ready",
    ]


def test_delete_cascades_chunks_and_retains_history(environment, database_settings):
    lifecycle, config, _, document, source, output = environment
    lifecycle.ingest(document, source, input_kind="pdf", output_root=output)

    deleted = lifecycle.delete(document["document_id"])

    assert deleted.deleted and deleted.chunks_deleted == 1
    assert lifecycle.repository.status(document["document_id"]) == []
    assert PgVectorRepository(database_settings, config).search(_query(), 5) == []
    history = lifecycle.repository.history(document["document_id"])
    assert [run["operation"] for run in history] == ["ingest", "delete"]
    assert all(run["document_id"] is None for run in history)
    assert lifecycle.delete(document["document_id"]).deleted is False


@pytest.mark.parametrize("state", ["pending", "processing", "failed"])
def test_retrieval_requires_ingestion_ready_even_if_publication_flag_is_ready(
    environment, database_settings, state: str
):
    lifecycle, config, _, document, source, output = environment
    lifecycle.ingest(document, source, input_kind="pdf", output_root=output)
    with psycopg.connect(str(database_settings.database_url)) as connection:
        connection.execute("UPDATE documents SET ingestion_status = %s", (state,))

    assert PgVectorRepository(database_settings, config).search(_query(), 5) == []


def test_document_is_processing_and_invisible_while_embedding_runs(environment, database_settings):
    lifecycle, config, embedder, document, source, output = environment

    def observe() -> None:
        row = lifecycle.repository.status(document["document_id"])[0]
        assert row["ingestion_status"] == "processing"
        assert PgVectorRepository(database_settings, config).search(_query(), 5) == []

    embedder.callback = observe
    assert (
        lifecycle.ingest(document, source, input_kind="pdf", output_root=output).status == "ready"
    )


def test_source_hash_mismatch_is_audited_and_retry_succeeds(environment):
    lifecycle, _, _, document, source, output = environment
    wrong_hash = {**document, "sha256": "f" * 64}

    rejected = lifecycle.ingest(wrong_hash, source, input_kind="pdf", output_root=output)

    assert rejected.error_code == "source_hash_mismatch"
    run = lifecycle.repository.history(document["document_id"])[0]
    assert run["requested_source_sha256"] == "f" * 64
    assert run["actual_source_sha256"] == document["sha256"]
    assert (
        lifecycle.ingest(document, source, input_kind="pdf", output_root=output).status == "ready"
    )


def test_changed_embedding_revision_invalidates_the_unchanged_shortcut(environment):
    lifecycle, _, embedder, document, source, output = environment
    lifecycle.ingest(document, source, input_kind="pdf", output_root=output)
    lifecycle.config.embedding.model_revision = "f" * 40

    result = lifecycle.ingest(document, source, input_kind="pdf", output_root=output)

    assert result.outcome == "ingested"
    assert embedder.calls == 2
    assert (
        lifecycle.repository.history(document["document_id"])[-1]["embedding_revision"] == "f" * 40
    )


def test_busy_document_rejects_second_writer_without_changing_ready_state(environment):
    lifecycle, _, embedder, document, source, output = environment
    lifecycle.ingest(document, source, input_kind="pdf", output_root=output)
    with lifecycle.repository.session() as owner:
        assert lifecycle.repository.lock(owner, document["document_id"])
        try:
            result = lifecycle.ingest(document, source, input_kind="pdf", output_root=output)
        finally:
            lifecycle.repository.unlock(owner, document["document_id"])

    assert result.error_code == "document_busy"
    assert embedder.calls == 1
    assert lifecycle.repository.status(document["document_id"])[0]["ingestion_status"] == "ready"


def test_lost_worker_is_recorded_as_interrupted_on_retry(environment, database_settings):
    lifecycle, _, _, document, source, output = environment
    lifecycle.ingest(document, source, input_kind="pdf", output_root=output)
    with psycopg.connect(str(database_settings.database_url)) as connection:
        connection.execute(
            "UPDATE documents SET ingestion_status = 'processing', retrieval_status = 'blocked'"
        )
        connection.execute(
            "UPDATE ingestion_runs SET status = 'processing', outcome = NULL, finished_at = NULL"
        )

    result = lifecycle.ingest(document, source, input_kind="pdf", output_root=output)

    assert result.status == "ready"
    history = lifecycle.repository.history(document["document_id"])
    assert history[0]["status"] == "failed"
    assert history[0]["error_code"] == "interrupted"
    assert history[1]["status"] == "ready"


def test_unknown_source_is_audited_without_creating_a_ready_document(environment):
    lifecycle, _, embedder, _, source, _ = environment

    result = lifecycle.reject_unregistered(source)

    assert result.error_code == "source_not_registered"
    assert lifecycle.repository.status() == []
    assert lifecycle.repository.history()[0]["document_id"] is None
    assert embedder.calls == 0


def test_publication_constraint_failure_rolls_back_chunk_replacement(
    environment, database_settings
):
    lifecycle, config, _, document, source, output = environment
    lifecycle.ingest(document, source, input_kind="pdf", output_root=output)
    other_path = source.parent / "other.pdf"
    other = _document(
        config.retrieval.eligible_document_ids[1], "test-1", other_path, _pdf(other_path)
    )
    lifecycle.ingest(other, other_path, input_kind="pdf", output_root=output)
    replacement = source.parent / "updated.pdf"
    invalid_metadata = {
        **document,
        "document_number": other["document_number"],
        "sha256": _pdf(replacement, "UPDATED"),
    }

    result = lifecycle.ingest(invalid_metadata, replacement, input_kind="pdf", output_root=output)

    assert result.error_code == "database_write_error"
    with psycopg.connect(str(database_settings.database_url)) as connection:
        text = connection.execute(
            "SELECT text FROM chunks WHERE document_id = %s", (document["document_id"],)
        ).fetchone()[0]
        assert "ORIGINAL" in text and "UPDATED" not in text
    hits = PgVectorRepository(database_settings, config).search(_query(), 5)
    assert {hit.document_id for hit in hits} == {other["document_id"]}


def test_cli_returns_partial_failure_code_and_writes_report(
    database_settings, tmp_path: Path, monkeypatch, capsys
):
    from regularag.ingestion import cli as cli_module
    from regularag.ingestion import lifecycle as lifecycle_module

    config = RagBaselineConfig.from_path(ROOT / "configs/rag/baseline.json")
    good = tmp_path / "good.pdf"
    bad = tmp_path / "bad.pdf"
    good_hash = _pdf(good)
    bad.write_bytes(b"broken PDF")
    rows = [
        _document(config.retrieval.eligible_document_ids[0], "test-0", good, good_hash),
        _document(
            config.retrieval.eligible_document_ids[1],
            "test-1",
            bad,
            sha256(bad.read_bytes()).hexdigest(),
        ),
    ]
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    monkeypatch.setattr(cli_module, "get_settings", lambda: database_settings)
    monkeypatch.setattr(
        cli_module, "SentenceTransformerEmbedder", lambda config: CountingEmbedder()
    )
    monkeypatch.setattr(
        lifecycle_module, "HuggingFaceTokenizer", lambda model, revision: WordTokenizer()
    )
    report = tmp_path / "report.csv"

    exit_code = cli_module.main(
        [
            "--config",
            str(ROOT / "configs/rag/baseline.json"),
            "--ingestion-config",
            str(ROOT / "configs/ingestion/baseline.json"),
            "ingest",
            str(tmp_path),
            "--manifest",
            str(manifest),
            "--output-dir",
            str(tmp_path / "output"),
            "--report",
            str(report),
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["ready"] == payload["summary"]["failed"] == 1
    with report.open(encoding="utf-8", newline="") as report_file:
        assert {row["status"] for row in csv.DictReader(report_file)} == {"ready", "failed"}


def test_delete_closes_an_abandoned_processing_run(environment, database_settings):
    lifecycle, _, _, document, source, output = environment
    lifecycle.ingest(document, source, input_kind="pdf", output_root=output)
    with psycopg.connect(str(database_settings.database_url)) as connection:
        connection.execute(
            "UPDATE ingestion_runs SET status = 'processing', outcome = NULL, finished_at = NULL"
        )

    assert lifecycle.delete(document["document_id"]).deleted
    history = lifecycle.repository.history(document["document_id"])
    assert history[0]["error_code"] == "interrupted"
    assert history[1]["outcome"] == "deleted"


def test_cli_flushes_completed_report_rows_before_an_interruption(
    database_settings, tmp_path: Path, monkeypatch
):
    from regularag.ingestion import cli as cli_module
    from regularag.ingestion import lifecycle as lifecycle_module

    config = RagBaselineConfig.from_path(ROOT / "configs/rag/baseline.json")
    rows = []
    for index, name in enumerate(("a.pdf", "b.pdf")):
        source = tmp_path / name
        rows.append(
            _document(
                config.retrieval.eligible_document_ids[index],
                f"test-{index}",
                source,
                _pdf(source),
            )
        )
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    embedder = CountingEmbedder()

    def interrupt_second_document() -> None:
        if embedder.calls == 2:
            raise KeyboardInterrupt

    embedder.callback = interrupt_second_document
    monkeypatch.setattr(cli_module, "get_settings", lambda: database_settings)
    monkeypatch.setattr(cli_module, "SentenceTransformerEmbedder", lambda config: embedder)
    monkeypatch.setattr(
        lifecycle_module, "HuggingFaceTokenizer", lambda model, revision: WordTokenizer()
    )
    report = tmp_path / "report.csv"
    with pytest.raises(KeyboardInterrupt):
        cli_module.main(
            [
                "--config",
                str(ROOT / "configs/rag/baseline.json"),
                "--ingestion-config",
                str(ROOT / "configs/ingestion/baseline.json"),
                "ingest",
                str(tmp_path),
                "--manifest",
                str(manifest),
                "--output-dir",
                str(tmp_path / "output"),
                "--report",
                str(report),
            ]
        )
    with report.open(encoding="utf-8", newline="") as report_file:
        completed = list(csv.DictReader(report_file))
    assert len(completed) == 1
    assert completed[0]["document_id"] == rows[0]["document_id"]
    assert completed[0]["status"] == "ready"
    repository = IngestionLifecycle(database_settings, config, embedder).repository
    history = repository.history(rows[1]["document_id"])
    assert history[0]["error_code"] == "interrupted"
