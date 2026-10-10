import json
from dataclasses import replace

import pytest
from pydantic import ValidationError

from regularag.generation.clarification import QuestionScope, analyse_scope
from regularag.generation.local import GeneratedAnswer
from regularag.generation.passages import prepare_passages, resolve_passages
from regularag.generation.service import AnswerService
from regularag.retrieval.filters import RetrievalFilters
from tests.unit.generation.test_service import (
    FakeEmbedder,
    FakeGenerator,
    FakeRetriever,
    _chunk,
    _config,
)


@pytest.mark.parametrize(
    ("question", "fields"),
    [
        (
            "Em cần đạt chuẩn ngoại ngữ nào để tốt nghiệp?",
            {"cohort_year", "applies_to", "programmes"},
        ),
        ("Học phí gia hạn của em bao nhiêu?", {"cohort_year", "design_years", "as_of"}),
        ("Đồ án tốt nghiệp bao nhiêu tín chỉ?", {"project_type"}),
        (
            "Theo Quyết định956 sau bốn học kỳ chưa đạt ngoại ngữ bị giới hạn thế nào?",
            {"programmes"},
        ),
        ("Theo Thông báo43 khóa2018 bắt đầu thu học phí gia hạn khi nào?", {"design_years"}),
        ("Em muốn tạm ngừng học theo Quyết định790.", {"applies_to"}),
        ("Theo quy định năm2025 công nhận tín chỉ thế nào?", {"as_of"}),
    ],
)
def test_missing_applicability_axes_are_asked_explicitly(question, fields):
    plan = analyse_scope(question, None, None)
    assert plan.clarification and set(plan.clarification.required_fields) == fields


@pytest.mark.parametrize(
    "question,filters",
    [
        ("Quyết định851 có hiệu lực từ ngày nào?", None),
        ("Theo Quyết định956 quy định bắt buộc từ khóa nào?", None),
        ("Theo Quyết định1393 học kỳ hè tối đa bao nhiêu tín chỉ?", None),
        ("Theo Quyết định277 đồ án bao nhiêu tín chỉ và áp dụng từ khóa nào?", None),
        ("Theo Quyết định159 khóa luận có yêu cầu chuẩn ngoại ngữ nào?", None),
        (
            "Khóa2026 muốn đăng kýPET02 cần môn tiếng Anh tiên quyết nào?",
            RetrievalFilters(domains=["foreign_language"]),
        ),
        (
            "Thời gian KLTN thông thường bao nhiêu tuần?",
            RetrievalFilters(domains=["graduation_thesis"]),
        ),
    ],
)
def test_source_reading_or_uniform_clause_does_not_ask_irrelevant_scope(question, filters):
    assert analyse_scope(question, filters, None).clarification is None


def test_scope_conflicts_do_not_silently_override_filters_or_question():
    filters = RetrievalFilters(cohort_year=2026)
    plan = analyse_scope("Tôi khóa2025 học tiếng Anh.", filters, QuestionScope(programmes=["CTA"]))
    assert plan.failure_reason == "conflicting_scope"
    assert "cohort_year" in plan.clarification.conflicting_fields
    assert plan.filters.cohort_year == 2026


def test_only_explicit_cohort_and_calendar_cues_derive_filters():
    plan = analyse_scope(
        "Theo956 khóa2026 tại ngày08-10-2026 chuẩn ngoại ngữ CTA là gì?", None, None
    )
    assert plan.scope.cohort_year == 2026 and plan.scope.programmes == ("cta",)
    assert plan.filters.as_of.isoformat() == "2026-10-08"
    issued_year = analyse_scope("Quyết định956 ban hành năm2026 áp dụng từ khóa nào?", None, None)
    assert issued_year.scope.cohort_year is None and issued_year.filters.as_of is None


def test_invalid_spelled_calendar_date_asks_for_correction():
    plan = analyse_scope(
        "Theo956 tại ngày31-02-2026 quy định ngoại ngữ áp dụng thế nào?", None, None
    )
    assert plan.failure_reason == "invalid_scope_date"
    assert "as_of" in plan.clarification.required_fields


@pytest.mark.parametrize(
    "scope",
    [{"cohort_year": "2026"}, {"programmes": ["invalid"]}, {"design_years": True}, {"unknown": 1}],
)
def test_invalid_structured_scope_is_not_coerced(scope):
    with pytest.raises(ValidationError):
        QuestionScope.model_validate(scope)


def test_clarification_bypasses_retrieval_embedding_and_generation():
    class UnusedRetriever(FakeRetriever):
        def search(self, *args, **kwargs):
            raise AssertionError("Clarification must precede all model/database work")

    config = _config()
    config.behaviour.enabled = True
    service = AnswerService(config, FakeEmbedder(), UnusedRetriever([]), FakeGenerator(None))
    result = service.ask("Em cần đạt chuẩn tiếng Anh nào để tốt nghiệp?")
    assert result.status == "needs_clarification" and result.clarification
    assert not result.sources and result.selection_attempts == 0 and result.input_tokens == 0


