from dataclasses import dataclass
from hashlib import sha256

from regularag.ingestion.models import Chunk, ParsedPage
from regularag.ingestion.tokenizer import TextTokenizer


@dataclass(frozen=True, slots=True)
class _Fragment:
    text: str
    pdf_page_number: int
    printed_page_number: int | None


def _join_fragments(fragments: list[_Fragment]) -> str:
    return "\n\n".join(fragment.text for fragment in fragments if fragment.text).strip()


def _split_long_fragment(
    fragment: _Fragment,
    tokenizer: TextTokenizer,
    token_limit: int,
) -> list[_Fragment]:
    token_ids = tokenizer.encode(fragment.text)
    if len(token_ids) <= token_limit:
        return [fragment]

    return [
        _Fragment(
            text=tokenizer.decode(token_ids[start : start + token_limit]).strip(),
            pdf_page_number=fragment.pdf_page_number,
            printed_page_number=fragment.printed_page_number,
        )
        for start in range(0, len(token_ids), token_limit)
    ]


def _trailing_overlap(
    fragments: list[_Fragment],
    tokenizer: TextTokenizer,
    overlap_tokens: int,
) -> list[_Fragment]:
    selected: list[_Fragment] = []

    for fragment in reversed(fragments):
        candidate = [fragment, *selected]
        if tokenizer.count(_join_fragments(candidate)) <= overlap_tokens:
            selected = candidate
            continue

        token_ids = tokenizer.encode(fragment.text)
        low, high = 1, len(token_ids)
        best: _Fragment | None = None
        while low <= high:
            midpoint = (low + high) // 2
            partial = _Fragment(
                text=tokenizer.decode(token_ids[-midpoint:]).strip(),
                pdf_page_number=fragment.pdf_page_number,
                printed_page_number=fragment.printed_page_number,
            )
            if tokenizer.count(_join_fragments([partial, *selected])) <= overlap_tokens:
                best = partial
                low = midpoint + 1
            else:
                high = midpoint - 1
        if best and best.text:
            selected = [best, *selected]
        break

    return selected


def _make_chunk(
    document_id: str,
    chunk_index: int,
    fragments: list[_Fragment],
    tokenizer: TextTokenizer,
) -> Chunk:
    text = _join_fragments(fragments)
    pdf_pages = tuple(dict.fromkeys(fragment.pdf_page_number for fragment in fragments))
    printed_pages = tuple(
        dict.fromkeys(
            fragment.printed_page_number
            for fragment in fragments
            if fragment.printed_page_number is not None
        )
    )
    return Chunk(
        document_id=document_id,
        chunk_id=f"{document_id}:chunk:{chunk_index:04d}",
        chunk_index=chunk_index,
        text=text,
        token_count=tokenizer.count(text),
        pdf_page_start=min(pdf_pages),
        pdf_page_end=max(pdf_pages),
        printed_page_start=printed_pages[0] if printed_pages else None,
        printed_page_end=printed_pages[-1] if printed_pages else None,
        source_pdf_pages=pdf_pages,
        source_printed_pages=printed_pages,
        content_sha256=sha256(text.encode("utf-8")).hexdigest(),
    )


def _merge_short_tail(
    chunks: list[Chunk],
    tokenizer: TextTokenizer,
    minimum_chunk_tokens: int,
    maximum_chunk_tokens: int,
    overlap_tokens: int,
) -> list[Chunk]:
    if len(chunks) < 2 or chunks[-1].token_count >= minimum_chunk_tokens:
        return chunks

    previous, tail = chunks[-2:]
    previous_token_ids = tokenizer.encode(previous.text)
    tail_token_ids = tokenizer.encode(tail.text)
    exact_overlap = 0
    for size in range(min(overlap_tokens, len(previous_token_ids), len(tail_token_ids)), 0, -1):
        if previous_token_ids[-size:] == tail_token_ids[:size]:
            exact_overlap = size
            break

    unique_tail = tokenizer.decode(tail_token_ids[exact_overlap:]).strip()
    merged_text = f"{previous.text}\n\n{unique_tail}" if unique_tail else previous.text
    merged_token_count = tokenizer.count(merged_text)
    if merged_token_count > maximum_chunk_tokens:
        return chunks

    pdf_pages = tuple(dict.fromkeys((*previous.source_pdf_pages, *tail.source_pdf_pages)))
    printed_pages = tuple(
        dict.fromkeys((*previous.source_printed_pages, *tail.source_printed_pages))
    )
    merged = Chunk(
        document_id=previous.document_id,
        chunk_id=previous.chunk_id,
        chunk_index=previous.chunk_index,
        text=merged_text,
        token_count=merged_token_count,
        pdf_page_start=min(pdf_pages),
        pdf_page_end=max(pdf_pages),
        printed_page_start=printed_pages[0] if printed_pages else None,
        printed_page_end=printed_pages[-1] if printed_pages else None,
        source_pdf_pages=pdf_pages,
        source_printed_pages=printed_pages,
        content_sha256=sha256(merged_text.encode("utf-8")).hexdigest(),
    )
    return [*chunks[:-2], merged]


def chunk_pages(
    document_id: str,
    pages: list[ParsedPage],
    tokenizer: TextTokenizer,
    chunk_size_tokens: int,
    chunk_overlap_tokens: int,
    minimum_chunk_tokens: int | None = None,
    maximum_chunk_tokens: int | None = None,
) -> list[Chunk]:
    if chunk_size_tokens <= 0:
        raise ValueError("chunk size must be positive")
    if not 0 <= chunk_overlap_tokens < chunk_size_tokens:
        raise ValueError("chunk overlap must be non-negative and smaller than chunk size")
    minimum_chunk_tokens = minimum_chunk_tokens or chunk_size_tokens
    maximum_chunk_tokens = maximum_chunk_tokens or chunk_size_tokens
    if minimum_chunk_tokens > chunk_size_tokens:
        raise ValueError("minimum chunk size cannot exceed target chunk size")
    if maximum_chunk_tokens < chunk_size_tokens:
        raise ValueError("maximum chunk size cannot be smaller than target chunk size")

    fragment_limit = chunk_size_tokens - chunk_overlap_tokens
    fragments = [
        split_fragment
        for page in pages
        for block in page.blocks
        for split_fragment in _split_long_fragment(
            _Fragment(block, page.pdf_page_number, page.printed_page_number),
            tokenizer,
            fragment_limit,
        )
    ]

    chunks: list[Chunk] = []
    current: list[_Fragment] = []

    for fragment in fragments:
        candidate = [*current, fragment]
        if current and tokenizer.count(_join_fragments(candidate)) > chunk_size_tokens:
            chunks.append(_make_chunk(document_id, len(chunks), current, tokenizer))
            current = _trailing_overlap(current, tokenizer, chunk_overlap_tokens)
            while (
                current
                and tokenizer.count(_join_fragments([*current, fragment])) > chunk_size_tokens
            ):
                current.pop(0)
        current.append(fragment)

    if current:
        chunks.append(_make_chunk(document_id, len(chunks), current, tokenizer))

    chunks = _merge_short_tail(
        chunks,
        tokenizer,
        minimum_chunk_tokens,
        maximum_chunk_tokens,
        chunk_overlap_tokens,
    )
    if any(chunk.token_count > maximum_chunk_tokens for chunk in chunks):
        raise RuntimeError("chunker produced a chunk larger than the configured limit")
    return chunks
