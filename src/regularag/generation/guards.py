import re
import unicodedata
from hashlib import sha256

from regularag.generation.clarification import folded
from regularag.retrieval.repository import RetrievedChunk

# Narrow, declared task boundaries for this UIT-regulation corpus. These are not
# a general intent classifier or a calibrated semantic confidence score.
_OUTSIDE_TASKS = (
    r"(?:uong|lieu|dieu tri).{0,60}(?:thuoc|paracetamol)|"
    r"(?:thuoc|paracetamol).{0,60}(?:uong|lieu|dieu tri)",
    r"^(?:(?:hay|vui long|ban(?: co the)?|giup toi)\s+)*"
    r"(?:viet|tao|lap trinh).{0,40}(?:ham python|code|quicksort)|"
    r"(?:viet|tao).{0,30}(?:bai tho|truyen ngan|bai hat)",
    r"(?:dau tu|mua ban|giao dich).{0,40}(?:bitcoin|chung khoan|tien ma hoa)",
    r"phat giao thong|vuot den do|luat giao thong",
    r"mat khau.{0,30}(?:wifi|wi-fi|khoa|database)|api[_ -]?key|"
    r"(?:wifi|wi-fi).{0,30}mat khau",
    r"(?:tang|cap|ho tro).{0,30}(?:laptop|macbook)",
)
_NAMED_INSTITUTION = re.compile(
    r"\b(?:tai|cua|o)\s+(?:truong\s+)?(?:dai hoc|hoc vien)\s+"
    r"(?!cong nghe thong tin\b|chinh quy\b|tu xa\b)([a-z][a-z -]+)"
)


def unsupported_question(question: str) -> str | None:
    q = folded(question)
    if any(re.search(pattern, q) for pattern in _OUTSIDE_TASKS):
        return "outside_supported_scope"
    # A request about another named institution must not inherit UIT's thresholds.
    if _NAMED_INSTITUTION.search(q) and not (
        re.search(r"cong nhan tin chi|xin mien hoc phan", q)
        and re.search(r"(?:tai|o|cua)\s+(?:truong\s+)?(?:uit\b|dai hoc cong nghe thong tin\b)", q)
    ):
        return "outside_institution_scope"
    return None


_DOCUMENT_INSTRUCTIONS = (
    r"<\s*\|\s*(?:im_start|im_end|start_header_id|end_header_id|eot_id)[^>]*>",
    r"(?:ignore|disregard|bypass).{0,40}(?:previous|system).{0,40}(?:instructions?|prompt)",
    r"system\s+override|(?:assistant|system)\s*:",
    r"bo qua.{0,40}(?:chi dan he thong|system prompt|filters|bo loc)",
    r"chi dan cho (?:tro ly|assistant)|coi.{0,40}chi dan he thong",
    r"[\"']?(?:passage_ids|source_ids)[\"']?\s*[:=]",
)


def document_instruction(text: str) -> bool:
    # Fold only the detector view. Bound evidence text/offsets/hashes remain unchanged.
    detector = folded("".join(c for c in text if unicodedata.category(c) != "Cf"))
    return any(re.search(pattern, detector, re.S) for pattern in _DOCUMENT_INSTRUCTIONS)


def evidence_failure(chunks: list[RetrievedChunk]) -> str | None:
    for chunk in chunks:
        if (
            chunk.content_sha256
            and sha256(chunk.text.encode("utf-8")).hexdigest() != chunk.content_sha256
        ):
            return "passage_binding_mismatch"
    if any(document_instruction(chunk.text) for chunk in chunks):
        # Fail closed for the complete context; never strip an update/exception or
        # silently rebind the cleaned text to an approved source hash.
        return "untrusted_document_instruction"
    return None
