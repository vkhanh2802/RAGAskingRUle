import re
from collections import Counter
from hashlib import sha256

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from regularag.evaluation.dataset import canonical_hash

EVALUATOR_VERSION = "source-bound-evaluation-v1"


class AnswerReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    question_id: str
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    covered_fact_ids: list[str]
    faithful_passage_ids: list[str]
    relevant_passage_ids: list[str]
    forbidden_claims_present: bool
    behaviour_correct: bool
    reviewer: str = Field(min_length=3)
    note: str = Field(min_length=10)


def fraction(numerator, denominator, unknown=0):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "unknown": unknown,
        "value": numerator / denominator if denominator and not unknown else None,
    }


def retrieval_case(case, hits, evidence):
    if case.expected_status != "answered":
        return None  # Context/contrast evidence is never positive answer gold.
    gold = {evidence[eid].chunk_id for eid in case.support_evidence_ids}
    ranking = list(dict.fromkeys(hit["chunk_id"] for hit in hits))[:10]
    usable = {hit["chunk_id"] for hit in hits if not hit.get("freshness_failure")}
    found5 = gold.intersection(ranking[:5], usable)
    found10 = gold.intersection(ranking, usable)
    first = next((i for i, cid in enumerate(ranking, 1) if cid in gold & usable), None)
    return {
        "gold_chunks": len(gold),
        "found_at_5": len(found5),
        "found_at_10": len(found10),
        "recall_at_5": len(found5) / len(gold),
        "recall_at_10": len(found10) / len(gold),
        "reciprocal_rank_at_10": 1 / first if first else 0.0,
        "complete_at_5": found5 == gold,
        "complete_at_10": found10 == gold,
    }


def citation_binding(response, chunks):
    sources = {s["source_id"]: s for s in response.get("sources", [])}
    passages = [p for p in response.get("evidence_passages", []) if p["cited"]]
    valid = set()
    source_errors = 0
    for source in sources.values():
        row = chunks.get(source["chunk_id"])
        if (
            not row
            or any(
                source.get(key) != row[key]
                for key in ("document_id", "document_number", "source_url")
            )
            or source.get("excerpt") != row["text"]
        ):
            source_errors += 1
    for passage in passages:
        source = sources.get(passage["source_id"])
        row = chunks.get(passage["chunk_id"])
        start, end = passage["char_start"], passage["char_end"]
        views = source.get("evidence_char_ranges", []) if source else []
        if (
            source
            and row
            and source["chunk_id"] == passage["chunk_id"]
            and source["cited"]
            and 0 <= start < end <= len(row["text"])
            and row["text"][start:end] == passage["text"]
            and sha256(passage["text"].encode()).hexdigest() == passage["text_sha256"]
            and (not views or any(a <= start < end <= b for a, b in views))
        ):
            valid.add(passage["passage_id"])
    ids = [p["passage_id"] for p in passages]
    valid_registry = len(ids) == len(set(ids)) and all(
        re.fullmatch(r"P[1-9]\d*", pid) for pid in ids
    )
    ordered = sorted(passages, key=lambda p: int(p["passage_id"][1:])) if valid_registry else []
    rendered = "\n\n".join(f"“{p['text']}” [{p['source_id']}]" for p in ordered)
    answered = response.get("status") == "answered"
    fidelity = (
        bool(passages) and rendered == response.get("answer")
        if answered
        else not passages and not any(s["cited"] for s in sources.values())
    )
    source_ids = {p["source_id"] for p in passages}
    fidelity = bool(
        fidelity
        and valid_registry
        and not source_errors
        and len(sources) == len(response.get("sources", []))
        and valid == set(ids)
        and {s["source_id"] for s in sources.values() if s["cited"]} == source_ids
    )
    return {
        "valid_passage_ids": sorted(valid),
        "fidelity": fidelity
        and response.get("status") in ("answered", "insufficient_evidence", "needs_clarification"),
        "unbound_answer_units": int(answered and rendered != response.get("answer")),
    }


def span_covered(span, passages):
    intervals = sorted(
        (p["char_start"], p["char_end"]) for p in passages if p["chunk_id"] == span.chunk_id
    )
    cursor = span.char_start
    for start, end in intervals:
        if start > cursor:
            break
        cursor = max(cursor, end)
        if cursor >= span.char_end:
            return True
    return False


