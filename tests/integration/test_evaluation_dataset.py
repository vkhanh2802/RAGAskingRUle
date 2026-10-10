import os
from hashlib import sha256

import psycopg
import pytest

from regularag.evaluation.dataset import (
    EvaluationCase,
    EvidenceSpan,
    fetch_chunks,
    verify_answer_filters,
    verify_spans,
)
from tests.integration.test_metadata_filters import scoped as scoped
from tests.integration.test_vector_baseline import artifacts as artifacts

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("REGULARAG_RUN_DB_TESTS") != "1", reason="PostgreSQL opt-in"),
]


def _evidence(row):
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
            "evidence_id": "E1",
            "char_start": 0,
            "char_end": len(row["text"]),
            "excerpt": row["text"],
            "excerpt_sha256": sha256(row["text"].encode()).hexdigest(),
            "locator": "Synthetic SQL source-bound range",
        }
    )


@pytest.mark.parametrize("gate", ["quality", "publication", "revision"])
def test_evidence_binding_uses_real_publication_quality_and_model_guards(
    database_settings, scoped, gate
):
    config, ids = scoped
    cid = f"{ids[0]}:chunk:0000"
    rows = fetch_chunks(database_settings, config, {cid})
    span = _evidence(rows[cid])
    verify_spans({"E1": span}, rows)
    with psycopg.connect(str(database_settings.database_url)) as connection:
        if gate == "quality":
            connection.execute(
                "UPDATE chunks SET quality_status='review_required' WHERE chunk_id=%s", (cid,)
            )
        elif gate == "publication":
            connection.execute(
                "UPDATE documents SET retrieval_status='blocked' WHERE document_id=%s", (ids[0],)
            )
        else:
            connection.execute(
                "UPDATE chunks SET embedding_revision=%s WHERE chunk_id=%s", ("f" * 40, cid)
            )
    with pytest.raises(ValueError, match="absent|blocked|unapproved|stale"):
        fetch_chunks(database_settings, config, {cid})


def test_gold_filter_conflict_is_reported_instead_of_relaxing_unknown_cohort(
    database_settings, scoped
):
    config, ids = scoped
    cid = f"{ids[0]}:chunk:0000"
    rows = fetch_chunks(database_settings, config, {cid})
    span = _evidence(rows[cid])
    case = EvaluationCase.model_validate(
        {
            "question_id": "D01",
            "split": "development",
            "category": "single_clause",
            "paraphrase_group": "synthetic_case",
            "rule_families": ["synthetic_case"],
            "question": "SharedQuery",
            "expected_status": "answered",
            "reference_answer": "SharedQuery is the located fixture.",
            "required_facts": [
                {"fact_id": "F1", "statement": "SharedQuery fixture text", "evidence_ids": ["E1"]}
            ],
            "support_evidence_ids": ["E1"],
            "filters": {"document_ids": [ids[0]], "cohort_year": 2026},
            "origin": "synthetic SQL test",
            "review_note": "Fixture intentionally has unknown cohort bounds.",
        }
    )
    with pytest.raises(ValueError, match="contradicts caller filters"):
        verify_answer_filters(database_settings, config, [case], {"E1": span})


def test_current_source_content_drift_is_not_automatically_rebound(database_settings, scoped):
    config, ids = scoped
    cid = f"{ids[0]}:chunk:0000"
    original = fetch_chunks(database_settings, config, {cid})
    span = _evidence(original[cid])
    text = "New approved text with a different claim"
    with psycopg.connect(str(database_settings.database_url)) as connection:
        connection.execute(
            "UPDATE chunks SET text=%s,content_sha256=%s WHERE chunk_id=%s",
            (text, sha256(text.encode()).hexdigest(), cid),
        )
    current = fetch_chunks(database_settings, config, {cid})
    with pytest.raises(ValueError, match="Stale evidence"):
        verify_spans({"E1": span}, current)
