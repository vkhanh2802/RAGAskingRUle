import json
import math
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date
from hashlib import sha256
from itertools import combinations

from regularag.generation.clarification import QuestionScope, needs_programme
from regularag.generation.guards import evidence_failure
from regularag.retrieval.keyword import normalize_vietnamese
from regularag.retrieval.repository import RetrievedChunk

_BOUNDARY = re.compile(r"(?m)^(?:Điều\s+\d+[a-z]?\.|\d+(?:\.\d+)*[.)]\s)")
_SIGNATURE = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.I)
_STOP = {
    "theo",
    "quyet",
    "dinh",
    "quy",
    "cua",
    "cac",
    "duoc",
    "cho",
    "voi",
    "trong",
    "tu",
    "toi",
    "la",
    "gi",
    "nao",
    "bao",
    "nhieu",
    "va",
    "hoac",
    "hay",
    "neu",
    "khi",
    "ve",
    "phai",
    "mot",
    "co",
    "sinh",
    "vien",
    "truong",
    "ngay",
    "nam",
    "so",
    "tai",
}


@dataclass(frozen=True, slots=True)
class EvidencePassage:
    passage_id: str
    source_id: str
    chunk_id: str
    char_start: int
    char_end: int
    text: str
    text_sha256: str
    required_passage_ids: tuple[str, ...] = ()
    cited: bool = False


@dataclass(frozen=True, slots=True)
class PreparedPassages:
    prompt: str
    chunks: tuple[RetrievedChunk, ...]
    passages: tuple[EvidencePassage, ...]
    input_tokens: int
    failure_reason: str | None = None


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", normalize_vietnamese(text))) - _STOP


def _fold(text: str) -> str:
    return " ".join(normalize_vietnamese(text).split())


