import argparse
import csv
import json
import platform
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
from evaluate_development import matches_filters

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
from regularag.retrieval.freshness import select_with_updates
from regularag.retrieval.keyword import KeywordRepository
from regularag.retrieval.pipeline import RetrievalPipeline
from regularag.retrieval.repository import PgVectorRepository
from regularag.retrieval.reranker import CrossEncoderReranker


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare frozen candidate pools, reranker quality and warm CPU stage latency."
    )
    parser.add_argument("--config", type=Path, default=Path("configs/rag/baseline.json"))
    parser.add_argument(
        "--questions", type=Path, default=Path("data/manifests/development_questions.csv")
    )
    parser.add_argument(
        "--evidence", type=Path, default=Path("data/manifests/development_evidence.json")
    )
    parser.add_argument(
        "--probes", type=Path, default=Path("data/manifests/m2_corpus_probe_questions.csv")
    )
    parser.add_argument("--candidate-k", type=int)
    parser.add_argument(
        "--document-reference-policy", choices=("keyword-only-v1", "shared-query-refs-v1")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/t3-1-retrieval-20"))
    parser.add_argument(
        "--summary", type=Path, default=Path("data/manifests/t3_1_retrieval_20_candidates.csv")
    )
    args = parser.parse_args()
    config = RagBaselineConfig.from_path(args.config)
    if args.candidate_k is not None:
        if not 20 <= args.candidate_k <= 40:
            parser.error("candidate-k must be between20 and40")
        config.reranker.candidate_k = config.retrieval.candidate_k = args.candidate_k
    if args.document_reference_policy:
        config.retrieval.document_reference_policy = args.document_reference_policy
    if not config.reranker.enabled or config.retrieval.top_k < 5:
        raise ValueError("Evaluation requires an enabled reranker and top_k >=5")
    settings = get_settings()
    questions = load_questions(args.questions)
    binding = json.loads(args.evidence.read_text(encoding="utf-8"))
    if binding["dataset_sha256"] != dataset_hash(questions):
        raise ValueError("Development dataset changed after evidence binding")
    verify_evidence(binding["chunks"], fetch_evidence(settings, config, questions))
    for question in questions:
        question["set"] = "development"
        question["expected_documents"] = []
    with args.probes.open(encoding="utf-8", newline="") as file:
        for probe in csv.DictReader(file):
            questions.append(
                {
                    **probe,
                    "set": "identifier_probes",
                    "filters": {},
                    "evidence_ids": [],
                    "expected_documents": probe["candidate_document_numbers"].split(";"),
                }
            )
    embedder = CachedQueries(SentenceTransformerEmbedder(config.embedding))
    started = perf_counter()
    _ = embedder.embedder.model
    embedding_load_ms = (perf_counter() - started) * 1000
    query_times = []
    for question in questions:
        started = perf_counter()
        embedder.embed_query(question["question"])
        query_times.append((perf_counter() - started) * 1000)
    reranker = CrossEncoderReranker(config.reranker)
    started = perf_counter()
    model = reranker.model
    reranker_load_ms = (perf_counter() - started) * 1000
    model.predict([("warm up", "warm up")], batch_size=1, show_progress_bar=False)
    pipeline = RetrievalPipeline(
        config,
        embedder,
        PgVectorRepository(settings, config),
        KeywordRepository(settings, config),
        reranker=reranker,
    )
    # Warm database/query planning independently of the first recorded question.
    pipeline.candidates(questions[0]["question"], "hybrid", RetrievalFilters())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with (args.output_dir / "results.jsonl").open("w", encoding="utf-8") as results:
        for question in questions:
            conditions = (
                ("unfiltered", "scoped") if question["set"] == "development" else ("unfiltered",)
            )
            for condition in conditions:
                filters = RetrievalFilters.model_validate(
                    question["filters"] if condition == "scoped" else {}
                )
                for mode in ("vector", "hybrid"):
                    started = perf_counter()
                    pool = pipeline.candidates(question["question"], mode, filters)
                    retrieval_ms = (perf_counter() - started) * 1000
                    variants = [(f"{mode}_off", pool, 0.0)]
                    if mode == "hybrid":
                        started = perf_counter()
                        reranked = reranker.rerank(question["question"], pool)
                        variants.append(("hybrid_on", reranked, (perf_counter() - started) * 1000))
                    for variant, ordered, rerank_ms in variants:
                        hits = select_with_updates(ordered, config.retrieval.top_k)
                        gold = set(question["evidence_ids"])
                        ids = {hit.chunk_id for hit in hits}
                        context = select_with_updates(hits, config.generation.context_chunks)
                        context_ids = {hit.chunk_id for hit in context}
                        row = {
                            "question_id": question["question_id"],
                            "set": question["set"],
                            "condition": condition,
                            "variant": variant,
                            "candidate_count": len(pool),
                            "gold_hit_at_1": bool(gold.intersection(h.chunk_id for h in hits[:1])),
                            "gold_hit_at_2": bool(gold.intersection(h.chunk_id for h in hits[:2])),
                            "gold_hit_at_5": bool(gold.intersection(h.chunk_id for h in hits[:5])),
                            "complete_evidence_at_2": bool(gold)
                            and gold.issubset({h.chunk_id for h in hits[:2]}),
                            "complete_evidence_at_context": bool(gold)
                            and gold.issubset(context_ids),
                            "document_hit_at_1": bool(hits)
                            and hits[0].document_number in question["expected_documents"],
                            "top_chunk_id": hits[0].chunk_id if hits else "",
                            "scope_violations": sum(
                                not matches_filters(hit, filters) for hit in hits
                            ),
                            "missing_update_context": sum(
                                not set(hit.required_update_chunk_ids).issubset(context_ids)
                                for hit in context
                            ),
                            "freshness_blocked": sum(bool(hit.freshness_failure) for hit in hits),
                            "retrieval_ms": round(retrieval_ms, 3),
                            "rerank_ms": round(rerank_ms, 3),
                            "total_stage_ms": round(retrieval_ms + rerank_ms, 3),
                            "rerank_windows": sum(hit.rerank_windows for hit in ordered),
                            "result_count": len(ids),
                        }
                        rows.append(row)
                        results.write(
                            json.dumps(
                                {
                                    "question": question,
                                    "summary": row,
                                    "candidates": [asdict(hit) for hit in pool],
                                    "hits": [asdict(hit) for hit in hits],
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                        results.flush()
            print(question["question_id"] + " complete", flush=True)
    with args.summary.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metrics = {}
    for group in sorted({(r["set"], r["condition"], r["variant"]) for r in rows}):
        selected = [r for r in rows if (r["set"], r["condition"], r["variant"]) == group]
        metrics["/".join(group)] = {
            "questions": len(selected),
            **{
                key: sum(r[key] for r in selected)
                for key in (
                    "gold_hit_at_1",
                    "gold_hit_at_2",
                    "gold_hit_at_5",
                    "complete_evidence_at_2",
                    "complete_evidence_at_context",
                    "document_hit_at_1",
                    "scope_violations",
                    "missing_update_context",
                    "freshness_blocked",
                )
            },
            "stage_p50_ms": round(float(np.median([r["total_stage_ms"] for r in selected])), 3),
            "stage_p95_ms": round(
                float(np.percentile([r["total_stage_ms"] for r in selected], 95)), 3
            ),
            "rerank_p50_ms": round(float(np.median([r["rerank_ms"] for r in selected])), 3),
        }
    metadata = {
        "finished_at": datetime.now(UTC).isoformat(),
        "config": config.model_dump(),
        "dataset_sha256": binding["dataset_sha256"],
        "embedding_fingerprint": config.embedding.fingerprint,
        "python": platform.python_version(),
        "embedding_load_ms": round(embedding_load_ms, 3),
        "reranker_load_ms": round(reranker_load_ms, 3),
        "query_encoding_p50_ms": round(float(np.median(query_times)), 3),
        "query_encoding_p95_ms": round(float(np.percentile(query_times, 95)), 3),
        "unique_query_vectors": len(embedder.cache),
        "metrics": metrics,
        "conditions": "CPU, warmed models and database; shared cached query vectors; "
        "identical frozen hybrid pools for on/off; stage timing excludes query encoding, "
        "LLM and prompt budgeting; context completeness before LLM token budget; "
        "assistant-reviewed development evidence, not held-out answer accuracy",
    }
    (args.output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
