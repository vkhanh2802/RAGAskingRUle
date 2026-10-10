import re
from typing import Literal

from regularag.retrieval.keyword import normalize_vietnamese


def registration_focus(question: str) -> Literal["regular", "summer"] | None:
    q = " ".join(normalize_vietnamese(question).split())
    if not re.search(r"dang\s*k[yi]|d[kc]hp", q) or not re.search(r"tin\s*chi", q):
        return None
    grade = bool(re.search(r"diem\s*(?:trung\s*binh|tb)|\bdtbc\b|\bgpa\b", q))
    if not grade and re.search(
        r"ngoai ngu|tieng anh|tieng nhat|\b(?:pet|iel|jan)\d{2}\b|chua dat", q
    ):
        return None  # Progress/prerequisite rules are not the general GPA credit limit.
    summer = bool(re.search(r"hoc\s*ky\s*he|\bhkhe\b", q))
    regular = bool(re.search(r"hoc\s*ky\s*chinh|\bhkchinh\b", q))
    if summer and regular:
        return None  # A combined question must retain the update needed for summer.
    if summer:
        return "summer"
    if regular or grade:
        return "regular"
    return None


def has_regular_credit_rule(text: str) -> bool:
    folded = " ".join(normalize_vietnamese(text).split())
    return bool(
        re.search(r"hoc ky chinh", folded)
        and re.search(
            r"(?:dtbc|diem trung binh chung).{0,150}(?:dang ky|dang ki).{0,50}tin chi", folded
        )
    )


def regular_subitem_range(text: str) -> tuple[int, int] | None:
    """Only return a complete, explicit 1(a) before 1(b); never infer missing hierarchy."""
    parent = list(re.finditer(r"(?m)^1\.\s", text))
    a = list(re.finditer(r"(?m)^a\)\s*Trong học kỳ chính:", text))
    b = list(re.finditer(r"(?m)^b\)\s*Trong học kỳ hè:", text))
    if len(parent) != 1 or len(a) != 1 or len(b) != 1:
        return None
    if not parent[0].start() < a[0].start() < b[0].start():
        return None
    if re.search(r"(?m)^\d+\.\s", text[parent[0].end() : b[0].start()]):
        return None
    return parent[0].start(), b[0].start()
