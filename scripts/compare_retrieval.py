import argparse
import csv
import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from regularag.core.config import get_settings
from regularag.evaluation.development import CachedQueries
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.embedding import SentenceTransformerEmbedder
from regularag.retrieval.keyword import KeywordRepository, build_keyword_query
from regularag.retrieval.pipeline import RetrievalPipeline
from regularag.retrieval.repository import PgVectorRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare three retrieval modes on one frozen question set."
    )
    parser.add_argument("--questions", action="append", type=Path, default=[])
    parser.add_argument("--config", type=Path, default=Path("configs/rag/baseline.json"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/retrieval-comparison")
    )
    parser.add_argument(
        "--summary", type=Path, default=Path("data/manifests/retrieval_comparison.csv")
    )
    args = parser.parse_args()
    config = RagBaselineConfig.from_path(args.config)
    settings = get_settings()
    paths = args.questions or [
        Path("data/manifests/question_sources.csv"),
        Path("data/manifests/baseline_control_questions.csv"),
        Path("data/manifests/ocr_smoke_questions.csv"),
        Path("data/manifests/keyword_probe_questions.csv"),
    ]
    questions = []
    seen = set()
    for path in paths:
        with path.open(encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                if row["question_id"] in seen:
                    raise ValueError("Comparison question IDs must be unique")
                seen.add(row["question_id"])
                questions.append(row)
    embedder = CachedQueries(SentenceTransformerEmbedder(config.embedding))
    pipeline = RetrievalPipeline(
        config, embedder, PgVectorRepository(settings, config), KeywordRepository(settings, config)
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    with (args.output_dir / "results.jsonl").open("w", encoding="utf-8") as results:
        for question in questions:
            for mode in ("vector", "keyword", "hybrid"):
                started = perf_counter()
                hits = pipeline.search(question["question"], config.retrieval.top_k, mode)
                elapsed = round((perf_counter() - started) * 1000, 3)
                expected = set(question["candidate_document_numbers"].split(";"))
                first = hits[0] if hits else None
                row = {
                    "question_id": question["question_id"],
                    "mode": mode,
                    "document_hit_at_1": bool(first and first.document_number in expected),
                    "document_hit_at_2": any(hit.document_number in expected for hit in hits[:2]),
                    "document_hit_at_5": any(hit.document_number in expected for hit in hits),
                    "result_count": len(hits),
                    "latency_ms": elapsed,
                    "top_document": first.document_number if first else "",
                    "top_article": first.article or "" if first else "",
                    "top_chunk_id": first.chunk_id if first else "",
                    "top_score": first.score if first else "",
                    "score_kind": first.score_kind if first else "",
                    "dense_rank": first.dense_rank if first else "",
                    "keyword_rank": first.keyword_rank if first else "",
                }
                summary_rows.append(row)
                results.write(
                    json.dumps(
                        {
                            "question": question,
                            "mode": mode,
                            "keyword_query": asdict(build_keyword_query(question["question"])),
                            "summary": row,
                            "hits": [asdict(hit) for hit in hits],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                results.flush()
                print(json.dumps(row, ensure_ascii=False), flush=True)
    with args.summary.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    aggregates = {}
    for mode in ("vector", "keyword", "hybrid"):
        rows = [row for row in summary_rows if row["mode"] == mode]
        aggregates[mode] = {
            "questions": len(rows),
            "document_hits_at_1": sum(row["document_hit_at_1"] for row in rows),
            "document_hits_at_2": sum(row["document_hit_at_2"] for row in rows),
            "document_hits_at_5": sum(row["document_hit_at_5"] for row in rows),
        }
    metadata = {
        "finished_at": datetime.now(UTC).isoformat(),
        "config": config.model_dump(),
        "question_paths": [str(path) for path in paths],
        "question_count": len(questions),
        "embedding_fingerprint": config.embedding.fingerprint,
        "query_vectors_encoded_once": len(embedder.cache),
        "metrics": aggregates,
        "score_kinds": dict(Counter(row["score_kind"] for row in summary_rows)),
        "conditions": "Development smoke; document-level hits only; "
        "vector cold-start and hybrid cached query vectors; no LLM/answer-accuracy metric",
    }
    (args.output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(aggregates, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