def support_facets(question: str) -> dict[str, str]:
    """Declared lexical support checks, not an entailment/confidence estimator."""
    q = _fold(question)
    facets = {}
    numeric = bool(re.search(r"bao\s*nhieu|may|toi\s*da|toi\s*thieu", q))
    amount = r"(?:\d+(?:[,.]\d+)?|mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi)\s*"
    if numeric:
        for name, unit in (
            ("credits", r"tin\s*chi"),
            ("students", r"sinh\s*vien"),
            ("hours", r"gio"),
            ("days", r"ngay"),
            ("weeks", r"tuan"),
            ("minutes", r"phut"),
            ("years", r"nam"),
            ("topics", r"de\s*tai"),
            ("sessions", r"dot"),
        ):
            asks_unit = bool(re.search(unit, q))
            if name in ("weeks", "minutes", "years", "topics", "sessions"):
                asks_unit = bool(
                    re.search(r"(?:bao\s*nhieu|may|toi\s*da|toi\s*thieu)\s*" + unit, q)
                )
            if name == "students":
                asks_unit = bool(
                    re.search(
                        r"(?:bao\s*nhieu|may|toi\s*thieu|toi\s*da|so\s*luong|it\s*nhat).{0,30}sinh\s*vien",
                        q,
                    )
                )
            if asks_unit:
                measure = amount + (r"(?:sinh\s*vien|sv\b)" if name == "students" else unit)
                if name == "credits":
                    measure = "(?:" + measure + r"|so luong tin chi.{0,50}\d+(?:[,.]\d+)?)"
                facets[name] = measure
    if "hieu luc" in q:
        facets["effective_date"] = r"hieu luc.{0,120}(?:ngay|ky|hoc ky)"
    if re.search(r"thoi\s*han|trong\s*bao\s*lau", q):
        facets["deadline"] = amount + r"(?:ngay|thang|tuan|nam|hoc\s*ky)"
    if re.search(r"nhan\s*diem|diem\s*gi", q):
        facets["grade"] = r"diem\s+(?:khong\s*\(0\)|[a-z]\b|\d)"
    if "truc tuyen" in q:
        facets["online_scope"] = r"truc tuyen"
    if "hoc ky he" in q:
        facets["summer_period"] = r"hoc ky he"
    if "dai cuong" in q and "co so nganh" in q:
        facets["course_group"] = r"dai cuong.*co so nganh"
    if re.search(r"nhom.{0,40}(?:nao|gi)|chi ap dung.{0,30}nhom", q):
        facets["group"] = r"nhom\s+(?:hoc\s*phan|mon|sinh)"
    if "van bang giay" in q:
        facets["paper_degree"] = r"van bang giay.{0,100}\d+\s*ngay"
    if "van bang so" in q or "vbcc so" in q:
        facets["digital_degree"] = r"(?:vbcc|van bang) so.{0,100}\d+\s*ngay"
    if "cbhd" in q and "cbpb" in q and re.search(r"dong thoi|khac|la cbhd", q):
        facets["distinct_reviewer"] = r"cbpb.{0,80}(?:khac|khong).{0,40}cbhd"
    if "ruot thit" in q:
        facets["family_condition"] = r"ruot thit"
    if re.search(r"viet\s*[-–]?\s*nhat", q):
        facets["program"] = r"viet\s*[-–]?\s*nhat"
        if re.search(r"chua\s*dat|gioi\s*han", q):
            facets["unmet_limit"] = r"(?:chua dat|toi da).{0,300}\d+\s*tin chi"
    programs = re.findall(r"\b(?:ctc|cttn|cta|cttt)\b", q)
    if programs:
        facets["named_program"] = r"\b(?:" + "|".join(programs) + r")\b"
        if re.search(r"chua dat|gioi han", q):
            facets["unmet_limit"] = r"(?:chua dat|toi da).{0,300}\d+\s*tin chi"
    if "dieu kien" in q:
        facets["conditions"] = r"dieu kien"
    for term, name in (("dinh chi", "suspension"), ("giua ky", "midterm")):
        if term in q:
            facets[name] = re.escape(term)
    if re.search(r"cac thang|thang nao", q):
        facets["schedule_months"] = r"thang\s*\d"
    if "he so" in q:
        facets["weighting"] = r"he so"
    if "lam tron" in q:
        facets["rounding"] = r"lam tron"
    course = re.search(r"\b(?:pet|iel|jan)\d{2}\b", q)
    if course and ("tien quyet" in q or "dang ky" in q and re.search(r"can dat|phai dat", q)):
        # A progress deadline mentioning the same course is not a prerequisite edge.
        facets["prerequisite"] = (
            r"tien quyet cua.{0,50}\b" + re.escape(course[0]) + r"\b|"
            r"phai dat.{0,100}moi.{0,30}dang ky.{0,50}\b" + re.escape(course[0]) + r"\b"
        )
        facets["requested_course"] = re.escape(course[0])
    if re.search(r"ap dung.{0,30}(?:tu khoa|khoa nao)|bat buoc.{0,30}khoa", q):
        facets["declared_cohort_scope"] = (
            r"\bkhoa(?:\s+tuyen(?:\s+sinh)?)?\s*(?:tu\s*(?:nam\s*)?|nam\s*)?(?:19|20)\d{2}\b"
        )
    if numeric and re.search(r"do an.{0,40}tin chi", q) and not re.search(r"no tin chi|dang ky", q):
        facets["module_credit_count"] = r"so luong tin chi|khoi luong.{0,50}tin chi"
    return facets


def scoped_facets(question: str, scope: QuestionScope | None = None) -> dict[str, str]:
    facets = support_facets(question)
    if scope and scope.programmes and needs_programme(question):
        for programme in scope.programmes:
            facets[f"scope_programme_{programme}"] = (
                r"viet\s*[-–]?\s*nhat" if programme == "viet_japan" else rf"\b{programme}\b"
            )
        if re.search(r"chua dat|gioi han", _fold(question)):
            facets["unmet_limit"] = r"(?:chua dat|toi da).{0,300}\d+\s*tin chi"
    return facets


def missing_support(
    question: str, passages: list[EvidencePassage], scope: QuestionScope | None = None
) -> tuple[str, ...]:
    text = " ".join(_fold(p.text) for p in passages)
    return tuple(
        name
        for name, pattern in scoped_facets(question, scope).items()
        if not re.search(pattern, text, re.S)
    )


