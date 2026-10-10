import argparse
import csv
import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from regularag.core.config import get_settings
from regularag.evaluation.development import (
    CachedQueries,
    dataset_hash,
    fetch_evidence,
    load_questions,
    verify_evidence,
)
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.embedding import SentenceTransformerEmbedder
from regularag.retrieval.filters import RetrievalFilters
from regularag.retrieval.keyword import KeywordRepository
from regularag.retrieval.pipeline import RetrievalPipeline
from regularag.retrieval.repository import PgVectorRepository


def matches_filters(hit, filters: RetrievalFilters) -> bool:
    for values, actual in (
        (filters.document_ids, hit.document_id),
        (filters.domains, hit.domain),
        (filters.document_types, hit.document_type),
    ):
        if values and actual not in values:
            return False
    if filters.applies_to and not set(filters.applies_to).intersection(hit.applies_to.split(";")):
        return False
    if filters.cohort_year is not None:
        if hit.cohort_from is None and hit.cohort_to is None:
            return False
        if hit.cohort_from is not None and filters.cohort_year < hit.cohort_from:
            return False
        if hit.cohort_to is not None and filters.cohort_year > hit.cohort_to:
            return False
    if filters.as_of:
        if (
            not hit.effective_from_date
            or date.fromisoformat(hit.effective_from_date) > filters.as_of
        ):
            return False
        if hit.effective_to_date and date.fromisoformat(hit.effective_to_date) < filters.as_of:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate gold chunks with/without scope filters.")
    parser.add_argument(
        "--questions", type=Path, default=Path("data/manifests/development_questions.csv")
    )
    parser.add_argument(
        "--evidence", type=Path, default=Path("data/manifests/development_evidence.json")
    )
    parser.add_argument("--config", type=Path, default=Path("configs/rag/baseline.json"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/development-retrieval")
    )
    parser.add_argument(
        "--summary", type=Path, default=Path("data/manifests/development_retrieval.csv")
    )
    args = parser.parse_args()
    questions = load_questions(args.questions)
    binding = json.loads(args.evidence.read_text(encoding="utf-8"))
    if binding["dataset_sha256"] != dataset_hash(questions):
        raise ValueError("Development questions/answers/filters changed after evidence binding")
    config = RagBaselineConfig.from_path(args.config)
    if config.retrieval.top_k < 5:
        raise ValueError("Development hit@5 needs retrieval top_k >= 5")
    settings = get_settings()
    verify_evidence(binding["chunks"], fetch_evidence(settings, config, questions))
    embedder = CachedQueries(SentenceTransformerEmbedder(config.embedding))
    pipeline = RetrievalPipeline(
        config, embedder, PgVectorRepository(settings, config), KeywordRepository(settings, config)
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with (args.output_dir / "results.jsonl").open("w", encoding="utf-8") as results:
        for question in questions:
            gold = set(question["evidence_ids"])
            for condition in ("unfiltered", "scoped"):
                filters = (
                    RetrievalFilters.model_validate(question["filters"])
                    if condition == "scoped"
                    else RetrievalFilters()
                )
                for mode in ("vector", "keyword", "hybrid"):
                    hits = pipeline.search(
                        question["question"], config.retrieval.top_k, mode, filters
                    )
                    positions = [i for i, hit in enumerate(hits, 1) if hit.chunk_id in gold]
                    row = {
                        "question_id": question["question_id"],
                        "condition": condition,
                        "mode": mode,
                        "gold_hit_at_1": any(hit.chunk_id in gold for hit in hits[:1]),
                        "gold_hit_at_2": any(hit.chunk_id in gold for hit in hits[:2]),
                        "gold_hit_at_5": any(hit.chunk_id in gold for hit in hits[:5]),
                        "complete_evidence_at_2": gold.issubset({hit.chunk_id for hit in hits[:2]}),
                        "complete_evidence_at_5": gold.issubset({hit.chunk_id for hit in hits[:5]}),
                        "first_gold_rank": min(positions) if positions else "",
                        "result_count": len(hits),
                        "top_chunk_id": hits[0].chunk_id if hits else "",
                        "scope_violations": sum(not matches_filters(hit, filters) for hit in hits),
                    }
                    rows.append(row)
                    results.write(
                        json.dumps(
                            {
                                "question": question,
                                "filters": filters.model_dump(mode="json"),
                                "summary": row,
                                "hits": [asdict(hit) for hit in hits],
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    results.flush()
    with args.summary.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    aggregates = {}
    for condition in ("unfiltered", "scoped"):
        for mode in ("vector", "keyword", "hybrid"):
            selected = [
                row for row in rows if row["condition"] == condition and row["mode"] == mode
            ]
            aggregates[f"{condition}/{mode}"] = {
                "questions": len(selected),
                **{
                    key: sum(row[key] for row in selected)
                    for key in (
                        "gold_hit_at_1",
                        "gold_hit_at_2",
                        "gold_hit_at_5",
                        "complete_evidence_at_2",
                        "complete_evidence_at_5",
                        "scope_violations",
                    )
                },
            }
    metadata = {
        "finished_at": datetime.now(UTC).isoformat(),
        "config": config.model_dump(),
        "dataset_sha256": binding["dataset_sha256"],
        "question_count": len(questions),
        "embedding_fingerprint": config.embedding.fingerprint,
        "metrics": aggregates,
        "query_vectors_encoded_once": len(embedder.cache),
        "conditions": "Development gold-chunk retrieval only; supplied scope filters; "
        "shared cached vectors; no answer accuracy or latency comparison",
    }
    (args.output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(aggregates, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
