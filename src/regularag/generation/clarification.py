import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from regularag.retrieval.filters import MetadataTag, RetrievalFilters
from regularag.retrieval.keyword import build_keyword_query, normalize_vietnamese
from regularag.retrieval.repository import RetrievedChunk

Programme = Literal["ctc", "cttn", "cta", "cttt", "viet_japan"]
ScopeField = Literal[
    "cohort_year", "applies_to", "programmes", "as_of", "design_years", "project_type"
]


class QuestionScope(BaseModel):
    """Explicit question/structured scope only; no applicability inferred from issue years."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    cohort_year: int | None = Field(default=None, strict=True, ge=1980, le=2100)
    applies_to: tuple[MetadataTag, ...] = Field(default=(), max_length=20)
    programmes: tuple[Programme, ...] = Field(default=(), max_length=5)
    as_of: date | None = None
    design_years: float | None = Field(default=None, gt=0, le=10, strict=True)
    project_type: Literal["regular", "enterprise"] | None = None

    @field_validator("as_of", mode="before")
    @classmethod
    def validate_date(cls, value):
        return RetrievalFilters.validate_date(value)

    @field_validator("programmes", mode="before")
    @classmethod
    def normalize_programmes(cls, value):
        if isinstance(value, (list, tuple)):
            return tuple(item.casefold() if isinstance(item, str) else item for item in value)
        return value


@dataclass(frozen=True, slots=True)
class Clarification:
    required_fields: tuple[ScopeField, ...]
    questions: tuple[str, ...]
    conflicting_fields: tuple[ScopeField, ...] = ()


@dataclass(frozen=True, slots=True)
class ScopePlan:
    scope: QuestionScope
    filters: RetrievalFilters
    topic: str
    source_lookup: bool
    clarification: Clarification | None = None
    failure_reason: str | None = None
    current_validity: bool = False
    compare_versions: bool = False
    explicit_present: bool = False
    historical_schedule: bool = False


def folded(text: str) -> str:
    return " ".join(normalize_vietnamese(text).split())


def needs_programme(question: str) -> bool:
    q = folded(question)
    language = bool(re.search(r"ngoai ngu|tieng anh|tieng nhat|\b(?:pet|iel|jan)\d{2}\b", q))
    return bool(
        language
        and re.search(r"chuan|chua dat|gioi han", q)
        or re.search(r"chuan qua trinh|sau.{0,30}hoc ky.{0,50}(?:dat|chuan)", q)
    )


def _topic(q: str, filters: RetrievalFilters, codes: tuple[str, ...]) -> str:
    # Explicit document/domain requests take precedence over a cross-reference topic
    # in the question (e.g. foreign-language prerequisites in a thesis regulation).
    source_topics = {
        "43": "extension_tuition",
        "956": "foreign_language",
        "277": "capstone",
        "697": "capstone",
        "159": "graduation_thesis",
        "790": "academic_training",
        "1393": "academic_training",
    }
    if codes:
        topics = {source_topics.get(code, "general") for code in codes}
        return topics.pop() if len(topics) == 1 else "general"
    if len(filters.domains) == 1:
        domain = filters.domains[0]
        if domain in ("graduation_project", "graduation_project_enterprise"):
            return "capstone"
        return domain
    if re.search(r"khoa luan|\bkltn\b", q):
        return "graduation_thesis"
    if re.search(r"do an tot nghiep|do an.{0,20}doanh nghiep", q):
        return "capstone"
    if re.search(r"hoc phi gia han|phi gia han|hpgh", q):
        return "extension_tuition"
    if re.search(r"ngoai ngu|tieng anh|tieng nhat|ielts|jlpt|nat.test|\b(?:pet|iel|jan)\d{2}\b", q):
        return "foreign_language"
    if re.search(r"hoc ky he|bao luu|tam (?:ngung|nghi|dung) hoc|nghi hoc|hoc che tin chi", q):
        return "academic_training"
    return "general"


def analyse_scope(
    question: str, requested_filters: RetrievalFilters | None, supplied: QuestionScope | None
) -> ScopePlan:
    filters = requested_filters or RetrievalFilters()
    supplied = supplied or QuestionScope()
    q = folded(question)
    codes = build_keyword_query(question).document_codes
    personal = bool(
        re.search(r"\b(?:tôi|em|mình)\b", question, re.I)
        or re.search(r"\btoi\b(?!\s+(?:da|thieu)\b)|\b(?:em|minh)\b|cua ban|truong hop cua", q)
    )
    source_lookup = bool(codes or filters.document_ids or filters.domains) and not personal
    topic = _topic(q, filters, codes)
    parsed = {}
    conflicts = set()
    years = set(
        re.findall(
            r"\b(?:khoa\s*(?:tuyen\s*(?:sinh\s*)?)?|tuyen sinh)\s*(?:nam\s*)?((?:19|20)\d{2})\b", q
        )
    )
    if len(years) == 1:
        parsed["cohort_year"] = int(next(iter(years)))
    elif len(years) > 1:
        conflicts.add("cohort_year")
    audiences = []
    if re.search(r"chinh quy|\bdhcq\b|\bhe cq\b", q):
        audiences.append("undergraduate_regular")
    if re.search(r"dao tao tu xa|\bhe tu xa\b|\bhinh thuc tu xa\b", q):
        audiences.append("undergraduate_distance")
    if re.search(r"chuong trinh lien ket|he lien ket", q):
        audiences.append("joint_program")
    if audiences:
        parsed["applies_to"] = tuple(audiences)
    programmes = tuple(dict.fromkeys(re.findall(r"(?:\b|chuong trinh\s*)(ctc|cttn|cta|cttt)\b", q)))
    if re.search(r"viet\s*[-–]?\s*nhat", q):
        programmes += ("viet_japan",)
    if programmes:
        parsed["programmes"] = programmes
    if topic == "capstone":
        if re.search(r"khong.{0,15}doanh nghiep", q):
            parsed["project_type"] = "regular"
        elif "doanh nghiep" in q:
            parsed["project_type"] = "enterprise"
        elif re.search(r"thong thuong|do an thuong", q):
            parsed["project_type"] = "regular"
    duration = re.search(r"(?:chuong trinh|thiet ke)\s*(\d+(?:[,.]\d+)?)\s*nam", q)
    if duration:
        parsed["design_years"] = float(duration[1].replace(",", "."))
    when = re.search(
        r"(?:tai ngay|tinh den|vao ngay|ap dung ngay)\s*"
        r"(\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})",
        q,
    )
    invalid_date = False
    if when:
        value = when[1]
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                parsed["as_of"] = date.fromisoformat(value)
            else:
                day, month, year = map(int, re.split(r"[-/]", value))
                parsed["as_of"] = date(year, month, day)
        except ValueError:
            conflicts.add("as_of")
            invalid_date = True
    filter_scope = {
        "cohort_year": filters.cohort_year,
        "applies_to": filters.applies_to,
        "as_of": filters.as_of,
    }
    resolved = {}
    for field in QuestionScope.model_fields:
        values = [
            value
            for value in (getattr(supplied, field), filter_scope.get(field), parsed.get(field))
            if value is not None and value != ()
        ]
        if values and any(
            (set(value) != set(values[0]) if isinstance(value, tuple) else value != values[0])
            for value in values[1:]
        ):
            conflicts.add(field)
        if values:
            resolved[field] = values[0]
    scope = QuestionScope.model_validate(resolved)
    missing = []
    if not scope.as_of and re.search(
        r"(?:tai|tinh den|truoc|thoi diem|theo quy dinh)\s*nam\s*(?:19|20)\d{2}\b", q
    ):
        missing.append("as_of")
    factual_scope = bool(
        re.search(
            r"ap dung.{0,30}(?:khoa nao|tu khoa|doi tuong)|ngay.{0,20}(?:ban hanh|ky)|hieu luc", q
        )
    )
    if topic == "foreign_language" and not factual_scope:
        if not scope.cohort_year and not source_lookup:
            missing.append("cohort_year")
        if not scope.applies_to and not source_lookup and (personal or not scope.programmes):
            missing.append("applies_to")
        if needs_programme(question) and not scope.programmes:
            missing.append("programmes")
    if topic == "extension_tuition" and not (factual_scope and source_lookup):
        if not scope.cohort_year:
            missing.append("cohort_year")
        if scope.design_years is None:
            missing.append("design_years")
        if (
            not scope.as_of
            and not source_lookup
            and not re.search(r"hien nay|hien tai|bay gio|nam hoc|bat dau thu", q)
        ):
            missing.append("as_of")
    if topic == "capstone" and not codes and not filters.document_ids:
        specified_domain = set(filters.domains).intersection(
            {"graduation_project", "graduation_project_enterprise"}
        )
        if not scope.project_type and not specified_domain:
            missing.append("project_type")
        if not scope.cohort_year and personal:
            missing.append("cohort_year")
    if (
        personal
        and topic in ("capstone", "graduation_thesis", "academic_training")
        and not scope.applies_to
    ):
        missing.append("applies_to")
    questions = {
        "cohort_year": "Bạn thuộc khóa tuyển sinh năm nào?",
        "applies_to": "Bạn học hệ chính quy, đào tạo từ xa hay chương trình liên kết?",
        "programmes": "Bạn thuộc CTC/CTTN, CTA, CTTT hay CNTT Việt–Nhật?",
        "as_of": "Bạn muốn đối chiếu tại ngày nào (YYYY-MM-DD)?",
        "design_years": "Thời gian thiết kế chương trình của bạn là bao nhiêu năm (3,5; 4; 4,5…)?",
        "project_type": "Bạn hỏi đồ án tốt nghiệp thông thường hay đồ án tại doanh nghiệp?",
    }
    required = tuple(dict.fromkeys(missing + sorted(conflicts)))
    clarification = None
    if required:
        prompts = tuple(questions[field] for field in required)
        if conflicts:
            prompts = (
                "Thông tin trong câu hỏi, scope và filters đang mâu thuẫn; vui lòng xác nhận lại.",
            ) + prompts
        clarification = Clarification(required, prompts, tuple(sorted(conflicts)))
    effective = filters.model_dump()
    if scope.applies_to and not filters.applies_to:
        effective["applies_to"] = scope.applies_to
    if scope.as_of and not filters.as_of:
        effective["as_of"] = scope.as_of
    if not filters.domains and topic in ("foreign_language", "extension_tuition"):
        effective["domains"] = (topic,)
    if (
        topic in ("foreign_language", "extension_tuition", "capstone")
        and scope.cohort_year
        and not filters.cohort_year
    ):
        effective["cohort_year"] = scope.cohort_year
    if topic == "capstone" and scope.project_type and not filters.domains:
        effective["domains"] = (
            "graduation_project_enterprise"
            if scope.project_type == "enterprise"
            else "graduation_project",
        )
    validity = bool(
        re.search(
            r"(?:con|dang).{0,20}hieu luc|van ban.{0,25}hien hanh|hieu luc hien tai|"
            r"hieu luc.{0,25}(?:hien nay|hien tai|bay gio)",
            q,
        )
    )
    compare = bool(
        re.search(r"so sanh|khac biet|khac nhau", q)
        and (len(codes) >= 2 or re.search(r"van ban|phien ban|quyet dinh|hieu luc|hai nguon", q))
    )
    return ScopePlan(
        scope,
        RetrievalFilters.model_validate(effective),
        topic,
        source_lookup,
        clarification,
        "invalid_scope_date"
        if invalid_date
        else "conflicting_scope"
        if conflicts
        else "missing_scope"
        if missing
        else None,
        validity,
        compare,
        bool(re.search(r"hien nay|hien tai|bay gio", q)),
        bool(re.search(r"bat dau thu|nam hoc\s*\d{4}\s*[-–]\s*\d{4}", q)),
    )


@dataclass(frozen=True, slots=True)
class VersionNote:
    source_id: str
    document_number: str
    issued_date: str | None
    document_role: str
    related_document_number: str | None
    legal_status: str
    cohort_scope: str
    effective_from_date: str | None


def version_notes(chunks: list[RetrievedChunk]) -> tuple[VersionNote, ...]:
    seen = set()
    notes = []
    for index, chunk in enumerate(chunks, 1):
        if chunk.document_id in seen:
            continue
        seen.add(chunk.document_id)
        notes.append(
            VersionNote(
                f"S{index}",
                chunk.document_number,
                chunk.issued_date,
                chunk.document_role,
                chunk.related_document_number,
                chunk.legal_status,
                chunk.cohort_scope,
                chunk.effective_from_date,
            )
        )
    return tuple(notes)


def applicability_failure(plan: ScopePlan, chunks: list[RetrievedChunk]) -> str | None:
    if plan.topic == "extension_tuition" and (
        plan.explicit_present
        or not plan.source_lookup
        and not plan.scope.as_of
        and not plan.historical_schedule
    ):
        return "current_fee_not_verified"
    if plan.current_validity and any(chunk.legal_status == "unknown" for chunk in chunks):
        return "legal_status_not_verified"
    if plan.scope.cohort_year is not None and any(
        chunk.cohort_from is not None
        and plan.scope.cohort_year < chunk.cohort_from
        or chunk.cohort_to is not None
        and plan.scope.cohort_year > chunk.cohort_to
        for chunk in chunks
    ):
        return "cohort_outside_evidence"
    return None
