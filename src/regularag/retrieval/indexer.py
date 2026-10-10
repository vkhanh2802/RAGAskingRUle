from dataclasses import dataclass
from pathlib import Path

from regularag.core.config import Settings
from regularag.ingestion.lifecycle import IngestionLifecycle
from regularag.ingestion.manifest import load_manifest
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.embedding import Embedder


@dataclass(frozen=True, slots=True)
class IndexResult:
    documents: int
    chunks: int


def index_baseline(
    settings: Settings,
    config: RagBaselineConfig,
    embedder: Embedder,
    manifest_path: Path,
    processed_root: Path,
) -> IndexResult:
    """Compatibility entry point; every processed document goes through the lifecycle."""
    manifest = load_manifest(manifest_path)
    eligible_ids = config.retrieval.eligible_document_ids
    missing_manifest_ids = set(eligible_ids) - set(manifest)
    if missing_manifest_ids:
        raise ValueError(
            f"Eligible documents missing from manifest: {sorted(missing_manifest_ids)}"
        )

    lifecycle = IngestionLifecycle(settings, config, embedder)
    results = [
        lifecycle.ingest(
            manifest[document_id], processed_root / document_id, input_kind="processed"
        )
        for document_id in eligible_ids
    ]
    failures = [result for result in results if result.status == "failed"]
    if failures:
        messages = (
            f"{result.document_id}: {result.error_message or result.error_code}"
            for result in failures
        )
        raise ValueError("; ".join(messages))
    return IndexResult(documents=len(results), chunks=sum(result.chunk_count for result in results))