def score_case(case, prediction, evidence, chunks, review=None):
    response = prediction["response"]
    passages = [p for p in response.get("evidence_passages", []) if p["cited"]]
    binding = citation_binding(response, chunks)
    cited_ids = {p["passage_id"] for p in passages}
    facts = {fact.fact_id for fact in case.required_facts}
    if review:
        if review.question_id != case.question_id or review.response_sha256 != canonical_hash(
            response
        ):
            raise ValueError("Review is not bound to this prediction: " + case.question_id)
        for values, allowed in (
            (review.covered_fact_ids, facts),
            (review.faithful_passage_ids, cited_ids),
            (review.relevant_passage_ids, cited_ids),
        ):
            if len(values) != len(set(values)) or not set(values).issubset(allowed):
                raise ValueError("Unknown/duplicate fact or claim review identifier")
        if response.get("status") != "answered" and review.covered_fact_ids:
            raise ValueError("An abstention cannot satisfy answer facts")
    valid_passages = [p for p in passages if p["passage_id"] in binding["valid_passage_ids"]]
    proxy = [
        fact.fact_id
        for fact in case.required_facts
        if all(span_covered(evidence[eid], valid_passages) for eid in fact.evidence_ids)
    ]
    answered = response.get("status") == "answered"
    status_ok = response.get("status") == case.expected_status
    covered = set(review.covered_fact_ids) if review and answered else set()
    faithful = set(review.faithful_passage_ids) if review else set()
    relevant = set(review.relevant_passage_ids) if review else set()
    supported = faithful & relevant & set(binding["valid_passage_ids"])
    if case.expected_status == "answered":
        correct = (
            status_ok
            and binding["fidelity"]
            and covered == facts
            and faithful == cited_ids
            and not review.forbidden_claims_present
            if review
            else False
            if not answered or not binding["fidelity"]
            else None
        )
    else:
        correct = (
            status_ok
            and binding["fidelity"]
            and review.behaviour_correct
            and not review.forbidden_claims_present
            if review
            else False
            if not status_ok
            else None
        )
    requested = case.filters.model_dump(mode="json")
    applied = response.get("applied_filters", {})
    filter_ok = (
        all(
            applied.get(key) == value for key, value in requested.items() if value not in (None, [])
        )
        if "applied_filters" in response
        else None
    )
    if correct is True and filter_ok is not True:
        correct = False
    actual_fields = set((response.get("clarification") or {}).get("required_fields", []))
    return {
        "question_id": case.question_id,
        "category": case.category,
        "expected_status": case.expected_status,
        "actual_status": response.get("status", "error"),
        "status_match": status_ok,
        "correct": correct,
        "reviewed": review is not None,
        "required_facts": len(facts),
        "covered_facts": len(covered),
        "facts_unknown": len(facts) if answered and review is None else 0,
        "fact_span_coverage_proxy": proxy,
        "claim_units": len(passages) + binding["unbound_answer_units"],
        "citation_units": len(passages),
        "faithful_claims": len(faithful & set(binding["valid_passage_ids"])),
        "supported_citations": len(supported),
        "claims_unknown": len(passages) if review is None else 0,
        "citation_fidelity": binding["fidelity"],
        "filter_preserved": filter_ok,
        "clarification_fields_matched": len(set(case.required_clarifications) & actual_fields),
        "clarification_fields_required": len(case.required_clarifications),
        "retrieval": retrieval_case(case, prediction.get("retrieved", []), evidence),
        "failure_reason": response.get("failure_reason"),
    }


def retrieval_aggregate(rows):
    values = [r["retrieval"] for r in rows if r["retrieval"] is not None]
    n = len(values)
    return {
        "eligible_questions": n,
        "recall_at_5": sum(v["recall_at_5"] for v in values) / n if n else None,
        "recall_at_10": sum(v["recall_at_10"] for v in values) / n if n else None,
        "mrr_at_10": sum(v["reciprocal_rank_at_10"] for v in values) / n if n else None,
        "micro_recall_at_5": fraction(
            sum(v["found_at_5"] for v in values), sum(v["gold_chunks"] for v in values)
        ),
        "micro_recall_at_10": fraction(
            sum(v["found_at_10"] for v in values), sum(v["gold_chunks"] for v in values)
        ),
        "complete_at_5": fraction(sum(v["complete_at_5"] for v in values), n),
        "complete_at_10": fraction(sum(v["complete_at_10"] for v in values), n),
        "ndcg_at_10": None,
        "ndcg_note": "Not applicable: dataset has binary support, no graded relevance labels",
    }


