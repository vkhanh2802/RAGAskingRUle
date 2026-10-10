import csv
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Literal

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field, model_validator

from regularag.generation.clarification import QuestionScope
from regularag.retrieval.filters import METADATA_FILTER, RetrievalFilters, filter_parameters
from regularag.retrieval.sql import READY_FILTER, retrieval_parameters

Category = Literal[
    "single_clause", "multi_clause", "temporal_scope", "no_answer", "clarification", "adversarial"
]
Split = Literal["development", "test"]
CATEGORY_COUNTS = {
    "single_clause": 30,
    "multi_clause": 20,
    "temporal_scope": 15,
    "no_answer": 15,
    "clarification": 10,
    "adversarial": 10,
}


def canonical_hash(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def artifact_hash(path: Path) -> str:
    if path.suffix == ".json":
        return canonical_hash(json.loads(path.read_text(encoding="utf-8")))
    if path.suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as file:
            return canonical_hash(list(csv.DictReader(file)))
    return sha256(path.read_bytes()).hexdigest()


class RequiredFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fact_id: str = Field(min_length=1)
    statement: str = Field(min_length=5)
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    question_id: str = Field(pattern=r"^[DT][0-9]{2}$")
    split: Split
    category: Category
    paraphrase_group: str = Field(min_length=3)
    rule_families: tuple[str, ...] = Field(min_length=1)
    question: str = Field(min_length=3, max_length=1000)
    expected_status: Literal["answered", "insufficient_evidence", "needs_clarification"]
    reference_answer: str = Field(min_length=10)
    required_facts: tuple[RequiredFact, ...] = ()
    support_evidence_ids: tuple[str, ...] = ()
    context_evidence_ids: tuple[str, ...] = ()
    contrast_evidence_ids: tuple[str, ...] = ()
    required_clarifications: tuple[str, ...] = ()
    must_not_claim: tuple[str, ...] = ()
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    scope: QuestionScope = Field(default_factory=QuestionScope)
    origin: str = Field(min_length=5)
    review_note: str = Field(min_length=15)

    @model_validator(mode="after")
    def validate_contract(self):
        if self.expected_status == "answered":
            if (
                not self.required_facts
                or not self.support_evidence_ids
                or self.required_clarifications
            ):
                raise ValueError("Answered cases require facts/located support and resolved scope")
            if {eid for fact in self.required_facts for eid in fact.evidence_ids} != set(
                self.support_evidence_ids
            ):
                raise ValueError("Every support span must be tied to a required fact")
        elif self.required_facts or self.support_evidence_ids:
            raise ValueError("Abstention/clarification contrast is not gold answer support")
        if (self.expected_status == "needs_clarification") != bool(self.required_clarifications):
            raise ValueError("Clarification requires explicit missing/conflicting fields")
        if self.category == "no_answer" and self.expected_status != "insufficient_evidence":
            raise ValueError("No-answer category must declare abstention")
        if self.category == "clarification" and self.expected_status != "needs_clarification":
            raise ValueError("Clarification category has an incompatible status")
        for values in (
            self.rule_families,
            self.support_evidence_ids,
            self.context_evidence_ids,
            self.contrast_evidence_ids,
            self.required_clarifications,
        ):
            if len(values) != len(set(values)):
                raise ValueError("Duplicate family/evidence/clarification identifiers")
        if len({fact.fact_id for fact in self.required_facts}) != len(self.required_facts):
            raise ValueError("Duplicate fact ID")
        if set(self.support_evidence_ids) & set(self.contrast_evidence_ids):
            raise ValueError("A contrast span cannot also be answer support")
        return self


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_id: str
    chunk_id: str
    document_id: str
    document_number: str
    source_url: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    char_start: int = Field(ge=0, strict=True)
    char_end: int = Field(gt=0, strict=True)
    excerpt: str = Field(min_length=1, max_length=1300)
    excerpt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_pdf_pages: tuple[int, ...] = Field(min_length=1)
    article: str | None
    clauses: tuple[str, ...]
    extraction_methods: tuple[str, ...]
    quality_status: Literal["approved"]
    locator: str = Field(min_length=5)
    page_granularity: Literal["approved_chunk_page_range"] = "approved_chunk_page_range"

    @model_validator(mode="after")
    def validate_span(self):
        if self.char_end - self.char_start != len(self.excerpt):
            raise ValueError("Unicode offsets do not match the curated excerpt")
        if sha256(self.excerpt.encode()).hexdigest() != self.excerpt_sha256:
            raise ValueError("Curated excerpt hash mismatch")
        if any(page < 1 for page in self.source_pdf_pages):
            raise ValueError("Invalid PDF page")
        return self


def read_cases(path: Path) -> list[EvaluationCase]:
    return [
        EvaluationCase.model_validate(row) for row in json.loads(path.read_text(encoding="utf-8"))
    ]


def read_evidence(path: Path) -> dict[str, EvidenceSpan]:
    spans = [
        EvidenceSpan.model_validate(row) for row in json.loads(path.read_text(encoding="utf-8"))
    ]
    if len({span.evidence_id for span in spans}) != len(spans):
        raise ValueError("Duplicate evidence identifier")
    return {span.evidence_id: span for span in spans}


def validate_splits(
    cases: list[EvaluationCase], evidence: dict[str, EvidenceSpan], exposed: set[str]
):
    if len(cases) != 100 or len({case.question_id for case in cases}) != 100:
        raise ValueError("Dataset100 needs 100 unique question IDs")
    if Counter(case.category for case in cases) != CATEGORY_COUNTS:
        raise ValueError("Dataset categories differ from the plan")
    if Counter(case.split for case in cases) != {"development": 60, "test": 40}:
        raise ValueError("Dataset split must be 60 development / 40 prospective held-out")
    groups = {}
    families = {}
    questions = set()
    referenced = set()
    for case in cases:
        canonical_question = " ".join(case.question.casefold().split())
        if canonical_question in questions:
            raise ValueError("Duplicate normalized question")
        questions.add(canonical_question)
        if groups.setdefault(case.paraphrase_group, case.split) != case.split:
            raise ValueError("Paraphrase group leakage across splits")
        for family in case.rule_families:
            if families.setdefault(family, case.split) != case.split:
                raise ValueError("Shared rule family crosses development/held-out")
            if case.split == "test" and family in exposed:
                raise ValueError("An already tuned family cannot become held-out")
        refs = set(
            case.support_evidence_ids + case.context_evidence_ids + case.contrast_evidence_ids
        )
        if not refs.issubset(evidence):
            raise ValueError("Unknown evidence identifier")
        referenced.update(refs)
    if referenced != set(evidence):
        raise ValueError("Unused evidence spans need review/removal, not hidden gold")


def fetch_chunks(settings, config, ids: set[str]) -> dict:
    with psycopg.connect(str(settings.database_url), row_factory=dict_row) as connection:
        rows = connection.execute(
            f"""SELECT c.chunk_id,c.document_id,c.text,c.content_sha256,c.source_pdf_pages,
                c.article,c.clauses,c.extraction_methods,c.quality_status,d.document_number,
                d.source_url,d.source_sha256 FROM chunks c JOIN documents d
                ON d.document_id=c.document_id WHERE {READY_FILTER} AND c.chunk_id=ANY(%(ids)s)
                ORDER BY c.chunk_id""",
            {**retrieval_parameters(config), "ids": sorted(ids)},
        ).fetchall()
    if {row["chunk_id"] for row in rows} != ids:
        raise ValueError("Evidence is absent, blocked, unapproved, or has stale model binding")
    return {row["chunk_id"]: row for row in rows}


def verify_spans(evidence: dict[str, EvidenceSpan], chunks: dict):
    for span in evidence.values():
        row = chunks[span.chunk_id]
        if sha256(row["text"].encode()).hexdigest() != row["content_sha256"]:
            raise ValueError("Current chunk content hash mismatch")
        for key in (
            "document_id",
            "document_number",
            "source_url",
            "source_sha256",
            "content_sha256",
            "article",
            "quality_status",
        ):
            if getattr(span, key) != row[key]:
                raise ValueError("Stale evidence provenance: " + key)
        for key in ("source_pdf_pages", "clauses", "extraction_methods"):
            if getattr(span, key) != tuple(row[key]):
                raise ValueError("Stale evidence page/structure/extraction binding")
        if row["text"][span.char_start : span.char_end] != span.excerpt:
            raise ValueError("Bound source range changed; do not silently rebind gold")


def verify_answer_filters(settings, config, cases, evidence):
    with psycopg.connect(str(settings.database_url), row_factory=dict_row) as connection:
        for case in cases:
            if case.expected_status != "answered":
                continue
            ids = {
                evidence[eid].chunk_id
                for eid in case.support_evidence_ids + case.context_evidence_ids
            }
            found = connection.execute(
                f"SELECT c.chunk_id FROM chunks c JOIN documents d ON d.document_id=c.document_id "
                f"WHERE {READY_FILTER} AND {METADATA_FILTER} AND c.chunk_id=ANY(%(ids)s)",
                {
                    **retrieval_parameters(config),
                    **filter_parameters(case.filters),
                    "ids": sorted(ids),
                },
            ).fetchall()
            if {row["chunk_id"] for row in found} != ids:
                raise ValueError("Gold support contradicts caller filters: " + case.question_id)


def verify_freeze(directory: Path):
    lock = json.loads((directory / "freeze.json").read_text(encoding="utf-8"))
    cases = read_cases(directory / "questions.json")
    evidence = read_evidence(directory / "evidence.json")
    serialized = [case.model_dump(mode="json") for case in cases]
    if canonical_hash(serialized) != lock["dataset_sha256"]:
        raise ValueError("Frozen evaluation questions/labels/splits drifted")
    if (
        canonical_hash([span.model_dump(mode="json") for span in evidence.values()])
        != lock["evidence_sha256"]
    ):
        raise ValueError("Frozen evaluation evidence drifted")
    if (
        canonical_hash([row for row in serialized if row["split"] == "test"])
        != lock["held_out_sha256"]
    ):
        raise ValueError("Held-out freeze drifted")
    for filename, digest in lock["files"].items():
        if artifact_hash(directory / filename) != digest:
            raise ValueError("Frozen authoring/review evidence drifted: " + filename)
    return cases, evidence, lock


def load_evaluation_cases(directory: Path, split: Split = "development") -> list[EvaluationCase]:
    """Default development only. Selecting test is explicit; this performs no model work."""
    if split not in ("development", "test"):
        raise ValueError("Explicit development/test split required")
    cases, _, _ = verify_freeze(directory)
    return [case for case in cases if case.split == split]
