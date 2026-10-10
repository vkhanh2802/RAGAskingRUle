from dataclasses import replace

from regularag.generation.prompt import build_prompt, focus_evidence, prepare_context
from tests.unit.generation.test_service import _chunk


def test_context_budget_drops_lower_ranked_source_before_truncating_evidence() -> None:
    first = replace(_chunk(), text="Highest-ranked evidence. " * 100)
    second = replace(_chunk(), chunk_id="doc:chunk:0001", text="Lower-ranked evidence. " * 100)
    limit = len(build_prompt("Question", [first]))

    context = prepare_context("Question", [first, second], limit, len)

    assert len(context.chunks) == 1
    assert context.chunks[0].text == first.text
    assert context.input_tokens <= limit
    assert "[S2]" not in context.prompt


def test_context_budget_reports_only_the_text_that_was_sent_to_the_model() -> None:
    first = replace(_chunk(), text="Evidence line. " * 200)
    limit = len(build_prompt("Question", [replace(first, text="")])) + 100

    context = prepare_context("Question", [first], limit, len)

    assert context.input_tokens <= limit
    assert first.text.startswith(context.chunks[0].text)
    assert len(context.chunks[0].text) < len(first.text)


def test_evidence_focus_keeps_neighboring_exception_and_original_provenance() -> None:
    chunk = replace(
        _chunk(),
        text="Header.\n\nOther subject.\n\nArticle 3.\n\n"
        "Thesis duration is 15 weeks.\n\n"
        "Exception: an extension requires approval.\n\nOther ending.",
    )

    focused = focus_evidence("What is the thesis duration in weeks?", chunk)

    assert "Thesis duration is 15 weeks." in focused.text
    assert "Exception: an extension requires approval." in focused.text
    assert focused.text in chunk.text
    assert focused.chunk_id == chunk.chunk_id
    assert focused.pdf_page_start == chunk.pdf_page_start


def test_reviewed_table_focus_selects_explicit_cohort_and_design_duration_without_other_rows():
    wrong = "Khóa tuyển 2012 | Thời gian thiết kế chương trình đào tạo 4,5 năm | HK 2."
    correct = (
        "Khóa tuyển 2018 | Thời gian thiết kế chương trình đào tạo 4 năm | HK 1, NH 2022-2023."
    )
    other = "Khóa tuyển 2018 | Thời gian thiết kế chương trình đào tạo 4,5 năm | HK 2."
    chunk = replace(_chunk(), text="Table schedule:\n" + "\n".join([wrong, correct, other]))
    focused = focus_evidence("Theo thông báo43 khóa2018 chương trình4năm thu ở kỳ nào?", chunk)
    assert focused.text == correct and focused.text in chunk.text
    assert focused.chunk_id == chunk.chunk_id
    ambiguous = focus_evidence("Khóa2018 thu ở kỳ nào?", chunk)
    assert ambiguous.text == chunk.text
    wrong_cohort = replace(chunk, text=wrong)
    prepared = prepare_context("Khóa2018 chương trình4năm thu ở kỳ nào?", [wrong_cohort], 4096, len)
    assert not prepared.chunks and wrong not in prepared.prompt
