from dataclasses import replace
from hashlib import sha256

import pytest

from regularag.generation.passages import EvidencePassage, prepare_passages, resolve_passages
from regularag.retrieval.filters import RetrievalFilters
from regularag.retrieval.freshness import FreshnessPolicy
from regularag.retrieval.pipeline import RetrievalPipeline
from regularag.retrieval.registration import registration_focus
from tests.unit.generation.test_service import _config
from tests.unit.retrieval.test_freshness import Catalog, family

QUESTION = (
    "Nếu điểm trung bình đến hiện tại của tôi >=8.0, tôi được phép đăng kí bao nhiêu tín chỉ?"
)
TEXT = (
    "Điều 14. Đăng ký học tập\n1. Số tín chỉ tối thiểu, tối đa\n"
    "Số tín chỉ gồm tại Trường hoặc CSĐT khác.\n"
    "a) Trong học kỳ chính:\n- Bình thường 14 ≤ n ≤ 24 tín chỉ. "
    "Sinh viên có ĐTBC ≥ 8,0 đến thời điểm đăng ký, được phép đăng ký tối đa 30 tín chỉ.\n"
    "b) Trong học kỳ hè:\n- Tổng số không vượt quá 12 tín chỉ.\n2. Học lại bắt buộc."
)


def scoped_family():
    base, update, evidence, chunk = family()
    update.metadata["_document_relations"][0]["relation_evidence"] = (
        "Verified article14clause1itemb amendment"
    )
    chunk = replace(
        chunk, text=TEXT, clauses=("1", "2"), content_sha256=sha256(TEXT.encode()).hexdigest()
    )
    return base, update, evidence, chunk


@pytest.mark.parametrize(
    "question,expected",
    [
        (QUESTION, "regular"),
        ("ĐTBC>=8 đăng ký học kỳ hè bao nhiêu tín chỉ?", "summer"),
        ("Đăng ký học kỳ chính và học kỳ hè bao nhiêu tín chỉ?", None),
        ("CTC chưa đạt PET01 sau2học kỳ chính giới hạn đăng ký bao nhiêu tín chỉ?", None),
    ],
)
def test_registration_focus_does_not_confuse_summer_or_language_progress(question, expected):
    assert registration_focus(question) == expected


def test_verified_unchanged_regular_subitem_survives_old_only_filter_without_rebinding():
    base, update, evidence, chunk = scoped_family()
    update = replace(update, matches_scope=False)
    hits = FreshnessPolicy(Catalog([base, update], evidence), clause_scoped=True).apply(
        [chunk], RetrievalFilters(document_ids=["doc"]), QUESTION
    )
    assert len(hits) == 1 and hits[0].freshness_failure is None
    assert hits[0].text == TEXT and hits[0].content_sha256 == chunk.content_sha256
    assert not hits[0].amendment_required and not hits[0].required_update_chunk_ids
    prepared = prepare_passages(QUESTION, hits, 10000, len, 8)
    selected, reason = resolve_passages(QUESTION, ("P1",), prepared)
    assert reason is None and "30 tín chỉ" in selected[0].text
    assert "học kỳ chính" in selected[0].text and "học kỳ hè" not in selected[0].text
    assert TEXT[selected[0].char_start : selected[0].char_end] == selected[0].text


@pytest.mark.parametrize(
    "witness", ["Entire article14clause1 amended", "Verified article14clause1itema amended"]
)
def test_no_precise_untouched_proof_never_falls_back_to_old_regular_rule(witness):
    base, update, evidence, chunk = scoped_family()
    update.metadata["_document_relations"][0]["relation_evidence"] = witness
    hits = FreshnessPolicy(
        Catalog([base, replace(update, matches_scope=False)], evidence), clause_scoped=True
    ).apply([chunk], None, QUESTION)
    assert hits[0].freshness_failure == "latest_excluded_by_filters"


def test_ambiguous_child_boundary_is_not_treated_as_unmodified():
    base, update, evidence, chunk = scoped_family()
    chunk = replace(
        chunk, text=TEXT.replace("a) Trong", "2. Other clause\na) Trong"), content_sha256=""
    )
    hits = FreshnessPolicy(
        Catalog([base, replace(update, matches_scope=False)], evidence), clause_scoped=True
    ).apply([chunk], None, QUESTION)
    assert hits[0].freshness_failure == "latest_excluded_by_filters"


