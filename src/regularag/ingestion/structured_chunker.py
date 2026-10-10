import re
from dataclasses import dataclass, replace
from hashlib import sha256

from regularag.ingestion.models import Chunk, ParsedPage
from regularag.ingestion.tokenizer import TextTokenizer

_CHAPTER = re.compile(r"^CHƯƠNG\s+([IVXLCDM]+|\d+)\b", re.I)
_ARTICLE = re.compile(r"^Điều\s+(\d+[a-z]?)[.:]?\s", re.I)
_CLAUSE = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){0,2})[.)](?:\s+|$)")


@dataclass(frozen=True, slots=True)
class Fragment:
    text: str
    page: ParsedPage
    clause: str | None = None
    kind: str = "body"


@dataclass
class Section:
    chapter: str | None
    article: str | None
    heading: Fragment | None
    units: list[list[Fragment]]


def _text(fragments: list[Fragment]) -> str:
    return "\n".join(fragment.text for fragment in fragments).strip()


def _sections(pages: list[ParsedPage]) -> list[Section]:
    sections = []
    chapter = None
    article = None
    heading = None
    units: list[list[Fragment]] = []
    current_clause = None

    def flush() -> None:
        nonlocal units
        if units or heading:
            sections.append(Section(chapter, article, heading, units))
            units = []

    for page in pages:
        if not page.publishable:
            flush()
            chapter = None
            article = None
            heading = None
            current_clause = None
            continue
        for block in page.blocks:
            lines = block.splitlines()
            consumed_until = -1
            for line_index, line in enumerate(lines):
                if line_index <= consumed_until:
                    continue
                line = line.strip()
                if not line:
                    continue
                if re.match(r"^Phụ lục\b", line, re.I):
                    flush()
                    chapter = None
                    article = None
                    heading = None
                    current_clause = None
                    units.append([Fragment(line, page)])
                    continue
                match = _CHAPTER.match(line)
                if match:
                    flush()
                    chapter = match.group(1)
                    article = None
                    heading = None
                    current_clause = None
                    units.append([Fragment(line, page)])
                    continue
                match = _ARTICLE.match(line)
                if match and not re.search(r"[.·…]{4,}", line):
                    flush()
                    article = match.group(1)
                    heading_lines = [line]
                    for continuation_index in range(line_index + 1, len(lines)):
                        continuation = lines[continuation_index].strip()
                        if (
                            _CLAUSE.match(continuation)
                            or _ARTICLE.match(continuation)
                            or _CHAPTER.match(continuation)
                            or continuation.startswith(("-", ""))
                            or len(" ".join([*heading_lines, continuation])) > 240
                        ):
                            break
                        heading_lines.append(continuation)
                        consumed_until = continuation_index
                    heading = Fragment("\n".join(heading_lines), page, kind="heading")
                    current_clause = None
                    continue
                match = _CLAUSE.match(line)
                if match:
                    current_clause = match.group(1)
                    units.append([])
                if not units:
                    units.append([])
                units[-1].append(Fragment(line, page, current_clause))
    flush()
    return sections


def _split_fragment(
    fragment: Fragment, tokenizer: TextTokenizer, token_limit: int
) -> list[Fragment]:
    remaining = fragment.text
    pieces = []
    while tokenizer.count(remaining) > token_limit:
        low, high = 1, len(remaining)
        end = 0
        while low <= high:
            midpoint = (low + high) // 2
            if tokenizer.count(remaining[:midpoint]) <= token_limit:
                end = midpoint
                low = midpoint + 1
            else:
                high = midpoint - 1
        if end == 0:
            raise ValueError("No room for source text in the structured chunk budget")
        boundary = remaining.rfind(" ", max(0, end - 120), end)
        if boundary > 0:
            end = boundary
        pieces.append(replace(fragment, text=remaining[:end].rstrip()))
        remaining = remaining[end:].lstrip()
    if remaining:
        pieces.append(replace(fragment, text=remaining))
    return pieces


def _overlap(fragments: list[Fragment], tokenizer: TextTokenizer, limit: int) -> list[Fragment]:
    selected = []
    for fragment in reversed(fragments):
        if tokenizer.count(_text([fragment, *selected])) <= limit:
            selected = [fragment, *selected]
            continue
        low, high = 1, len(fragment.text)
        best = None
        while low <= high:
            length = (low + high) // 2
            tail = replace(fragment, text=fragment.text[-length:])
            if tokenizer.count(_text([tail, *selected])) <= limit:
                best = tail
                low = length + 1
            else:
                high = length - 1
        if best:
            selected = [best, *selected]
        break
    return selected


