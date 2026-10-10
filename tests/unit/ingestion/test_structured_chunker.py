from dataclasses import replace

from regularag.ingestion.models import ParsedPage
from regularag.ingestion.structured_chunker import structured_chunks
from tests.unit.ingestion.fakes import WordTokenizer


def _page(number: int, text: str, publishable: bool = True) -> ParsedPage:
    return ParsedPage(
        "doc",
        number,
        str(number),
        number + 10,
        "margin_number",
        "pymupdf_text",
        text,
        text,
        tuple(text.split("\n\n")),
        publishable=publishable,
    )


def test_articles_and_cross_page_clauses_stay_separate_and_keep_numbers() -> None:
    pages = [
        _page(1, "CHƯƠNG I. Rules\n\nĐiều 1. Điều kiện\n\n1. Tối đa 12 tín chỉ."),
        _page(2, "Ngoại lệ phải được phê duyệt.\n\nĐiều 2. Thời gian\n\n1. Trong vòng 1 tháng."),
    ]
    chunks = structured_chunks("doc", pages, WordTokenizer(), 60, 70, 8)
    article_one = next(chunk for chunk in chunks if chunk.article == "1")
    article_two = next(chunk for chunk in chunks if chunk.article == "2")

    assert "12 tín chỉ" in article_one.text
    assert "Ngoại lệ" in article_one.text
    assert article_one.source_pdf_pages == (1, 2)
    assert article_one.clauses == ("1",)
    assert "1 tháng" in article_two.text
    assert "Điều 2" not in article_one.text


def test_long_clause_repeats_complete_multiline_title_without_losing_words() -> None:
    heading = "Điều 14. Điều kiện đăng ký\nhọc phần trong học kỳ hè"
    words = [f"word_{index}" for index in range(130)]
    chunks = structured_chunks(
        "doc", [_page(1, heading + "\n\n1. " + " ".join(words))], WordTokenizer(), 60, 70, 8
    )

    assert len(chunks) > 1
    assert all(chunk.text.startswith(heading) for chunk in chunks)
    assert all(chunk.token_count <= 70 for chunk in chunks)
    assert all(chunk.article == "14" and chunk.clauses == ("1",) for chunk in chunks)
    assert all(word in "\n".join(chunk.text for chunk in chunks) for word in words)


def test_excluded_page_does_not_invent_the_article_of_a_later_continuation() -> None:
    pages = [
        _page(1, "Điều 1. Old\n\n1. Known content."),
        replace(_page(2, "Điều 2. Untrusted table", False), review_status="excluded"),
        _page(3, "Continuation after an excluded page.\n\nĐiều 3. New\n\n1. New content."),
    ]
    chunks = structured_chunks("doc", pages, WordTokenizer(), 60, 70, 8)
    continuation = next(chunk for chunk in chunks if "Continuation" in chunk.text)

    assert continuation.article is None
    assert continuation.source_pdf_pages == (3,)
    assert all(2 not in chunk.source_pdf_pages for chunk in chunks)


def test_single_block_article_and_year_are_not_lost_or_mislabeled() -> None:
    pages = [
        _page(
            1,
            "Điều 2. Quyết định có hiệu lực kể từ ngày ký.\n\n"
            "Điều 3. Phạm vi\n\nÁp dụng từ năm 2024.",
        )
    ]
    chunks = structured_chunks("doc", pages, WordTokenizer(), 60, 70, 8)

    assert any(chunk.article == "2" and "có hiệu lực" in chunk.text for chunk in chunks)
    assert all("2024" not in chunk.clauses for chunk in chunks)


def test_appendix_is_not_labeled_as_the_previous_article() -> None:
    chunks = structured_chunks(
        "doc",
        [
            _page(
                1,
                "Điều 18. Hiệu lực\n\nCó hiệu lực từ ngày ký.\n\nPhụ lục\n\n1. Quy trình bổ sung.",
            )
        ],
        WordTokenizer(),
        60,
        70,
        8,
    )
    appendix = next(chunk for chunk in chunks if "Phụ lục" in chunk.text)

    assert appendix.article is None
    assert appendix.chapter is None
