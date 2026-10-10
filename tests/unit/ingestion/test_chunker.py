from regularag.ingestion.chunker import chunk_pages
from regularag.ingestion.models import ParsedPage
from tests.unit.ingestion.fakes import WordTokenizer


def _page(page_number: int, words: list[str]) -> ParsedPage:
    text = " ".join(words)
    return ParsedPage(
        document_id="doc_test",
        pdf_page_number=page_number,
        pdf_page_label=str(page_number),
        printed_page_number=page_number + 4,
        printed_page_source="margin_number",
        extraction_method="pymupdf_text",
        raw_text=text,
        cleaned_text=text,
        blocks=(text,),
    )


def test_chunk_pages_enforces_limit_overlap_and_page_mapping() -> None:
    tokenizer = WordTokenizer()
    pages = [
        _page(1, [f"page1_word_{index}" for index in range(35)]),
        _page(2, [f"page2_word_{index}" for index in range(35)]),
        _page(3, [f"page3_word_{index}" for index in range(35)]),
    ]

    chunks = chunk_pages(
        "doc_test",
        pages,
        tokenizer,
        chunk_size_tokens=50,
        chunk_overlap_tokens=10,
    )

    assert len(chunks) == 3
    assert all(chunk.token_count <= 50 for chunk in chunks)
    assert chunks[0].chunk_id == "doc_test:chunk:0000"
    assert chunks[0].pdf_page_start == 1
    assert chunks[0].pdf_page_end == 1
    assert chunks[1].source_pdf_pages == (1, 2)
    assert chunks[1].printed_page_start == 5
    assert chunks[1].printed_page_end == 6
    assert tokenizer.encode(chunks[0].text)[-10:] == tokenizer.encode(chunks[1].text)[:10]


def test_chunk_pages_rejects_invalid_overlap() -> None:
    tokenizer = WordTokenizer()

    try:
        chunk_pages("doc_test", [], tokenizer, 100, 100)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("invalid overlap must raise ValueError")


def test_chunk_pages_merges_small_tail_within_hard_limit() -> None:
    tokenizer = WordTokenizer()
    pages = [
        _page(1, [f"first_{index}" for index in range(45)]),
        _page(2, [f"tail_{index}" for index in range(10)]),
    ]

    chunks = chunk_pages(
        "doc_test",
        pages,
        tokenizer,
        chunk_size_tokens=50,
        chunk_overlap_tokens=10,
        minimum_chunk_tokens=30,
        maximum_chunk_tokens=60,
    )

    assert len(chunks) == 1
    assert chunks[0].token_count == 55
    assert chunks[0].source_pdf_pages == (1, 2)