def _ranges(
    question: str, chunk: RetrievedChunk, scope: QuestionScope | None = None
) -> list[tuple[int, int]]:
    text = chunk.text
    q = normalize_vietnamese(question)
    if "dieu kien" in q and re.match(r"Điều\s+\d+\.\s*Điều kiện", text):
        return [(0, len(text))]  # Preserve all requirements, including grading and age limits.
    row_matches = list(re.finditer(r"(?m)^Khóa tuyển .+\|.+$", text))
    cohort = re.search(r"\bkhoa\s*(?:tuyen\s*)?(\d{4})\b", q)
    duration = re.search(r"(\d+(?:[,.]\d+)?)\s*nam\b", q)
    if row_matches:
        cohort_year = (
            scope.cohort_year if scope and scope.cohort_year else int(cohort[1]) if cohort else None
        )
        if cohort_year:
            row_matches = [
                m for m in row_matches if m[0].startswith(f"Khóa tuyển {cohort_year} | ")
            ]
        design_years = scope.design_years if scope else None
        if design_years is not None or duration:
            years = (f"{design_years:g}" if design_years is not None else duration[1]).replace(
                ".", ","
            )
            row_matches = [m for m in row_matches if f"chương trình đào tạo {years} năm | " in m[0]]
        return [(m.start(), m.end()) for m in row_matches]
    signatures = []
    if re.search(r"hieu luc|ngay\s*ky|ngay\s*ban\s*hanh", q):
        for signature in _SIGNATURE.finditer(text):
            try:
                issued = date(int(signature[3]), int(signature[2]), int(signature[1]))
            except ValueError:
                continue
            if issued.isoformat() == chunk.issued_date:
                signatures.append((signature.start(), signature.end()))
    starts = [m.start() for m in _BOUNDARY.finditer(text)]
    if not starts:
        # Preserve complete paragraphs, including the surrounding conditions of a bullet list.
        starts = [0] + [m.end() for m in re.finditer(r"\n\s*\n", text)]
    elif starts[0] != 0:
        starts.insert(0, 0)
    ends = starts[1:] + [len(text)]
    ranges = list(zip(starts, ends, strict=True))
    if len(ranges) > 1:
        first = text[ranges[0][0] : ranges[0][1]].strip()
        # An article heading on its own is not an answer; bind it to the first complete clause.
        if re.fullmatch(r"Điều\s+\d+[a-z]?\.[^\n]+", first) and not re.search(
            r"hiệu lực|kể từ|\d+\s*(?:ngày|tín chỉ)", first, re.I
        ):
            ranges = [(ranges[0][0], ranges[1][1])] + ranges[2:]
    return list(dict.fromkeys(signatures + ranges))


