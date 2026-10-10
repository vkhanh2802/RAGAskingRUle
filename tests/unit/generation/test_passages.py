import json
from dataclasses import replace
from hashlib import sha256

import pytest

from regularag.generation.local import GeneratedAnswer, parse_passage_selection
from regularag.generation.passages import prepare_passages, resolve_passages
from regularag.generation.service import AnswerService
from tests.unit.generation.test_service import (
    FakeEmbedder,
    FakeGenerator,
    FakeRetriever,
    _chunk,
    _config,
)


def prepare(question, chunks, limit=10000):
    return prepare_passages(question, chunks, limit, len, 8)


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ('{"passage_ids":["P99"]}', "invalid_passage_ids"),
        ('{"passage_ids":["P1","P1"]}', "invalid_schema"),
        ('{"passage_ids":"P1"}', "invalid_schema"),
        ('{"passage_ids":[1]}', "invalid_schema"),
        ('{"passage_ids":["P1"],"source_id":"S9"}', "invalid_schema"),
        ('prefix {"passage_ids":["P1"]}', "invalid_json"),
    ],
)
def test_passage_selection_rejects_fabricated_ids_text_and_malformed_output(raw, reason):
    result = parse_passage_selection(raw, ("P1", "P2"))
    assert result.status == "insufficient_evidence" and result.failure_reason == reason


def test_passages_are_exact_contiguous_ranges_and_complete_condition_blocks():
    text = (
        "Điều 1. Công nhận tín chỉ\n1. Phạm vi khác.\n"
        "2. Học phần trực tuyến phải đáp ứng đầy đủ các điều kiện:\n"
        "a) Chỉ áp dụng cho nhóm học phần tự chọn tự do.\n"
        "b) Nội dung không trùng lặp.\n"
        "c) Tổng số không quá 03 tín chỉ; 15 giờ thực học tương đương một tín chỉ."
    )
    chunk = replace(_chunk(), text=text, content_sha256=sha256(text.encode()).hexdigest())
    question = "Học phần trực tuyến tối đa bao nhiêu tín chỉ và áp dụng cho nhóm nào?"
    prepared = prepare(question, [chunk])
    passage = next(p for p in prepared.passages if "2. Học phần" in p.text)
    selected, reason = resolve_passages(question, (passage.passage_id,), prepared)
    assert reason is None and len(selected) == 1
    assert "không trùng lặp" in passage.text and "15 giờ" in passage.text
    assert chunk.text[passage.char_start : passage.char_end] == passage.text
    too_small = prepare(question, [replace(chunk, text=passage.text, content_sha256="")], 120)
    assert too_small.failure_reason == "passage_budget_exceeded" and not too_small.passages


@pytest.mark.parametrize("field", ["text", "char_start", "text_sha256", "source_id"])
def test_tampered_span_binding_never_becomes_an_answer(field):
    question = "Học kỳ hè tối đa bao nhiêu tín chỉ?"
    chunk = replace(_chunk(), text="Học kỳ hè tối đa 12 tín chỉ.")
    prepared = prepare(question, [chunk])
    changes = {
        "text": "Học kỳ hè tối đa 15 tín chỉ.",
        "char_start": 1,
        "text_sha256": "0" * 64,
        "source_id": "S9",
    }
    tampered = replace(
        prepared, passages=(replace(prepared.passages[0], **{field: changes[field]}),)
    )
    assert resolve_passages(question, ("P1",), tampered)[1] == "passage_binding_mismatch"


def test_effective_date_from_signature_requires_same_document_literal_date_evidence():
    header = replace(
        _chunk(), chunk_id="header", text="ngày 29 tháng 12 năm 2023", issued_date="2023-12-29"
    )
    effective = replace(
        _chunk(), chunk_id="effect", text="Điều 2. Quyết định có hiệu lực kể từ ngày ký."
    )
    question = "Quyết định có hiệu lực từ ngày nào?"
    prepared = prepare(question, [effective, header])
    effect = next(p for p in prepared.passages if "hiệu lực" in p.text)
    selected, reason = resolve_passages(question, (effect.passage_id,), prepared)
    assert reason is None and any("29 tháng 12" in p.text for p in selected)
    missing = prepare(question, [effective])
    assert resolve_passages(question, ("P1",), missing)[1] == "missing_signature_evidence"


def test_selection_that_answers_only_one_requested_degree_type_is_rejected():
    question = "Văn bằng giấy và văn bằng số tối đa bao nhiêu ngày?"
    chunk = replace(_chunk(), text="1. Văn bằng giấy tối đa 30 ngày.\n2. VBCC số tối đa 05 ngày.")
    prepared = prepare(question, [chunk])
    paper = next(p for p in prepared.passages if "giấy" in p.text)
    digital = next(p for p in prepared.passages if "VBCC" in p.text)
    assert (
        resolve_passages(question, (paper.passage_id,), prepared)[1] == "incomplete_passage_support"
    )
    assert resolve_passages(question, (paper.passage_id, digital.passage_id), prepared)[1] is None