def answer_aggregate(rows):
    answerable = [r for r in rows if r["expected_status"] == "answered"]
    no_answer = [r for r in rows if r["expected_status"] == "insufficient_evidence"]
    clarify = [r for r in rows if r["expected_status"] == "needs_clarification"]
    claims = sum(r["claim_units"] for r in rows)
    unknown_claims = sum(r["claims_unknown"] for r in rows)
    return {
        "questions": len(rows),
        "reviewed": sum(r["reviewed"] for r in rows),
        "status_accuracy": fraction(sum(r["status_match"] for r in rows), len(rows)),
        "correctness": fraction(
            sum(r["correct"] is True for r in answerable),
            len(answerable),
            sum(r["correct"] is None for r in answerable),
        ),
        "required_fact_recall": fraction(
            sum(r["covered_facts"] for r in answerable),
            sum(r["required_facts"] for r in answerable),
            sum(r["facts_unknown"] for r in answerable),
        ),
        "faithfulness": fraction(sum(r["faithful_claims"] for r in rows), claims, unknown_claims),
        "citation_support_precision": fraction(
            sum(r["supported_citations"] for r in rows),
            sum(r["citation_units"] for r in rows),
            unknown_claims,
        ),
        "citation_coverage": fraction(
            sum(r["supported_citations"] for r in rows), claims, unknown_claims
        ),
        "citation_fidelity": fraction(sum(r["citation_fidelity"] for r in rows), len(rows)),
        "filter_preservation": fraction(
            sum(r["filter_preserved"] is True for r in rows),
            len(rows),
            sum(r["filter_preserved"] is None for r in rows),
        ),
        "correct_rejection": fraction(
            sum(r["actual_status"] == "insufficient_evidence" for r in no_answer), len(no_answer)
        ),
        "false_rejection": fraction(
            sum(r["actual_status"] == "insufficient_evidence" for r in answerable), len(answerable)
        ),
        "false_clarification": fraction(
            sum(r["actual_status"] == "needs_clarification" for r in answerable), len(answerable)
        ),
        "clarification_status": fraction(sum(r["status_match"] for r in clarify), len(clarify)),
        "clarification_field_recall": fraction(
            sum(r["clarification_fields_matched"] for r in clarify),
            sum(r["clarification_fields_required"] for r in clarify),
        ),
        "status_confusion": dict(
            Counter(r["expected_status"] + "->" + r["actual_status"] for r in rows)
        ),
        "claim_unit": "Each actual cited, atomic quote block; not arbitrary sentences",
        "coverage_note": "Verified-passages emits only cited quote blocks; coverage requires "
        "source binding and manual relevance/support, not just an inline citation ID",
    }


def operation_aggregate(predictions):
    stages = {}
    for name in ("retrieval_ms", "reranker_ms", "llm_ms", "generation_stage_ms", "end_to_end_ms"):
        values = [p["timing"][name] for p in predictions]
        active = [v for v in values if v > 0]
        stages[name] = {
            "samples": len(values),
            "p50": float(np.percentile(values, 50)) if values else None,
            "p95": float(np.percentile(values, 95)) if values else None,
            "active_samples": len(active),
            "active_p50": float(np.percentile(active, 50)) if active else None,
            "active_p95": float(np.percentile(active, 95)) if active else None,
        }
    tokens = {}
    for name in ("input_tokens", "output_tokens"):
        values = [p["usage"][name] for p in predictions]
        known = [v for v in values if v is not None]
        tokens[name] = {
            "known_requests": len(known),
            "unknown_requests": len(values) - len(known),
            "sum_known": sum(known),
            "mean_per_request": sum(known) / len(values)
            if values and len(known) == len(values)
            else None,
        }
    return {
        "stages": stages,
        "tokens": tokens,
        "api_cost": {"currency": "VND", "total": 0, "mean_per_request": 0},
        "hosting_compute_cost": {"value": None, "note": "Local existing hardware; unpriced"},
        "generation_requests": sum(p["usage"]["generation_called"] for p in predictions),
        "conditions": "Serialized local CPU; no paid API/LLM judge. Retrieval includes "
        "query encoding/loading/SQL/freshness, excludes reranker. LLM timer surrounds generate; "
        "generation stage also includes budgeting/loading/validation; timings are not additive.",
    }
