from dataclasses import replace
from pathlib import Path

import pytest

from regularag.evaluation.dataset import verify_freeze
from regularag.generation.clarification import QuestionScope, analyse_scope
from regularag.generation.passages import (
    prepare_passages,
    prioritize_support_sources,
    resolve_passages,
    support_facets,
)
from tests.unit.generation.test_service import _chunk


def prepare(question, text):
    chunks = [replace(_chunk(), text=text, content_sha256="")]
    return prepare_passages(question, chunks, 10000, len, 8)


def test_archive_and_grade_deadline_cannot_be_pruned_to_only_one_fact():
    question = "Khoa giữ hồ sơ bảo vệ bao lâu và gửi bảng điểm trong bao lâu sau bảo vệ?"
    registry = prepare(
        question,
        "1. Khoa lưu trữ hồ sơ tối thiểu trong vòng5 năm.\n"
        "2. Khoa nhập điểm hệ thống và gửi bảng điểm giấy trong20 ngày sau bảo vệ.",
    )
    assert len(registry.passages) == 2
    assert resolve_passages(question, ("P1",), registry)[1] == "incomplete_passage_support"
    selected, reason = resolve_passages(question, ("P1", "P2"), registry, minimize=True)
    assert reason is None and len(selected) == 2


def test_supervisor_degree_and_reviewer_distinctness_require_both_blocks():
    question = "Học vị CBHD tối thiểu là gì và người đó có thể kiêm CBPB không?"
    registry = prepare(
        question,
        "1. CBHD có học vị từ thạc sĩ trở lên.\n"
        "2. CBPB phải khác CBHD và không có quan hệ ruột thịt vớiSV.",
    )
    assert len(registry.passages) == 2
    assert resolve_passages(question, ("P1",), registry)[1] == "incomplete_passage_support"


def test_certificate_validity_and_month_schedule_both_required():
    question = "Hạn chứng chỉ xét miễn tính từ ngày nào và mở xét miễn vào những tháng nào?"
    registry = prepare(
        question,
        "1. Chứng chỉ phải còn thời hạn hai năm tính từ ngày thi đến ngày đăng ký xét miễn.\n"
        "2. Trường xét miễn4 đợt/năm vào các tháng2,5,8,11.",
    )
    assert len(registry.passages) == 2
    assert resolve_passages(question, ("P1",), registry)[1] == "incomplete_passage_support"


def test_compact_course_and_mgrade_are_not_confused_with_progress_rules():
    question = "Muốn đăng kýPET02 cần môn nào trước và điểmM miễn ngoại ngữ vào ĐTB không?"
    wrong = prepare(question, "Sinh viên CTC sau2 học kỳ phải đạtPET01 hoặcIEL01; cap16 tín chỉ.")
    assert wrong.failure_reason == "missing_support_candidates"
    registry = prepare(
        question,
        "1. PET01 hoặc IEL01 là môn tiên quyết của môn học PET02.\n"
        "2. Điểm miễn ký hiệu làM được tính học kỳ kế tiếp, "
        "không tính các điểm trung bình học tập.",
    )
    assert registry.failure_reason is None and len(registry.passages) == 2


def test_calendar_asof_is_not_a_count_of_days_obligation():
    question = (
        "Tại ngày01-12-2025 học phần công nhận cần tối thiểu điểm nào và hoàn thành bao nhiêu năm?"
    )
    facets = support_facets(question)
    assert "days" not in facets and "years" in facets and "recognition_grade" in facets
    registry = prepare(
        question,
        "1. Điểm học phần phải đạt từC hoặc5 trên thang10.\n"
        "2. Học phần phải hoàn thành không quá5 năm tính đến ngày nộp đơn.",
    )
    assert registry.failure_reason is None and len(registry.passages) == 2


def test_student_abbreviation_requires_class_count_not_unrelated_credit_definition():
    question = "Lớp đại cương chỉ cần50SV phải không?"
    assert "students" in support_facets(question)
    assert prepare(question, "Một tín chỉ bằng15 tiết học, sinh viên tự học30 giờ.").failure_reason
    registry = prepare(question, "Lớp học phần mở với70 sinh viên đối với môn đại cương.")
    assert registry.failure_reason is None


def test_source_reservation_finds_later_mgrade_provider_without_expanding_pool():
    question = "Đăng kýPET02 cần môn nào trước và điểmM miễn ngoại ngữ vào ĐTB không?"
    one = replace(_chunk(), chunk_id="prereq", text="PET01 là môn tiên quyết của PET02.")
    noise = [
        replace(_chunk(), chunk_id=f"n{i}", text="Chuẩn quá trình ngoại ngữ.") for i in range(4)
    ]
    grade = replace(
        _chunk(),
        chunk_id="grade",
        text="Điểm miễn ký hiệu làM không tính các điểm trung bình học tập.",
    )
    pool = [one, *noise, grade]
    reordered = prioritize_support_sources(question, pool)
    assert [c.chunk_id for c in reordered[:2]] == ["prereq", "grade"]
    assert {c.chunk_id for c in reordered} == {c.chunk_id for c in pool}
    blocked = [replace(one, freshness_failure="latest_excluded_by_filters"), *noise, grade]
    assert prioritize_support_sources(question, blocked) == blocked


def test_unknown_progress_is_asked_but_explicit_after_three_is_parsed():
    plan = analyse_scope("Em chưa đạt chuẩn ngoại ngữ thì đăng ký bao nhiêu tín chỉ?", None, None)
    assert "study_progress" in plan.clarification.required_fields
    plan = analyse_scope("Sau ba học kỳ chưa đạt ngoại ngữ bị giới hạn thế nào?", None, None)
    assert plan.scope.study_progress == 3
    assert "study_progress" not in plan.clarification.required_fields


@pytest.mark.parametrize("value", [True, "3", -1, 41, 2.5])
def test_progress_type_is_strict(value):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        QuestionScope(study_progress=value)


def test_absent_new_scope_axis_preserves_frozen_dataset_serialization():
    assert "study_progress" not in QuestionScope().model_dump(mode="json")
    assert QuestionScope(study_progress=0).model_dump(mode="json")["study_progress"] == 0
    _, _, lock = verify_freeze(Path("data/evaluation/v1"))
    assert (
        lock["dataset_sha256"] == "d577dcde2469cdb1650b4e7b1164e520afc5037d6668fe1b5eb06c7f98946f0c"
    )
