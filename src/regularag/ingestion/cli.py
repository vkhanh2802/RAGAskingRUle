import argparse
import csv
import json
import sys
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import asdict, fields
from pathlib import Path

import psycopg

from regularag.core.config import get_settings
from regularag.ingestion.lifecycle import IngestionLifecycle, IngestionResult
from regularag.ingestion.manifest import load_manifest
from regularag.ingestion.pipeline import BaselineIngestionConfig
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.embedding import SentenceTransformerEmbedder


def ingest_target(
    lifecycle: IngestionLifecycle,
    manifest: dict[str, dict[str, str]],
    target: Path,
    workspace_root: Path,
    output_root: Path,
    document_id: str | None = None,
    force: bool = False,
    on_result: Callable[[IngestionResult], None] | None = None,
) -> list[IngestionResult]:
    by_path: dict[Path, dict[str, str]] = {}
    for document in manifest.values():
        if document.get("local_path"):
            path = (workspace_root / document["local_path"]).resolve()
            if path in by_path:
                raise ValueError("Multiple manifest documents resolve to the same source path")
            by_path[path] = document
    if document_id is not None:
        if target.is_dir():
            raise ValueError("--document-id is only supported for a single PDF")
        if document_id not in manifest:
            raise ValueError("Document ID is not in the manifest")
        sources = [(target.resolve(), manifest[document_id])]
    elif target.is_dir():
        paths = sorted(
            path for path in target.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf"
        )
        sources = [(path.resolve(), by_path.get(path.resolve())) for path in paths]
    else:
        sources = [(target.resolve(), by_path.get(target.resolve()))]
    if not sources:
        raise ValueError("No PDF sources found in the target directory")
    results = []
    for source, document in sources:
        result = (
            lifecycle.ingest(
                document, source, input_kind="pdf", output_root=output_root, force=force
            )
            if document is not None
            else lifecycle.reject_unregistered(source)
        )
        results.append(result)
        if on_result:
            on_result(result)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest, inspect and delete registered documents.")
    parser.add_argument("--config", type=Path, default=Path("configs/rag/baseline.json"))
    parser.add_argument(
        "--ingestion-config", type=Path, default=Path("configs/ingestion/structured.json")
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)
    ingest = subparsers.add_parser(
        "ingest", help="Ingest one PDF or recursively ingest a directory"
    )
    ingest.add_argument("target", type=Path)
    ingest.add_argument("--manifest", type=Path, default=Path("data/manifests/documents.csv"))
    ingest.add_argument("--workspace-root", type=Path, default=Path.cwd())
    ingest.add_argument("--output-dir", type=Path, default=Path("data/processed/ingestion-runs"))
    ingest.add_argument("--document-id")
    ingest.add_argument("--force", action="store_true")
    ingest.add_argument("--report", type=Path)
    delete = subparsers.add_parser("delete", help="Delete database document and cascade its chunks")
    delete.add_argument("document_id")
    for operation in ("status", "history"):
        inspection = subparsers.add_parser(operation)
        inspection.add_argument("--document-id")
    args = parser.parse_args(argv)

    try:
        config = RagBaselineConfig.from_path(args.config)
        lifecycle = IngestionLifecycle(
            get_settings(),
            config,
            SentenceTransformerEmbedder(config.embedding),
            BaselineIngestionConfig.from_path(args.ingestion_config),
        )
        if args.operation == "ingest":
            manifest = load_manifest(args.manifest)
            with ExitStack() as stack:
                output = None
                writer = None
                if args.report:
                    args.report.parent.mkdir(parents=True, exist_ok=True)
                    output = stack.enter_context(
                        args.report.open("w", encoding="utf-8", newline="")
                    )
                    writer = csv.DictWriter(
                        output, fieldnames=[field.name for field in fields(IngestionResult)]
                    )
                    writer.writeheader()
                    output.flush()

                def record(result: IngestionResult) -> None:
                    if writer is not None and output is not None:
                        writer.writerow(asdict(result))
                        output.flush()
                    print(
                        f"{result.document_id}: {result.status} ({result.outcome})",
                        file=sys.stderr,
                        flush=True,
                    )

                results = ingest_target(
                    lifecycle,
                    manifest,
                    args.target,
                    args.workspace_root,
                    args.output_dir,
                    args.document_id,
                    args.force,
                    on_result=record,
                )
            payload = {
                "results": [asdict(result) for result in results],
                "summary": {
                    "ready": sum(result.status == "ready" for result in results),
                    "ingested": sum(result.outcome == "ingested" for result in results),
                    "unchanged": sum(result.outcome == "unchanged" for result in results),
                    "failed": sum(result.status == "failed" for result in results),
                },
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return int(any(result.status == "failed" for result in results))
        if args.operation == "delete":
            result = lifecycle.delete(args.document_id)
            print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
            return int(result.error_code is not None)
        records = (
            lifecycle.repository.status(args.document_id)
            if args.operation == "status"
            else lifecycle.repository.history(args.document_id)
        )
        print(json.dumps(records, ensure_ascii=False, indent=2, default=str))
        return 0
    except psycopg.Error:
        print(
            json.dumps(
                {
                    "error": "database_unavailable",
                    "message": "Database/migration is unavailable",
                }
            )
        )
        return 2
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
