from dataclasses import replace

import pytest

from regularag.evaluation.dataset import EvaluationCase, canonical_hash
from regularag.evaluation.instrumentation import RecordingRetriever
from regularag.evaluation.metrics import (
    AnswerReview,
    answer_aggregate,
    citation_binding,
    operation_aggregate,
    retrieval_case,
    score_case,
    span_covered,
)
from regularag.retrieval.pipeline import RetrievalPipeline
from tests.unit.generation.test_service import _config
from tests.unit.retrieval.test_registration_scope import scoped_family
from tests.unit.test_evaluation_dataset import _bound_span


def example():
    row, span = _bound_span()
    case = EvaluationCase.model_validate(
        {
            "question_id": "D01",
            "split": "development",
            "category": "single_clause",
            "paraphrase_group": "summer_cap",
            "rule_families": ["summer_cap"],
            "question": "Học kỳ hè tối đa bao nhiêu tín chỉ?",
            "expected_status": "answered",
            "reference_answer": "Học kỳ hè tối đa12tín chỉ.",
            "required_facts": [
                {"fact_id": "F1", "statement": "Tối đa12tín chỉ.", "evidence_ids": ["E1"]}
            ],
            "support_evidence_ids": ["E1"],
            "origin": "synthetic metrics case",
            "review_note": "Explicit source-bound synthetic fixture for denominator tests.",
        }
    )
    response = {
        "status": "answered",
        "answer": f"“{span.excerpt}” [S1]",
        "applied_filters": {},
        "sources": [
            {
                **{
                    key: row[key]
                    for key in ("chunk_id", "document_id", "document_number", "source_url")
                },
                "source_id": "S1",
                "excerpt": row["text"],
                "cited": True,
            }
        ],
        "evidence_passages": [
            {
                "passage_id": "P1",
                "source_id": "S1",
                "chunk_id": row["chunk_id"],
                "char_start": span.char_start,
                "char_end": span.char_end,
                "text": span.excerpt,
                "text_sha256": span.excerpt_sha256,
                "cited": True,
            }
        ],
    }
    prediction = {"response": response, "retrieved": [{"chunk_id": row["chunk_id"]}]}
    review = AnswerReview(
        question_id="D01",
        response_sha256=canonical_hash(response),
        covered_fact_ids=["F1"],
        faithful_passage_ids=["P1"],
        relevant_passage_ids=["P1"],
        forbidden_claims_present=False,
        behaviour_correct=True,
        reviewer="synthetic-test",
        note="Located summer cap reviewed.",
    )
    return row, span, case, prediction, review


def test_recall_is_fraction_of_unique_support_and_mrr_is_first_relevant_rank():
    _, span, case, _, _ = example()
    second = span.model_copy(update={"evidence_id": "E2", "chunk_id": "other"})
    case = case.model_copy(update={"support_evidence_ids": ("E1", "E2")})
    hits = [{"chunk_id": "noise"}, {"chunk_id": span.chunk_id}, {"chunk_id": span.chunk_id}]
    result = retrieval_case(case, hits, {"E1": span, "E2": second})
    assert result["recall_at_5"] == 0.5 and result["reciprocal_rank_at_10"] == 0.5
    assert not result["complete_at_10"]


def test_contrast_abstention_never_enters_retrieval_denominator():
    _, span, case, _, _ = example()
    case = case.model_copy(
        update={
            "expected_status": "insufficient_evidence",
            "support_evidence_ids": (),
            "contrast_evidence_ids": ("E1",),
        }
    )
    assert retrieval_case(case, [{"chunk_id": span.chunk_id}], {"E1": span}) is None


def test_blocked_gold_hit_is_not_usable_retrieval_support():
    _, span, case, _, _ = example()
    result = retrieval_case(
        case, [{"chunk_id": span.chunk_id, "freshness_failure": "blocked"}], {"E1": span}
    )
    assert result["recall_at_10"] == 0 and result["reciprocal_rank_at_10"] == 0