def _trim_range(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _prompt(
    question: str,
    chunks: list[RetrievedChunk],
    passages: list[EvidencePassage],
    scope: QuestionScope | None = None,
) -> str:
    lookup = {f"S{i}": chunk for i, chunk in enumerate(chunks, 1)}
    return json.dumps(
        {
            "question": question,
            "scope": scope.model_dump(mode="json") if scope else {},
            "passages": [
                {
                    "passage_id": p.passage_id,
                    "document": lookup[p.source_id].document_number,
                    "article": lookup[p.source_id].article,
                    "text": p.text,
                }
                for p in passages
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def prepare_passages(
    question: str,
    chunks: list[RetrievedChunk],
    token_limit: int,
    count_tokens: Callable[[str], int],
    max_passages: int,
    scope: QuestionScope | None = None,
) -> PreparedPassages:
    if reason := evidence_failure(chunks):
        return PreparedPassages("", tuple(chunks), (), 0, reason)
    candidates = []
    for chunk_index, chunk in enumerate(chunks):
        digest = sha256(chunk.text.encode("utf-8")).hexdigest()
        if chunk.content_sha256 and digest != chunk.content_sha256:
            return PreparedPassages("", tuple(chunks), (), 0, "passage_binding_mismatch")
        for start, end in _ranges(question, chunk, scope):
            start, end = _trim_range(chunk.text, start, end)
            if start == end:
                continue
            text = chunk.text[start:end]
            candidates.append((chunk_index, start, end, text, _terms(text)))
    frequencies = Counter(term for *_, terms in candidates for term in terms)
    query_terms = _terms(question)
    facets = scoped_facets(question, scope)
    scored = []
    coverage_sets = {}
    for index, candidate in enumerate(candidates):
        *_, text, terms = candidate
        lexical = sum(math.log(1 + len(candidates) / frequencies[t]) for t in terms & query_terms)
        coverage_sets[index] = {
            name for name, pattern in facets.items() if re.search(pattern, _fold(text), re.S)
        }
        # Keep the already measured semantic chunk ranking as the primary source prior.
        score = lexical + 8 * len(coverage_sets[index]) - 6 * candidate[0]
        scored.append((score, index))
    order = [
        index
        for _, index in sorted(scored, key=lambda pair: (-pair[0], candidates[pair[1]][0], pair[1]))
    ]
    complete = [i for i in order if facets and set(facets).issubset(coverage_sets[i])]
    if complete:
        # Present complete answer blocks instead of diluting them with unrelated options.
        primary_document = chunks[candidates[complete[0]][0]].document_id
        selected = [
            i for i in complete if chunks[candidates[i][0]].document_id == primary_document
        ][: min(2, max_passages)]
    elif facets:
        selected = []
        remaining = set(facets)
        available = list(order)
        while remaining and available and len(selected) < max_passages:
            best = max(available, key=lambda i: len(coverage_sets[i] & remaining))
            if not coverage_sets[best] & remaining:
                break
            selected.append(best)
            remaining -= coverage_sets[best]
            available.remove(best)
        if remaining:
            return PreparedPassages("", tuple(chunks), (), 0, "missing_support_candidates")
    else:
        rows = [i for i in order if candidates[i][3].startswith("Khóa tuyển ")]
        selected = rows[:max_passages] if rows else order[: min(4, max_passages)]
    if "effective_date" in facets:
        # Keep literal signature evidence for source-declared 'from signature' dates.
        for index in list(selected):
            owner = chunks[candidates[index][0]]
            if not re.search(
                r"hieu luc.*ngay ky", normalize_vietnamese(candidates[index][3]), re.S
            ):
                continue
            signatures = [
                i
                for i in order
                if chunks[candidates[i][0]].document_id == owner.document_id
                and _SIGNATURE.search(candidates[i][3])
            ]
            if signatures:
                selected.append(min(signatures, key=lambda i: len(candidates[i][3])))
        selected = list(dict.fromkeys(selected))

    def materialize(indices):
        owners = {candidates[index][0] for index in indices}
        selected_chunks = [chunk for index, chunk in enumerate(chunks) if index in owners]
        source_ids = {index: f"S{rank}" for rank, index in enumerate(sorted(owners), 1)}
        passages = [
            EvidencePassage(
                f"P{rank}",
                source_ids[candidates[index][0]],
                chunks[candidates[index][0]].chunk_id,
                candidates[index][1],
                candidates[index][2],
                candidates[index][3],
                sha256(candidates[index][3].encode("utf-8")).hexdigest(),
            )
            for rank, index in enumerate(indices, 1)
        ]
        # Source-declared 'from signature' needs literal signature evidence to answer a date.
        if "effective_date" in facets:
            for index, passage in enumerate(passages):
                if re.search(
                    r"hieu luc.*(?:ngay ky|ke tu.*ky)", normalize_vietnamese(passage.text), re.S
                ):
                    owner = selected_chunks[int(passage.source_id[1:]) - 1]
                    signatures = [
                        p
                        for p in passages
                        if _SIGNATURE.search(p.text)
                        and selected_chunks[int(p.source_id[1:]) - 1].document_id
                        == owner.document_id
                    ]
                    passages[index] = replace(
                        passage,
                        required_passage_ids=(
                            min(signatures, key=lambda p: len(p.text)).passage_id,
                        )
                        if signatures
                        else (),
                    )
        return selected_chunks, passages

    while selected:
        selected_chunks, passages = materialize(selected)
        # Reserve a complete passage from every required update before adding lower-ranked options.
        required = {cid for chunk in selected_chunks for cid in chunk.required_update_chunk_ids}
        presented = {p.chunk_id for p in passages}
        missing = required - presented
        if missing:
            additions = [
                next((i for i in order if chunks[candidates[i][0]].chunk_id == cid), None)
                for cid in sorted(missing)
            ]
            if any(i is None for i in additions):
                return PreparedPassages("", tuple(selected_chunks), (), 0, "latest_not_in_context")
            selected = list(
                dict.fromkeys(selected[: max(1, max_passages - len(additions))] + additions)
            )
            selected_chunks, passages = materialize(selected)
        prompt = _prompt(question, selected_chunks, passages, scope)
        tokens = count_tokens(prompt)
        if tokens <= token_limit:
            return PreparedPassages(prompt, tuple(selected_chunks), tuple(passages), tokens)
        if len(selected) == 1:
            break  # Never truncate an atomic condition/exception block to make it fit.
        # Remove a lower-ranked non-companion; if only the base/update pair is too big, abstain.
        required = {cid for chunk in selected_chunks for cid in chunk.required_update_chunk_ids}
        removable = [
            i for i in reversed(selected) if chunks[candidates[i][0]].chunk_id not in required
        ]
        if not removable:
            break
        selected.remove(removable[0])
    return PreparedPassages(
        "", tuple(chunks), (), 0, "passage_budget_exceeded" if candidates else "no_scoped_passage"
    )


def resolve_passages(
    question: str,
    selected_ids: tuple[str, ...],
    prepared: PreparedPassages,
    scope: QuestionScope | None = None,
    minimize: bool = False,
) -> tuple[list[EvidencePassage], str | None]:
    if reason := evidence_failure(list(prepared.chunks)):
        return [], reason
    lookup = {p.passage_id: p for p in prepared.passages}
    if len(set(selected_ids)) != len(selected_ids) or any(
        pid not in lookup for pid in selected_ids
    ):
        return [], "invalid_passage_ids"
    if not selected_ids:
        return [], None
    selected = [lookup[pid] for pid in selected_ids]
    for passage in list(selected):
        for required in passage.required_passage_ids:
            if required not in lookup:
                return [], "required_passage_not_in_context"
            if required not in {p.passage_id for p in selected}:
                selected.append(lookup[required])
        if (
            "effective_date" in support_facets(question)
            and re.search(r"hieu luc.*ngay ky", normalize_vietnamese(passage.text), re.S)
            and not passage.required_passage_ids
        ):
            return [], "missing_signature_evidence"
    chunks = {chunk.chunk_id: chunk for chunk in prepared.chunks}
    for passage in selected:
        chunk = chunks.get(passage.chunk_id)
        if (
            chunk is None
            or not 0 <= passage.char_start < passage.char_end <= len(chunk.text)
            or passage.source_id not in {f"S{i}" for i in range(1, len(prepared.chunks) + 1)}
            or prepared.chunks[int(passage.source_id[1:]) - 1].chunk_id != passage.chunk_id
            or chunk.text[passage.char_start : passage.char_end] != passage.text
            or sha256(passage.text.encode("utf-8")).hexdigest() != passage.text_sha256
        ):
            return [], "passage_binding_mismatch"
    if missing_support(question, selected, scope):
        return [], "incomplete_passage_support"
    if not support_facets(question) and not _terms(question).intersection(
        _terms(" ".join(p.text for p in selected))
    ):
        return [], "unsupported_passage_topic"
    selected.sort(key=lambda p: int(p.passage_id[1:]))
    if minimize:
        # Only prune model-selected evidence; never substitute an unselected answer or
        # remove a source-bound condition/signature dependency. No calibrated confidence.
        facets = scoped_facets(question, scope)
        query_terms = _terms(question)
        for count in range(1, len(selected) + 1):
            reduced = None
            for subset in combinations(selected, count):
                ids = {p.passage_id for p in subset}
                if any(not set(p.required_passage_ids).issubset(ids) for p in subset):
                    continue
                if facets and not missing_support(question, list(subset), scope):
                    reduced = list(subset)
                    break
                text_terms = _terms(" ".join(p.text for p in subset))
                if not facets and len(query_terms) >= 3 and query_terms.issubset(text_terms):
                    reduced = list(subset)
                    break
            if reduced is not None:
                selected = reduced
                break
    return selected, None