def test_wrapped_units_and_grading_question_do_not_impose_reviewer_identity_rule():
    question = "Điểm CBHD và CBPB có hệ số bao nhiêu và làm tròn thế nào?"
    chunk = replace(
        _chunk(), text="Điểm CBHD và CBPB hệ số 2; thành viên khác hệ số 1. Làm\ntròn đến 0.1."
    )
    prepared = prepare(question, [chunk])
    assert resolve_passages(question, ("P1",), prepared)[1] is None
    students = replace(
        _chunk(), text="Lớp đại cương và cơ sở\nngành học chung mở với 70 sinh viên."
    )
    q = "Lớp đại cương hoặc cơ sở ngành cần ít nhất bao nhiêu sinh viên?"
    assert prepare(q, [students]).failure_reason is None


def test_student_abbreviation_and_complete_condition_article_are_preserved():
    question = "Một đề tài được giao cho mấy sinh viên?"
    prepared = prepare(
        question, [replace(_chunk(), text="3. Mỗi đề tài được giao cho từ 1 đến 2 SV.")]
    )
    assert resolve_passages(question, ("P1",), prepared)[1] is None
    text = (
        "Điều 3. Điều kiện công nhận tín chỉ\n1. Tương đương nội dung.\n"
        "2. Điểm từ C hoặc 5 trở lên.\n3. Hoàn thành trong vòng 5 năm."
    )
    conditions = prepare(
        "Công nhận tín chỉ cần đáp ứng điều kiện nào?", [replace(_chunk(), text=text)]
    )
    assert len(conditions.passages) == 1 and conditions.passages[0].text == text


def test_matching_grade_without_requested_midterm_suspension_is_not_support():
    chunk = replace(_chunk(), text="Sau bảo vệ nhận điểm 0 nếu không nộp báo cáo.")
    prepared = prepare("Bị đình chỉ sau đánh giá giữa kỳ nhận điểm thế nào?", [chunk])
    assert prepared.failure_reason == "missing_support_candidates"


def test_named_program_question_does_not_present_other_program_limits():
    text = (
        "1. Sinh viên CTC chưa đạt tối đa 16 tín chỉ.\n2. Sinh viên CTA chưa đạt tối đa 16 tín chỉ."
    )
    prepared = prepare(
        "Sinh viên CTA chưa đạt bị giới hạn thế nào?", [replace(_chunk(), text=text)]
    )
    assert len(prepared.passages) == 1 and "CTA" in prepared.passages[0].text


def test_backend_assigns_source_id_and_ignores_freeform_model_answer():
    config = _config()
    config.generation.response_policy = "verified_passages"
    first = replace(_chunk(), chunk_id="other", text="Học phần không liên quan.")
    second = replace(_chunk(), chunk_id="cap", text="Học kỳ hè tối đa 12 tín chỉ.")

    class Selector(FakeGenerator):
        def generate(self, prompt):
            ids = [p["passage_id"] for p in json.loads(prompt)["passages"] if "12" in p["text"]]
            return GeneratedAnswer(
                "answered", "Invented URL/page/threshold", (), "raw", passage_ids=tuple(ids)
            )

    service = AnswerService(config, FakeEmbedder(), FakeRetriever([first, second]), Selector(None))
    result = service.ask("Học kỳ hè tối đa bao nhiêu tín chỉ?")
    assert result.status == "answered" and result.answer == "“Học kỳ hè tối đa 12 tín chỉ.” [S1]"
    assert len(result.sources) == 1 and result.sources[0].chunk_id == "cap"
    assert result.sources[0].cited
    assert result.evidence_passages[0].cited


def test_low_memory_mode_releases_models_even_when_generation_raises():
    config = _config()
    config.generation.response_policy = "verified_passages"
    config.generation.low_memory_mode = True
    events = []

    class Retriever(FakeRetriever):
        def release_models(self):
            events.append("retrieval_release")

    class Generator(FakeGenerator):
        def generate(self, prompt):
            assert events == ["retrieval_release"]
            raise RuntimeError("Model unavailable")

        def release(self):
            events.append("generation_release")

    service = AnswerService(config, FakeEmbedder(), Retriever([_chunk()]), Generator(None))
    with pytest.raises(RuntimeError, match="unavailable"):
        service.ask("Evidence text?")
    assert events == ["retrieval_release", "generation_release", "retrieval_release"]