def test_structured_reply_scope_is_used_for_prompt_and_derived_filter():
    class FilteredRetriever(FakeRetriever):
        def search(self, question, limit, filters=None):
            assert filters.cohort_year == 2026 and filters.applies_to == ("undergraduate_regular",)
            return self.chunks

    class Selector(FakeGenerator):
        def generate(self, prompt):
            assert json.loads(prompt)["scope"]["programmes"] == ["cta"]
            return GeneratedAnswer("answered", "", (), "raw", passage_ids=("P1",))

    config = _config()
    config.behaviour.enabled = True
    config.generation.response_policy = "verified_passages"
    chunk = replace(
        _chunk(),
        text="Sinh viên CTA sau 3 học kỳ chưa đạt chỉ đăng ký tối đa 16 tín chỉ.",
        cohort_from=2026,
    )
    service = AnswerService(config, FakeEmbedder(), FilteredRetriever([chunk]), Selector(None))
    result = service.ask(
        "Sau ba học kỳ chưa đạt ngoại ngữ bị giới hạn thế nào?",
        scope=QuestionScope(
            cohort_year=2026, programmes=["CTA"], applies_to=["undergraduate_regular"]
        ),
    )
    assert result.status == "answered" and "16" in result.answer
    assert (
        result.requested_filters == RetrievalFilters()
        and result.applied_filters.cohort_year == 2026
    )


def test_unknown_legal_status_returns_neutral_version_notes_without_generation():
    class Retriever(FakeRetriever):
        def search(self, question, limit, filters=None):
            return self.chunks

    config = _config()
    config.behaviour.enabled = True
    chunk = replace(_chunk(), issued_date="2024-01-01")
    service = AnswerService(config, FakeEmbedder(), Retriever([chunk]), FakeGenerator(None))
    result = service.ask("Văn bản này còn hiệu lực hiện tại không?")
    assert (
        result.status == "insufficient_evidence"
        and result.failure_reason == "legal_status_not_verified"
    )
    assert result.version_notes[0].legal_status == "unknown" and not result.sources[0].cited


def test_minimality_never_adds_unselected_facts_or_drops_signature_dependency():
    chunks = [
        replace(
            _chunk(), text="1. Học kỳ hè tối đa 12 tín chỉ.\n2. Số lượng hội đồng tối đa 12 người."
        )
    ]
    question = "Học kỳ hè tối đa bao nhiêu tín chỉ?"
    prepared = prepare_passages(question, chunks, 10000, len, 8)
    ids = tuple(p.passage_id for p in prepared.passages)
    selected, reason = resolve_passages(question, ids, prepared, minimize=True)
    assert reason is None and len(selected) == 1 and "Học kỳ hè" in selected[0].text


def test_source_cohort_question_requires_intake_statement_and_reverse_credit_measure():
    text = (
        "Điều 1. Học phần\n1. Số lượng tín chỉ của học phần: 6.\n"
        "2. Sinh viên chính quy các khóa tuyển từ năm 2024 trở về sau."
    )
    question = "Theo Quyết định277 đồ án tốt nghiệp bao nhiêu tín chỉ và áp dụng từ khóa nào?"
    prepared = prepare_passages(question, [replace(_chunk(), text=text)], 10000, len, 8)
    selected, reason = resolve_passages(
        question, tuple(p.passage_id for p in prepared.passages), prepared
    )
    assert reason is None and len(selected) == 2
    assert any("2024" in p.text for p in selected) and any("6." in p.text for p in selected)


def test_multiple_programmes_require_support_for_each_not_just_one():
    scope = QuestionScope(programmes=["ctc", "cta"])
    prepared = prepare_passages(
        "Sau ba học kỳ chưa đạt ngoại ngữ bị giới hạn thế nào?",
        [replace(_chunk(), text="Sinh viên CTA chưa đạt chỉ đăng ký tối đa 16 tín chỉ.")],
        10000,
        len,
        8,
        scope=scope,
    )
    assert prepared.failure_reason == "missing_support_candidates"


def test_matching_list_scope_in_another_order_is_not_a_conflict():
    plan = analyse_scope(
        "Chuẩn ngoại ngữ CTC/CTTN là gì?",
        RetrievalFilters(domains=["foreign_language"]),
        QuestionScope(programmes=["cttn", "ctc"]),
    )
    assert plan.clarification is None


def test_course_progress_limit_cannot_answer_a_prerequisite_question():
    question = "Sinh viên khóa2026 muốn đăng ký IEL02 phải đạt môn nào trước?"
    wrong = replace(
        _chunk(), text="Sau bốn học kỳ phải đạt PET02 hoặc IEL02; chỉ đăng ký tối đa 16 tín chỉ."
    )
    assert (
        prepare_passages(question, [wrong], 10000, len, 8).failure_reason
        == "missing_support_candidates"
    )
    right = replace(_chunk(), text="Môn học IEL01 là môn tiên quyết của môn học IEL02.")
    prepared = prepare_passages(question, [wrong, right], 10000, len, 8)
    selected, reason = resolve_passages(question, ("P1",), prepared)
    assert reason is None and selected[0].text == right.text


def test_annual_sessions_do_not_impose_a_number_of_years_and_retain_only_schedule():
    question = "Trường xét miễn tiếng Anh mấy đợt mỗi năm và vào các tháng nào?"
    chunk = replace(
        _chunk(),
        text="1. Chứng chỉ còn thời hạn hai năm.\n"
        "2. Trường xét miễn 4 đợt/năm vào các tháng 2, 5, 8, 11.",
    )
    prepared = prepare_passages(question, [chunk], 10000, len, 8)
    selected, reason = resolve_passages(question, ("P1",), prepared, minimize=True)
    assert reason is None and "4 đợt" in selected[0].text and "hai năm" not in selected[0].text
