import logging
from dataclasses import asdict
from time import perf_counter
from typing import Literal

import psycopg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from regularag.generation.clarification import QuestionScope
from regularag.generation.factory import build_answer_service
from regularag.generation.service import AnswerResult, AnswerService
from regularag.retrieval.filters import RetrievalFilters

router = APIRouter(prefix="/api/v1", tags=["questions"])
logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=3, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    retrieval_mode: Literal["vector", "keyword", "hybrid"] | None = None
    filters: RetrievalFilters | None = None
    scope: QuestionScope | None = None


class SourceResponse(BaseModel):
    source_id: str
    chunk_id: str
    document_id: str
    document_number: str
    title: str
    source_url: str
    pdf_page_start: int
    pdf_page_end: int
    printed_page_start: int | None
    printed_page_end: int | None
    score: float
    cited: bool
    excerpt: str
    chapter: str | None
    article: str | None
    clauses: list[str]
    extraction_methods: list[str]
    score_kind: str
    retrieval_branches: list[str]
    rank: int
    dense_rank: int | None
    keyword_rank: int | None
    dense_score: float | None
    keyword_score: float | None
    rrf_score: float | None
    legal_status: str
    domain: str
    document_type: str
    applies_to: str
    cohort_scope: str
    cohort_from: int | None
    cohort_to: int | None
    effective_from_date: str | None
    effective_to_date: str | None
    omitted_layout_pdf_pages: list[int]
    metadata_note: str
    issued_date: str | None
    source_checked_at: str | None
    source_check_status: str
    first_stage_rank: int | None
    rerank_rank: int | None
    rerank_score: float | None
    rerank_windows: int
    freshness_status: str
    latest_document_number: str | None
    latest_issued_date: str | None
    required_update_chunk_ids: list[str]


class AskResponse(BaseModel):
    status: Literal["answered", "insufficient_evidence", "needs_clarification"]
    answer: str
    sources: list[SourceResponse]
    embedding_model: str
    generation_model: str
    prompt_version: str
    warnings: list[str]
    failure_reason: str | None
    input_tokens: int
    response_policy: str
    retrieval_mode: str
    applied_filters: RetrievalFilters
    reranker_model: str | None
    reranker_revision: str | None
    freshness_policy: str | None
    query_document_codes: list[str]
    evidence_passages: list["PassageResponse"]
    retrieval_ms: float
    generation_ms: float
    selection_attempts: int
    clarification: "ClarificationResponse | None"
    resolved_scope: QuestionScope
    requested_filters: RetrievalFilters
    behaviour_policy: str | None
    version_notes: list["VersionNoteResponse"]


class ClarificationResponse(BaseModel):
    required_fields: list[str]
    questions: list[str]
    conflicting_fields: list[str]


class VersionNoteResponse(BaseModel):
    source_id: str
    document_number: str
    issued_date: str | None
    document_role: str
    related_document_number: str | None
    legal_status: str
    cohort_scope: str
    effective_from_date: str | None


class PassageResponse(BaseModel):
    passage_id: str
    source_id: str
    chunk_id: str
    char_start: int
    char_end: int
    text: str
    text_sha256: str
    required_passage_ids: list[str]
    cited: bool


def _get_answer_service(request: Request) -> AnswerService:
    with request.app.state.answer_service_lock:
        service = request.app.state.answer_service
        if service is None:
            service = build_answer_service(request.app.state.settings)
            request.app.state.answer_service = service
    return service


def _to_response(result: AnswerResult) -> AskResponse:
    return AskResponse(
        status=result.status,
        answer=result.answer,
        sources=[SourceResponse(**asdict(source)) for source in result.sources],
        embedding_model=result.embedding_model,
        generation_model=result.generation_model,
        prompt_version=result.prompt_version,
        warnings=list(result.warnings),
        failure_reason=result.failure_reason,
        input_tokens=result.input_tokens,
        response_policy=result.response_policy,
        retrieval_mode=result.retrieval_mode,
        applied_filters=result.applied_filters,
        reranker_model=result.reranker_model,
        reranker_revision=result.reranker_revision,
        freshness_policy=result.freshness_policy,
        query_document_codes=list(result.query_document_codes),
        evidence_passages=[PassageResponse(**asdict(p)) for p in result.evidence_passages],
        retrieval_ms=result.retrieval_ms,
        generation_ms=result.generation_ms,
        selection_attempts=result.selection_attempts,
        clarification=ClarificationResponse(**asdict(result.clarification))
        if result.clarification
        else None,
        resolved_scope=result.resolved_scope,
        requested_filters=result.requested_filters,
        behaviour_policy=result.behaviour_policy,
        version_notes=[VersionNoteResponse(**asdict(note)) for note in result.version_notes],
    )


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, request: Request) -> AskResponse:
    started = perf_counter()
    try:
        service = _get_answer_service(request)
        options = {"filters": payload.filters} if payload.filters is not None else {}
        if payload.scope is not None:
            options["scope"] = payload.scope
        result = (
            service.ask(payload.question, payload.top_k, payload.retrieval_mode, **options)
            if payload.retrieval_mode is not None
            else service.ask(payload.question, payload.top_k, **options)
        )
    except ValueError as exc:
        logger.warning("ask input or configuration error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=422, detail="Câu hỏi hoặc cấu hình vượt giới hạn xử lý."
        ) from exc
    except (OSError, RuntimeError, psycopg.Error) as exc:
        logger.error("ask backend unavailable: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Database hoặc model baseline chưa sẵn sàng."
        ) from exc
    logger.info(
        "ask completed status=%s sources=%s latency_ms=%.0f",
        result.status,
        [source.chunk_id for source in result.sources],
        (perf_counter() - started) * 1000,
    )
    return _to_response(result)
