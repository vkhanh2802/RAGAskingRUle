import argparse
import csv
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from regularag.core.config import get_settings
from regularag.evaluation.dataset import (
    EvaluationCase,
    EvidenceSpan,
    RequiredFact,
    fetch_chunks,
    validate_splits,
    verify_answer_filters,
    verify_spans,
)
from regularag.evaluation.development import (
    dataset_hash,
    fetch_evidence,
    load_questions,
    verify_evidence,
)
from regularag.retrieval.config import RagBaselineConfig


def locate_span(eid, draft, row):
    text = row["text"]
    if text.count(draft["start"]) != 1:
        raise ValueError("Missing/ambiguous manually chosen start marker: " + eid)
    start = text.index(draft["start"])
    end = len(text)
    if draft.get("end_before"):
        end = text.index(draft["end_before"], start + len(draft["start"]))
    if draft.get("end_after"):
        marker = draft["end_after"]
        end = text.index(marker, start) + len(marker)
    while end > start and text[end - 1].isspace():
        end -= 1
    excerpt = text[start:end]
    return EvidenceSpan.model_validate(
        {
            **{
                key: row[key]
                for key in (
                    "chunk_id",
                    "document_id",
                    "document_number",
                    "source_url",
                    "source_sha256",
                    "content_sha256",
                    "source_pdf_pages",
                    "article",
                    "clauses",
                    "extraction_methods",
                    "quality_status",
                )
            },
            "evidence_id": eid,
            "char_start": start,
            "char_end": end,
            "excerpt": excerpt,
            "excerpt_sha256": sha256(excerpt.encode()).hexdigest(),
            "locator": draft["locator"],
        }
    )


def case_from_draft(draft, legacy=None):
    facts = tuple(
        RequiredFact(fact_id=f"F{index}", statement=statement, evidence_ids=ids)
        for index, (statement, ids) in enumerate(draft.get("facts", []), 1)
    )
    support = tuple(dict.fromkeys(eid for fact in facts for eid in fact.evidence_ids))
    is_legacy = legacy is not None
    return EvaluationCase.model_validate(
        {
            "question_id": legacy["question_id"] if is_legacy else draft["id"],
            "split": "development" if is_legacy else draft["split"],
            "category": draft["category"],
            "paraphrase_group": legacy["paraphrase_group"] if is_legacy else draft["group"],
            "rule_families": draft["families"],
            "question": legacy["question"] if is_legacy else draft["q"],
            "expected_status": "needs_clarification"
            if draft.get("clarify")
            else "insufficient_evidence"
            if draft["category"] == "no_answer"
            else "answered",
            "reference_answer": legacy["answer"] if is_legacy else draft["a"],
            "required_facts": facts,
            "support_evidence_ids": support,
            "context_evidence_ids": draft.get("context", []),
            "contrast_evidence_ids": draft.get("contrast", []),
            "required_clarifications": draft.get("clarify", []),
            "must_not_claim": draft.get("must_not_claim", []),
            "filters": legacy["filters"] if is_legacy else draft.get("filters", {}),
            "scope": draft.get("scope", {}),
            "origin": "frozen-development30:" + legacy["question_id"]
            if is_legacy
            else "new-prospective-held-out:T4.1; no model inference"
            if draft["split"] == "test"
            else "development-expansion:T4.1; known family where applicable",
            "review_note": (
                "Assistant đối chiếu nguồn/điều kiện và locator frozen legacy; "
                + legacy["evidence_locator"]
            )
            if is_legacy
            else draft["note"],
        }
    )


def main():
    parser = argparse.ArgumentParser(
        description="Materialize manually authored QA and source spans; no models."
    )
    parser.add_argument("--directory", type=Path, default=Path("data/evaluation/v1"))
    args = parser.parse_args()
    if (args.directory / "freeze.json").exists():
        raise ValueError("Dataset is frozen; create a new reviewed version, do not rebind")
    authored = json.loads((args.directory / "authoring.json").read_text(encoding="utf-8"))
    settings = get_settings()
    config = RagBaselineConfig.from_path(settings.rag_config_path)
    old_rows = load_questions(Path("data/manifests/development_questions.csv"))
    old_binding = json.loads(
        Path("data/manifests/development_evidence.json").read_text(encoding="utf-8")
    )
    if dataset_hash(old_rows) != old_binding["dataset_sha256"]:
        raise ValueError("Frozen legacy dataset drifted")
    verify_evidence(old_binding["chunks"], fetch_evidence(settings, config, old_rows))
    old = {row["question_id"]: row for row in old_rows}
    if {row["legacy_id"] for row in authored["legacy_cases"]} != set(old):
        raise ValueError("Every frozen legacy question must be carried forward unchanged")
    cases = [case_from_draft(row, old[row["legacy_id"]]) for row in authored["legacy_cases"]]
    cases += [case_from_draft(row) for row in authored["new_cases"]]
    used = {
        eid
        for case in cases
        for eid in (
            case.support_evidence_ids + case.context_evidence_ids + case.contrast_evidence_ids
        )
    }
    chunks = fetch_chunks(settings, config, {authored["spans"][eid]["chunk_id"] for eid in used})
    spans = {
        eid: locate_span(eid, authored["spans"][eid], chunks[authored["spans"][eid]["chunk_id"]])
        for eid in sorted(used)
    }
    validate_splits(cases, spans, set(authored["exposed_rule_families"]))
    verify_spans(spans, chunks)
    verify_answer_filters(settings, config, cases, spans)
    for case in cases[:30]:
        if {spans[eid].chunk_id for eid in case.support_evidence_ids} != set(
            old[case.question_id]["evidence_ids"]
        ):
            raise ValueError("Legacy gold chunk set was changed: " + case.question_id)
    for name, values in (("questions", cases), ("evidence", spans.values())):
        (args.directory / f"{name}.json").write_text(
            json.dumps(
                [value.model_dump(mode="json") for value in values], ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
    with (args.directory / "manual_review.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "question_id",
                "split",
                "reviewer",
                "reviewed_at",
                "verdict",
                "review_note",
            ],
        )
        writer.writeheader()
        now = datetime.now(UTC).isoformat()
        for case in cases:
            writer.writerow(
                {
                    "question_id": case.question_id,
                    "split": case.split,
                    "reviewer": authored["reviewer"],
                    "reviewed_at": now,
                    "verdict": "source_reviewed"
                    if case.expected_status == "answered"
                    else "behaviour_reviewed",
                    "review_note": case.review_note,
                }
            )
    print(f"Materialized {len(cases)} reviewed cases and {len(spans)} curated spans; no inference")


if __name__ == "__main__":
    main()
