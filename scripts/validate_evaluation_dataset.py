import argparse
import csv
import json
import re
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from subprocess import check_output

import psycopg
from psycopg.rows import dict_row

from regularag.core.config import get_settings
from regularag.evaluation.dataset import (
    artifact_hash,
    canonical_hash,
    fetch_chunks,
    read_cases,
    read_evidence,
    validate_splits,
    verify_answer_filters,
    verify_freeze,
    verify_spans,
)
from regularag.evaluation.development import (
    dataset_hash,
    fetch_evidence,
    load_questions,
    verify_evidence,
)
from regularag.ingestion.manifest import load_manifest
from regularag.retrieval.config import RagBaselineConfig


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


def validate_review(directory, cases):
    with (directory / "manual_review.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    reviews = {row["question_id"]: row for row in rows}
    if len(rows) != len(reviews) or set(reviews) != {case.question_id for case in cases}:
        raise ValueError("Review inventory must cover every unique case")
    for case in cases:
        row = reviews[case.question_id]
        if row["split"] != case.split or row["review_note"] != case.review_note:
            raise ValueError("Review/split/note drift")
        verdict = "source_reviewed" if case.expected_status == "answered" else "behaviour_reviewed"
        if row["verdict"] != verdict or row["reviewer"] != "assistant_source_review":
            raise ValueError("Missing declared source/behaviour review")
        datetime.fromisoformat(row["reviewed_at"])


def validate_legacy(settings, config, cases, evidence):
    rows = load_questions(Path("data/manifests/development_questions.csv"))
    binding = json.loads(
        Path("data/manifests/development_evidence.json").read_text(encoding="utf-8")
    )
    if dataset_hash(rows) != binding["dataset_sha256"]:
        raise ValueError("Frozen development30 question drift")
    verify_evidence(binding["chunks"], fetch_evidence(settings, config, rows))
    current = {case.question_id: case for case in cases}
    for row in rows:
        case = current[row["question_id"]]
        if (
            case.split != "development"
            or case.question != row["question"]
            or case.reference_answer != row["answer"]
            or case.paraphrase_group != row["paraphrase_group"]
            or case.filters.model_dump(mode="json") != row["filters"]
            or {evidence[eid].chunk_id for eid in case.support_evidence_ids}
            != set(row["evidence_ids"])
        ):
            raise ValueError("Legacy QA/gold binding changed")
    return binding["dataset_sha256"]


def main():
    parser = argparse.ArgumentParser(
        description="Verify dataset100 and optionally seal a one-time freeze; no inference."
    )
    parser.add_argument("--directory", type=Path, default=Path("data/evaluation/v1"))
    parser.add_argument(
        "--summary", type=Path, default=Path("data/manifests/t4_1_dataset_validation.json")
    )
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    result = {
        "validated_at": datetime.now(UTC).isoformat(),
        "valid": False,
        "held_out_inference_requests": 0,
        "conditions": "Read-only schema/hash/filter/source review validation; "
        "no embedding/ranking/LLM",
    }
    try:
        directory = args.directory
        lock_exists = (directory / "freeze.json").exists()
        if args.freeze and lock_exists:
            raise ValueError("Freeze exists; never overwrite an immutable benchmark version")
        cases, evidence = (
            read_cases(directory / "questions.json"),
            read_evidence(directory / "evidence.json"),
        )
        authored = json.loads((directory / "authoring.json").read_text(encoding="utf-8"))
        validate_splits(cases, evidence, set(authored["exposed_rule_families"]))
        normalized = [" ".join(re.findall(r"\w+", case.question.casefold())) for case in cases]
        if len(set(normalized)) != 100:
            raise ValueError("Duplicate punctuation-normalized questions")
        validate_review(directory, cases)
        settings = get_settings()
        config = RagBaselineConfig.from_path(settings.rag_config_path)
        chunks = fetch_chunks(settings, config, {span.chunk_id for span in evidence.values()})
        verify_spans(evidence, chunks)
        verify_answer_filters(settings, config, cases, evidence)
        legacy_hash = validate_legacy(settings, config, cases, evidence)
        manifest = load_manifest(Path("data/manifests/documents.csv"))
        for document in manifest.values():
            if sha256(Path(document["local_path"]).read_bytes()).hexdigest() != document["sha256"]:
                raise ValueError("Source PDF byte/hash drift")
        corpus = corpus_snapshot(settings)
        if len(corpus["documents"]) != 15 or len(corpus["chunks"]) != 307:
            raise ValueError("Expected frozen M3 corpus15/307")
        omitted = next(row for row in corpus["documents"] if row["document_id"] == "uit_832_2024")
        quality = omitted["metadata"].get("_ingestion_quality", {})
        if isinstance(quality, str):
            quality = json.loads(quality)
        if omitted["coverage_status"] != "partial" or quality.get("omitted_layout_pdf_pages") != [
            3,
            5,
        ]:
            raise ValueError("Omitted-diagram negative case no longer matches corpus scope")
        history = {path: artifact_hash(Path(path)) for path in authored["exposure_files"]}
        serialized = [case.model_dump(mode="json") for case in cases]
        evidence_serialized = [span.model_dump(mode="json") for span in evidence.values()]
        if lock_exists:
            _, _, lock = verify_freeze(directory)
            if lock["corpus_sha256"] != canonical_hash(corpus) or lock["exposure_files"] != history:
                raise ValueError("Corpus/exposure registry changed after freeze")
        if args.freeze:
            lock = {
                "version": "eval100-freeze-v1",
                "frozen_at": datetime.now(UTC).isoformat(),
                "dataset_sha256": canonical_hash(serialized),
                "held_out_sha256": canonical_hash(
                    [row for row in serialized if row["split"] == "test"]
                ),
                "evidence_sha256": canonical_hash(evidence_serialized),
                "corpus_sha256": canonical_hash(corpus),
                "legacy_dataset_sha256": legacy_hash,
                "exposure_files": history,
                "files": {
                    name: artifact_hash(directory / name)
                    for name in ("authoring.json", "manual_review.csv")
                },
                "baseline_config_sha256": artifact_hash(settings.rag_config_path),
                "baseline_commit": check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "held_out_question_count": 40,
                "development_question_count": 60,
                "held_out_inference_requests_before_freeze": 0,
                "review_method": "Assistant source/behaviour review, inherited hash-bound M2 "
                "page review; not independent human review",
                "held_out_conditions": "Prospective question/rule-family hold-out authored "
                "after M3; common source corpus, not document-disjoint; "
                "no runtime tuning from test labels",
            }
            with (directory / "freeze.json").open("x", encoding="utf-8") as file:
                json.dump(lock, file, ensure_ascii=False, indent=2)
            verify_freeze(directory)
        result.update(
            {
                "valid": True,
                "cases": len(cases),
                "evidence_spans": len(evidence),
                "bound_chunks": len(chunks),
                "split_counts": dict(Counter(case.split for case in cases)),
                "category_counts": dict(Counter(case.category for case in cases)),
                "status_counts": dict(Counter(case.expected_status for case in cases)),
                "legacy_questions_preserved": 30,
                "legacy_gold_chunks_preserved": 19,
                "paraphrase_groups": len({case.paraphrase_group for case in cases}),
                "rule_families": len({f for case in cases for f in case.rule_families}),
                "dataset_sha256": canonical_hash(serialized),
                "frozen": (directory / "freeze.json").exists(),
            }
        )
    except (ValueError, KeyError, OSError, psycopg.Error) as error:
        result["valid"] = False
        result["failure_type"] = type(error).__name__
        result["failure_reason"] = str(error)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