def structured_chunks(
    document_id: str,
    pages: list[ParsedPage],
    tokenizer: TextTokenizer,
    target_tokens: int = 700,
    maximum_tokens: int = 800,
    overlap_tokens: int = 100,
) -> list[Chunk]:
    chunks = []
    for section in _sections(pages):
        prefix = [section.heading] if section.heading else []
        if tokenizer.count(_text(prefix)) >= target_tokens:
            raise ValueError("Article heading exceeds the structured chunk budget")
        groups = [] if section.units else [[]]
        current = []
        for unit in section.units:
            if tokenizer.count(_text([*prefix, *unit])) <= maximum_tokens:
                if current and tokenizer.count(_text([*prefix, *current, *unit])) > target_tokens:
                    groups.append(current)
                    current = []
                current.extend(unit)
                continue
            if current:
                groups.append(current)
                current = []
            fragment_limit = target_tokens - tokenizer.count(_text(prefix)) - overlap_tokens - 4
            if fragment_limit <= 0:
                raise ValueError("Heading and overlap leave no room for a clause")
            parts = [
                piece
                for fragment in unit
                for piece in _split_fragment(fragment, tokenizer, fragment_limit)
            ]
            for fragment in parts:
                if (
                    current
                    and tokenizer.count(_text([*prefix, *current, fragment])) > target_tokens
                ):
                    groups.append(current)
                    current = _overlap(current, tokenizer, overlap_tokens)
                while (
                    current
                    and tokenizer.count(_text([*prefix, *current, fragment])) > maximum_tokens
                ):
                    current.pop(0)
                current.append(fragment)
            if current:
                groups.append(current)
                current = []
        if current:
            groups.append(current)
        for part_index, group in enumerate(groups):
            fragments = [*prefix, *group]
            text = _text(fragments)
            page_numbers = tuple(sorted({fragment.page.pdf_page_number for fragment in fragments}))
            ordered_pages = {
                number: next(
                    fragment.page
                    for fragment in fragments
                    if fragment.page.pdf_page_number == number
                )
                for number in page_numbers
            }
            printed = tuple(
                dict.fromkeys(
                    page.printed_page_number
                    for page in ordered_pages.values()
                    if page.printed_page_number is not None
                )
            )
            count = tokenizer.count(text)
            if count > maximum_tokens:
                raise ValueError("Structured chunk exceeds the hard token ceiling")
            chunks.append(
                Chunk(
                    document_id=document_id,
                    chunk_id=f"{document_id}:chunk:{len(chunks):04d}",
                    chunk_index=len(chunks),
                    text=text,
                    token_count=count,
                    pdf_page_start=min(page_numbers),
                    pdf_page_end=max(page_numbers),
                    printed_page_start=printed[0] if printed else None,
                    printed_page_end=printed[-1] if printed else None,
                    source_pdf_pages=page_numbers,
                    source_printed_pages=printed,
                    content_sha256=sha256(text.encode("utf-8")).hexdigest(),
                    chapter=section.chapter,
                    article=section.article,
                    clauses=tuple(
                        dict.fromkeys(fragment.clause for fragment in group if fragment.clause)
                    ),
                    heading=section.heading.text if section.heading else "",
                    part_index=part_index,
                    extraction_methods=tuple(
                        dict.fromkeys(fragment.page.extraction_method for fragment in fragments)
                    ),
                    quality_flags=tuple(
                        dict.fromkeys(
                            flag for fragment in fragments for flag in fragment.page.quality_flags
                        )
                    ),
                    source_spans=tuple(
                        {
                            "pdf_page": fragment.page.pdf_page_number,
                            "printed_page": fragment.page.printed_page_number,
                            "kind": fragment.kind,
                            "extraction_method": fragment.page.extraction_method,
                            "review_status": fragment.page.review_status,
                            "text_sha256": sha256(fragment.text.encode("utf-8")).hexdigest(),
                            "text": fragment.text,
                        }
                        for fragment in fragments
                    ),
                    quality_status=(
                        "review_required"
                        if any(fragment.page.review_status == "pending" for fragment in fragments)
                        else "approved"
                    ),
                )
            )
    return chunks
