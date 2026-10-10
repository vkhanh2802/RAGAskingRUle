import pytest

from regularag.generation.local import parse_generated_answer, parse_quote_selection


def test_parse_generated_answer_accepts_json_and_deduplicates_sources() -> None:
    raw_output = (
        'prefix {"status":"answered","answer":"Nội dung [S1]","source_ids":["S1","S1"]} suffix'
    )

    result = parse_generated_answer(raw_output)

    assert result.status == "answered"
    assert result.answer == "Nội dung [S1]"
    assert result.source_ids == ("S1",)


def test_parse_generated_answer_abstains_on_invalid_output() -> None:
    result = parse_generated_answer("not json")

    assert result.status == "insufficient_evidence"
    assert result.source_ids == ()


@pytest.mark.parametrize(
    "raw_output",
    [
        '{"status":[],"answer":"text","source_ids":[]}',
        '{"status":"answered","answer":"text","source_ids":["bad"]}',
        '{"status":"answered","answer":"text","source_ids":"S1"}',
        '{"status":"answered","answer":"   ","source_ids":[]}',
    ],
)
def test_parse_generated_answer_rejects_malformed_schema(raw_output: str) -> None:
    result = parse_generated_answer(raw_output)

    assert result.status == "insufficient_evidence"
    assert result.failure_reason is not None


def test_quote_selection_derives_citations_from_the_selected_evidence() -> None:
    result = parse_quote_selection(
        '{"evidence_quotes":[{"source_id":"S2","quote":"Original evidence."}]}'
    )

    assert result.status == "answered"
    assert result.source_ids == ("S2",)
    assert result.evidence_quotes[0].quote == "Original evidence."