def test_other_unchanged_article_uses_old_source_without_unrelated_companion():
    base, update, evidence, chunk = scoped_family()
    chunk = replace(
        chunk, article="24", clauses=("2",), text="Definition of ĐTBC.", content_sha256=""
    )
    hits = FreshnessPolicy(
        Catalog([base, replace(update, matches_scope=False, ready=False)], evidence),
        clause_scoped=True,
    ).apply([chunk], None, "ĐTBC là gì?")
    assert len(hits) == 1 and not hits[0].freshness_failure and not hits[0].amendment_required


def test_unknown_new_source_drift_still_blocks_even_an_unmodified_article():
    base, update, evidence, chunk = scoped_family()
    update.metadata["source_check_status"] = "source_changed"
    chunk = replace(chunk, article="24")
    hits = FreshnessPolicy(Catalog([base, update], evidence), clause_scoped=True).apply(
        [chunk], None, QUESTION
    )
    assert hits[0].freshness_failure == "portal_source_drift"


def test_summer_update_and_full_replacement_are_never_bypassed_by_regular_view():
    base, update, evidence, chunk = scoped_family()
    policy = FreshnessPolicy(
        Catalog([base, replace(update, matches_scope=False)], evidence), clause_scoped=True
    )
    assert policy.apply([chunk], None, "ĐTBC>=8 đăng ký học kỳ hè bao nhiêu tín chỉ?")[
        0
    ].freshness_failure
    update.metadata["_document_relations"][0]["kind"] = "replaces"
    assert policy.apply([chunk], None, QUESTION)[0].freshness_failure


def test_summer_only_cap_is_not_support_for_gpa_registration_question():
    _, _, _, chunk = scoped_family()
    chunk = replace(
        chunk, text="Trong học kỳ hè tổng số đăng ký tối đa 12 tín chỉ.", content_sha256=""
    )
    assert (
        prepare_passages(QUESTION, [chunk], 10000, len, 8).failure_reason
        == "missing_support_candidates"
    )


def test_forged_model_registry_cannot_select_text_outside_unmodified_view():
    base, update, evidence, chunk = scoped_family()
    hits = FreshnessPolicy(Catalog([base, update], evidence), clause_scoped=True).apply(
        [chunk], None, QUESTION
    )
    prepared = prepare_passages(QUESTION, hits, 10000, len, 8)
    start = TEXT.index("b) Trong")
    text = TEXT[start:]
    forged = EvidencePassage(
        "P1", "S1", chunk.chunk_id, start, len(TEXT), text, sha256(text.encode()).hexdigest()
    )
    assert (
        resolve_passages(QUESTION, ("P1",), replace(prepared, passages=(forged,)))[1]
        == "passage_binding_mismatch"
    )


@pytest.mark.parametrize(
    "blocked_primary,primary_status",
    [
        (False, "unchanged_verified_clause"),
        (True, "unchanged_verified_clause"),
        (False, "latest_verified_corpus"),
    ],
)
def test_only_verified_unchanged_primary_can_discard_lower_failure(blocked_primary, primary_status):
    _, _, _, good = scoped_family()
    good = replace(good, freshness_status=primary_status)
    bad = replace(good, chunk_id="blocked", freshness_failure="latest_excluded_by_filters")
    pool = [bad, good] if blocked_primary else [good, bad]
    config = _config()
    config.freshness.enabled = True
    config.freshness.policy_version = "clause-scoped-v2"

    class Pipeline(RetrievalPipeline):
        def candidates(self, *args, **kwargs):
            return pool

    pipeline = Pipeline(config, None, None, None, freshness=object())
    result = pipeline.search(QUESTION, 2)
    if blocked_primary:
        assert result[0].freshness_failure == "latest_excluded_by_filters"
    elif primary_status == "unchanged_verified_clause":
        assert [hit.chunk_id for hit in result] == [good.chunk_id]
    else:
        assert [hit.chunk_id for hit in result] == [good.chunk_id, bad.chunk_id]


def test_old_standalone_source_is_not_rejected_because_unrelated_document_is_newer():
    from tests.unit.retrieval.test_freshness import version

    old = version(issued="2010-01-01")
    newer = version("other/QD", "2026-01-01")
    _, _, _, chunk = scoped_family()
    chunk = replace(chunk, document_role="standalone", related_document_number=None)
    result = FreshnessPolicy(Catalog([old, newer], None), clause_scoped=True).apply(
        [chunk], None, QUESTION
    )
    assert len(result) == 1 and not result[0].freshness_failure
    assert result[0].latest_document_number == old.document_number
    assert result[0].latest_issued_date == "2010-01-01"