def test_gold_span_coverage_is_not_automatically_semantic_correctness():
    row, span, case, prediction, _ = example()
    score = score_case(case, prediction, {"E1": span}, {row["chunk_id"]: row})
    assert score["fact_span_coverage_proxy"] == ["F1"] and score["correct"] is None
    metrics = answer_aggregate([score])
    assert metrics["correctness"]["unknown"] == 1 and metrics["correctness"]["value"] is None
    assert metrics["citation_fidelity"]["value"] == 1


def test_partial_overlap_does_not_count_as_complete_gold_span():
    _, span, _, prediction, _ = example()
    p = prediction["response"]["evidence_passages"][0]
    assert not span_covered(span, [{**p, "char_start": p["char_start"] + 1}])


@pytest.mark.parametrize("kind", ["hash", "source", "view", "extra_prose"])
def test_citation_fidelity_rejects_forged_binding_and_uncited_prose(kind):
    row, _, _, prediction, _ = example()
    response = prediction["response"]
    if kind == "hash":
        response["evidence_passages"][0]["text_sha256"] = "f" * 64
    elif kind == "source":
        response["sources"][0]["document_id"] = "wrong"
    elif kind == "view":
        response["sources"][0]["evidence_char_ranges"] = [[0, 1]]
    else:
        response["answer"] += " Invented uncited assertion."
    assert not citation_binding(response, {row["chunk_id"]: row})["fidelity"]


def test_manual_relevance_is_separate_from_verbatim_faithfulness():
    row, span, case, prediction, review = example()
    review = review.model_copy(update={"relevant_passage_ids": []})
    score = score_case(case, prediction, {"E1": span}, {row["chunk_id"]: row}, review)
    metrics = answer_aggregate([score])
    assert metrics["faithfulness"]["value"] == 1
    assert metrics["citation_support_precision"]["value"] == 0


def test_response_hash_prevents_reusing_reviews_on_changed_predictions():
    row, span, case, prediction, review = example()
    prediction["response"]["answer"] += " changed"
    with pytest.raises(ValueError, match="not bound"):
        score_case(case, prediction, {"E1": span}, {row["chunk_id"]: row}, review)


def test_missing_required_fact_and_forbidden_claims_fail_correctness():
    row, span, case, prediction, review = example()
    for change in ({"covered_fact_ids": []}, {"forbidden_claims_present": True}):
        score = score_case(
            case, prediction, {"E1": span}, {row["chunk_id"]: row}, review.model_copy(update=change)
        )
        assert score["correct"] is False


def test_unknown_usage_and_no_generation_are_not_confused():
    rows = [
        {
            "timing": {
                key: 0
                for key in (
                    "retrieval_ms",
                    "reranker_ms",
                    "llm_ms",
                    "generation_stage_ms",
                    "end_to_end_ms",
                )
            },
            "usage": {
                "input_tokens": value,
                "output_tokens": value,
                "generation_called": value is None,
            },
        }
        for value in (0, None)
    ]
    result = operation_aggregate(rows)
    assert result["tokens"]["output_tokens"]["unknown_requests"] == 1
    assert result["tokens"]["output_tokens"]["mean_per_request"] is None
    assert result["stages"]["llm_ms"]["active_samples"] == 0


def test_instrumentation_captures_rank10_without_changing_answer_top_k():
    _, _, _, original = scoped_family()
    pool = [replace(original, chunk_id=f"c{i}") for i in range(12)]

    class Pipeline(RetrievalPipeline):
        def candidates(self, *args, **kwargs):
            return pool

    pipeline = Pipeline(_config(), None, None, None)
    expected = pipeline.search("query", 5)
    observed = RecordingRetriever(pipeline)
    assert observed.search("query", 5) == expected
    assert [hit["chunk_id"] for hit in observed.hits] == [f"c{i}" for i in range(10)]
