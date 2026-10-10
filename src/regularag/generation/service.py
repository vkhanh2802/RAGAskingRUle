import re
from dataclasses import dataclass, field, replace
from threading import Lock
from time import perf_counter
from typing import Protocol

from regularag.generation.clarification import (
    Clarification,
    QuestionScope,
    ScopePlan,
    VersionNote,
    analyse_scope,
    applicability_failure,
    version_notes,
)
from regularag.generation.guards import evidence_failure, unsupported_question
from regularag.generation.local import AnswerStatus, Generator
from regularag.generation.passages import EvidencePassage, prepare_passages, resolve_passages
from regularag.generation.prompt import prepare_context
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.embedding import Embedder
from regularag.retrieval.filters import RetrievalFilters
from regularag.retrieval.freshness import select_with_updates
from regularag.retrieval.keyword import build_keyword_query
from regularag.retrieval.pipeline import RetrievalMode, usable_evidence
from regularag.retrieval.repository import RetrievedChunk


class Retriever(Protocol):
    def search(
        self,
        question: str,
        limit: int,
        mode: RetrievalMode | None = None,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievedChunk]: ...


@dataclass(frozen=True, slots=True)
class AnswerSource:
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
    chapter: str | None = None
    article: str | None = None
    clauses: tuple[str, ...] = ()
    extraction_methods: tuple[str, ...] = ("pymupdf_text",)
    score_kind: str = "cosine_similarity"
    retrieval_branches: tuple[str, ...] = ()
    rank: int = 0
    dense_rank: int | None = None
    keyword_rank: int | None = None
    dense_score: float | None = None
    keyword_score: float | None = None
    rrf_score: float | None = None
    legal_status: str = "unknown"
    domain: str = ""
    document_type: str = ""
    applies_to: str = ""
    cohort_scope: str = ""
    cohort_from: int | None = None
    cohort_to: int | None = None
    effective_from_date: str | None = None
    effective_to_date: str | None = None
    omitted_layout_pdf_pages: tuple[int, ...] = ()
    metadata_note: str = ""
    issued_date: str | None = None
    source_checked_at: str | None = None
    source_check_status: str = "unchecked"
    first_stage_rank: int | None = None
    rerank_rank: int | None = None
    rerank_score: float | None = None
    rerank_windows: int = 0
    freshness_status: str = "unchecked"
    latest_document_number: str | None = None
    latest_issued_date: str | None = None
    required_update_chunk_ids: tuple[str, ...] = ()
    evidence_char_ranges: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class AnswerResult:
    status: AnswerStatus
    answer: str
    sources: tuple[AnswerSource, ...]
    embedding_model: str
    generation_model: str
    prompt_version: str
    warnings: tuple[str, ...] = ()
    failure_reason: str | None = None
    input_tokens: int = 0
    response_policy: str = "abstractive"
    retrieval_mode: str = "vector"
    applied_filters: RetrievalFilters = field(default_factory=RetrievalFilters)
    reranker_model: str | None = None
    reranker_revision: str | None = None
    freshness_policy: str | None = None
    query_document_codes: tuple[str, ...] = ()
    evidence_passages: tuple[EvidencePassage, ...] = ()
    retrieval_ms: float = 0.0
    generation_ms: float = 0.0
    selection_attempts: int = 0
    clarification: Clarification | None = None
    resolved_scope: QuestionScope = field(default_factory=QuestionScope)
    requested_filters: RetrievalFilters = field(default_factory=RetrievalFilters)
    behaviour_policy: str | None = None
    version_notes: tuple[VersionNote, ...] = ()


class AnswerService:
    def __init__(
        self,
        config: RagBaselineConfig,
        embedder: Embedder,
        retriever: Retriever,
        generator: Generator,
    ) -> None:
        self.config = config
        self.embedder = embedder
        self.retriever = retriever
        self.generator = generator
        self._inference_lock = Lock()

    def ask(
        self,
        question: str,
        top_k: int | None = None,
        retrieval_mode: RetrievalMode | None = None,
        filters: RetrievalFilters | None = None,
        scope: QuestionScope | None = None,
    ) -> AnswerResult:
        # FastAPI executes sync endpoints in threads; serialize model work on this small host.
        with self._inference_lock:
            question_reason = (
                unsupported_question(question) if self.config.behaviour.enabled else None
            )
            plan = (
                analyse_scope(question, filters, scope)
                if self.config.behaviour.enabled and not question_reason
                else None
            )
            effective_filters = plan.filters if plan else filters
            try:
                if question_reason:
                    result = self._result(
                        "insufficient_evidence",
                        "Corpus hiện có chỉ hỗ trợ các quy định UIT đã kiểm chứng; "
                        "chưa có bằng chứng để trả lời đầy đủ yêu cầu này.",
                        [],
                        set(),
                        failure_reason=question_reason,
                    )
                elif plan and plan.clarification:
                    result = replace(
                        self._result(
                            "needs_clarification",
                            " ".join(plan.clarification.questions),
                            [],
                            set(),
                            failure_reason=plan.failure_reason,
                        ),
                        clarification=plan.clarification,
                    )
                else:
                    result = self._ask(question, top_k, retrieval_mode, effective_filters, plan)
            finally:
                if self.config.generation.low_memory_mode:
                    release = getattr(self.generator, "release", None)
                    if callable(release):
                        release()
                    release_retrieval = getattr(self.retriever, "release_models", None)
                    if callable(release_retrieval):
                        release_retrieval()
            warnings = result.warnings
            if effective_filters and effective_filters.as_of:
                warnings += (
                    "Bộ lọc as_of dùng mốc hiệu lực đã ghi nhận từ nguồn; "
                    "không xác nhận văn bản vẫn hiện hành tại ngày đó.",
                )
            return replace(
                result,
                retrieval_mode=retrieval_mode or self.config.retrieval.mode,
                applied_filters=effective_filters or RetrievalFilters(),
                requested_filters=filters or RetrievalFilters(),
                resolved_scope=plan.scope if plan else scope or QuestionScope(),
                behaviour_policy=(
                    self.config.behaviour.policy_version if self.config.behaviour.enabled else None
                ),
                warnings=warnings,
                query_document_codes=(
                    build_keyword_query(question).document_codes
                    if self.config.retrieval.document_reference_policy == "shared-query-refs-v1"
                    else ()
                ),
            )

    def _ask(
        self,
        question: str,
        top_k: int | None,
        mode: RetrievalMode | None,
        filters: RetrievalFilters | None,
        plan: ScopePlan | None = None,
    ) -> AnswerResult:
        retrieval_limit = top_k or self.config.retrieval.top_k
        options = {}
        if mode is not None:
            options["mode"] = mode
        if filters is not None:
            options["filters"] = filters
        started = perf_counter()
        retrieved = self.retriever.search(question, retrieval_limit, **options)
        if self.config.generation.low_memory_mode:
            release = getattr(self.retriever, "release_models", None)
            if callable(release):
                release()
        retrieval_ms = (perf_counter() - started) * 1000
        eligible = [chunk for chunk in retrieved if usable_evidence(chunk, self.config)]
        context = (
            select_with_updates(eligible, self.config.generation.context_chunks)
            if self.config.freshness.enabled
            else eligible[: self.config.generation.context_chunks]
        )
        if not context:
            result = self._result(
                status="insufficient_evidence",
                answer="Không tìm thấy bằng chứng đủ liên quan trong corpus hiện có.",
                context=context,
                cited_ids=set(),
                failure_reason="no_matching_evidence",
            )
            if plan and plan.topic != "general":
                result = replace(
                    result,
                    answer="Corpus chưa có bằng chứng đã kiểm chứng phù hợp "
                    "với khóa/hệ/chương trình "
                    "và thời điểm bạn yêu cầu; không dùng phạm vi khác để thay thế.",
                )
            return replace(result, retrieval_ms=round(retrieval_ms, 3))

        if reason := self._freshness_failure(context):
            return replace(
                self._result(
                    status="insufficient_evidence",
                    answer="Chưa đủ bằng chứng đã kiểm chứng từ văn bản cập nhật mới nhất "
                    "trong phạm vi yêu cầu; không sử dụng quy định cũ để thay thế.",
                    context=context,
                    cited_ids=set(),
                    failure_reason=reason,
                ),
                retrieval_ms=round(retrieval_ms, 3),
                version_notes=version_notes(context),
            )
        if reason := evidence_failure(context):
            return replace(
                self._result(
                    "insufficient_evidence",
                    "Context không đạt kiểm tra tính toàn vẹn hoặc có chỉ dẫn điều khiển trợ lý; "
                    "chưa sử dụng các đoạn này làm bằng chứng trả lời.",
                    context,
                    set(),
                    failure_reason=reason,
                ),
                retrieval_ms=round(retrieval_ms, 3),
            )
        if plan:
            reason = applicability_failure(plan, context)
            if reason or plan.compare_versions:
                notes = version_notes(context)
                details = "\n".join(
                    f"- {note.document_number}: ban hành {note.issued_date or 'chưa xác minh'}; "
                    f"vai trò {note.document_role}; liên quan "
                    f"{note.related_document_number or 'không ghi nhận'}; "
                    f"mốc hiệu lực nguồn {note.effective_from_date or 'chưa chuẩn hóa'}; "
                    f"legal_status={note.legal_status}."
                    for note in notes
                )
                return replace(
                    self._result(
                        "insufficient_evidence",
                        (
                            "Nguồn học phí gia hạn hiện có là lịch sử; chưa đủ bằng chứng "
                            "để xác nhận mức thu hiện nay."
                            if reason == "current_fee_not_verified"
                            else "Khóa yêu cầu nằm ngoài phạm vi được chứng minh từ nguồn."
                            if reason == "cohort_outside_evidence"
                            else "Chưa xác minh tình trạng hiệu lực pháp lý; ngày ban hành "
                            "và mốc hiệu lực trong nguồn không đủ để xác nhận còn hiện hành."
                            if reason == "legal_status_not_verified"
                            else "Chưa đủ bằng chứng để hợp nhất toàn bộ khác biệt phiên bản "
                            "và xác định hiệu lực."
                        )
                        + " Các thông tin nguồn đã ghi nhận:\n"
                        + details,
                        context,
                        set(),
                        failure_reason=reason or "version_comparison_not_consolidated",
                    ),
                    retrieval_ms=round(retrieval_ms, 3),
                    version_notes=notes,
                )
        if self.config.generation.response_policy == "verified_passages":
            return self._ask_passages(question, context, retrieval_ms, plan)
        prepared = prepare_context(
            question,
            context,
            self.generator.input_token_limit,
            self.generator.count_prompt_tokens,
        )
        context = list(prepared.chunks)
        if not context:
            return self._result(
                status="insufficient_evidence",
                answer="Không có đoạn trích phù hợp với phạm vi cụ thể của câu hỏi.",
                context=context,
                cited_ids=set(),
                failure_reason="no_scoped_passage",
                input_tokens=prepared.input_tokens,
            )
        if reason := self._freshness_failure(context):
            return self._result(
                status="insufficient_evidence",
                answer="Token budget không giữ được đủ bằng chứng của văn bản cập nhật "
                "để đối chiếu với văn bản gốc.",
                context=context,
                cited_ids=set(),
                failure_reason=reason,
                input_tokens=prepared.input_tokens,
            )
        generated = self.generator.generate(prepared.prompt)
        allowed_ids = {f"S{index}" for index in range(1, len(context) + 1)}
        cited_ids = set(generated.source_ids)
        inline_ids = set(re.findall(r"\[(S\d+)\]", generated.answer))
        verified_quotes = self.config.generation.response_policy == "verified_quotes"
        if (
            not cited_ids.issubset(allowed_ids)
            or (
                generated.status == "answered"
                and (not cited_ids or (not verified_quotes and inline_ids != cited_ids))
            )
            or not inline_ids.issubset(allowed_ids)
        ):
            return self._result(
                status="insufficient_evidence",
                answer="Mô hình không cung cấp citation hợp lệ cho câu trả lời.",
                context=context,
                cited_ids=set(),
                failure_reason="invalid_citations",
                input_tokens=prepared.input_tokens,
            )

        missing_amendments = {
            chunk.related_document_number
            for index, chunk in enumerate(context, start=1)
            if f"S{index}" in cited_ids
            and chunk.document_role == "base"
            and chunk.amendment_required
            and chunk.related_document_number
            and not chunk.related_document_ready
        }
        if generated.status == "answered" and missing_amendments:
            return self._result(
                status="insufficient_evidence",
                answer="Chưa đủ bằng chứng để kết luận vì chưa có văn bản cập nhật "
                + ", ".join(sorted(missing_amendments))
                + " trong corpus đã index.",
                context=context,
                cited_ids=set(),
                failure_reason="missing_amendment",
                input_tokens=prepared.input_tokens,
            )

        missing_context = {
            chunk.related_document_number
            for index, chunk in enumerate(context, start=1)
            if generated.status == "answered"
            and f"S{index}" in cited_ids
            and chunk.document_role == "base"
            and chunk.amendment_required
            and chunk.related_document_ready
            and chunk.related_document_number not in {source.document_number for source in context}
        }
        if missing_context:
            return self._result(
                status="insufficient_evidence",
                answer="Văn bản cập nhật đã được index nhưng chưa có trong context để đối chiếu: "
                + ", ".join(sorted(missing_context))
                + ".",
                context=context,
                cited_ids=set(),
                failure_reason="amendment_not_in_context",
                input_tokens=prepared.input_tokens,
            )

        if generated.status == "answered" and verified_quotes:
            lookup = {f"S{index}": chunk for index, chunk in enumerate(context, start=1)}
            quoted_ids = {quote.source_id for quote in generated.evidence_quotes}
            quotes_valid = bool(generated.evidence_quotes) and quoted_ids == cited_ids
            for quote in generated.evidence_quotes:
                source = lookup.get(quote.source_id)
                # Ignore only whitespace differences introduced by PDF line wrapping.
                quoted_text = " ".join(quote.quote.split())
                if (
                    source is None
                    or not quoted_text
                    or quoted_text not in " ".join(source.text.split())
                ):
                    quotes_valid = False
                    break
            if not quotes_valid:
                return self._result(
                    status="insufficient_evidence",
                    answer="Đoạn trích do mô hình chọn không khớp bằng chứng đã truy xuất.",
                    context=context,
                    cited_ids=set(),
                    failure_reason="unverified_quote",
                    input_tokens=prepared.input_tokens,
                )
            answer = "\n\n".join(
                f"“{quote.quote.strip()}” [{quote.source_id}]"
                for quote in generated.evidence_quotes
            )
        elif generated.status == "insufficient_evidence":
            answer = (
                "Bằng chứng được truy xuất chưa đủ để trả lời đầy đủ câu hỏi. "
                "Bạn có thể mở các nguồn bên dưới để đối chiếu."
            )
        else:
            answer = generated.answer

        return self._result(
            status=generated.status,
            answer=answer,
            context=context,
            cited_ids=cited_ids,
            failure_reason=generated.failure_reason,
            input_tokens=prepared.input_tokens,
        )

    def _ask_passages(
        self,
        question: str,
        context: list[RetrievedChunk],
        retrieval_ms: float,
        plan: ScopePlan | None = None,
    ) -> AnswerResult:
        started = perf_counter()
        prepared = prepare_passages(
            question,
            context,
            self.generator.input_token_limit,
            self.generator.count_prompt_tokens,
            self.config.generation.max_passages,
            scope=plan.scope if plan else None,
        )
        context = list(prepared.chunks)
        reason = prepared.failure_reason or self._freshness_failure(context)
        generated = None
        selected = []
        if not reason:
            generated = self.generator.generate(prepared.prompt)
            reason = generated.failure_reason
            if (
                generated.source_ids
                or generated.evidence_quotes
                or (
                    len(generated.passage_ids) > self.config.generation.max_selected_passages
                    or (generated.status == "answered") != bool(generated.passage_ids)
                )
            ):
                reason = "invalid_passage_output"
            if not reason:
                selected, reason = resolve_passages(
                    question,
                    generated.passage_ids,
                    prepared,
                    scope=plan.scope if plan else None,
                    minimize=self.config.behaviour.enabled
                    and self.config.behaviour.minimize_selected_passages,
                )
                if not selected and not reason:
                    reason = "no_supported_selection"
        cited_ids = {p.source_id for p in selected} if not reason else set()
        if not reason and selected:
            for index, chunk in enumerate(context, 1):
                if (
                    f"S{index}" not in cited_ids
                    or chunk.document_role != "base"
                    or not chunk.amendment_required
                ):
                    continue
                if chunk.related_document_number and not chunk.related_document_ready:
                    reason = "missing_amendment"
                elif chunk.related_document_number and chunk.related_document_number not in {
                    c.document_number for c in context
                }:
                    reason = "amendment_not_in_context"
            if reason:
                cited_ids = set()
        answer = (
            "\n\n".join(f"“{p.text}” [{p.source_id}]" for p in selected)
            if selected and not reason
            else "Các đoạn trích hiện có chưa đủ để trả lời đầy đủ câu hỏi trong phạm vi yêu cầu."
        )
        result = self._result(
            status="answered" if selected and not reason else "insufficient_evidence",
            answer=answer,
            context=context,
            cited_ids=cited_ids,
            failure_reason=reason,
            input_tokens=prepared.input_tokens,
        )
        selected_ids = {p.passage_id for p in selected} if not reason else set()
        return replace(
            result,
            evidence_passages=tuple(
                replace(p, cited=p.passage_id in selected_ids) for p in prepared.passages
            ),
            retrieval_ms=round(retrieval_ms, 3),
            generation_ms=round((perf_counter() - started) * 1000, 3),
            selection_attempts=generated.attempts if generated else 0,
            version_notes=version_notes(context) if plan else (),
        )

    def _freshness_failure(self, context: list[RetrievedChunk]) -> str | None:
        if not self.config.freshness.enabled:
            return None
        ids = {chunk.chunk_id for chunk in context}
        for chunk in context:
            if chunk.freshness_failure:
                return chunk.freshness_failure
            if not set(chunk.required_update_chunk_ids).issubset(ids):
                return "latest_not_in_context"
        return None

    def _result(
        self,
        status: AnswerStatus,
        answer: str,
        context: list[RetrievedChunk],
        cited_ids: set[str],
        failure_reason: str | None = None,
        input_tokens: int = 0,
    ) -> AnswerResult:
        sources = tuple(
            AnswerSource(
                source_id=f"S{index}",
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_number=chunk.document_number,
                title=chunk.title,
                source_url=chunk.source_url,
                pdf_page_start=chunk.pdf_page_start,
                pdf_page_end=chunk.pdf_page_end,
                printed_page_start=chunk.printed_page_start,
                printed_page_end=chunk.printed_page_end,
                score=round(chunk.score, 6),
                cited=f"S{index}" in cited_ids,
                excerpt=chunk.text,
                chapter=chunk.chapter,
                article=chunk.article,
                clauses=chunk.clauses,
                extraction_methods=chunk.extraction_methods,
                score_kind=chunk.score_kind,
                retrieval_branches=chunk.retrieval_branches,
                rank=chunk.rank,
                dense_rank=chunk.dense_rank,
                keyword_rank=chunk.keyword_rank,
                dense_score=chunk.dense_score,
                keyword_score=chunk.keyword_score,
                rrf_score=chunk.rrf_score,
                legal_status=chunk.legal_status,
                domain=chunk.domain,
                document_type=chunk.document_type,
                applies_to=chunk.applies_to,
                cohort_scope=chunk.cohort_scope,
                cohort_from=chunk.cohort_from,
                cohort_to=chunk.cohort_to,
                effective_from_date=chunk.effective_from_date,
                effective_to_date=chunk.effective_to_date,
                omitted_layout_pdf_pages=chunk.omitted_layout_pdf_pages,
                metadata_note=chunk.metadata_note,
                issued_date=chunk.issued_date,
                source_checked_at=chunk.source_checked_at,
                source_check_status=chunk.source_check_status,
                first_stage_rank=chunk.first_stage_rank,
                rerank_rank=chunk.rerank_rank,
                rerank_score=chunk.rerank_score,
                rerank_windows=chunk.rerank_windows,
                freshness_status=chunk.freshness_status,
                latest_document_number=chunk.latest_document_number,
                latest_issued_date=chunk.latest_issued_date,
                required_update_chunk_ids=chunk.required_update_chunk_ids,
                evidence_char_ranges=chunk.evidence_char_ranges,
            )
            for index, chunk in enumerate(context, start=1)
        )
        return AnswerResult(
            status=status,
            answer=answer,
            sources=sources,
            embedding_model=self.config.embedding.model_name,
            generation_model=self.config.generation.model_name,
            prompt_version=self.config.generation.prompt_version,
            warnings=tuple(
                dict.fromkeys(
                    (
                        [
                            "Mới nhất được đối chiếu theo ngày ban hành "
                            "và quan hệ sửa đổi/thay thế "
                            "đã kiểm chứng trong corpus, trong phạm vi filters; "
                            "không tự xác nhận trạng thái pháp lý hiện hành."
                        ]
                        if self.config.freshness.enabled
                        else []
                    )
                    + [
                        f"{chunk.document_number}: văn bản liên quan chưa đạt full/ready "
                        f"{chunk.related_document_number}."
                        for chunk in context
                        if chunk.amendment_required
                        and chunk.related_document_number
                        and not chunk.related_document_ready
                    ]
                    + [
                        f"{chunk.document_number}: chưa xác minh trạng thái hiệu lực."
                        for chunk in context
                        if chunk.legal_status == "unknown"
                    ]
                    + [
                        f"{chunk.document_number}: coverage partial; trang PDF loại khỏi evidence: "
                        + (", ".join(map(str, chunk.excluded_pdf_pages)) or "không có")
                        + "; trang có layout bị bỏ: "
                        + (", ".join(map(str, chunk.omitted_layout_pdf_pages)) or "không có")
                        for chunk in context
                        if chunk.coverage_status != "full"
                    ]
                )
            ),
            failure_reason=failure_reason,
            input_tokens=input_tokens,
            response_policy=self.config.generation.response_policy,
            reranker_model=self.config.reranker.model_name
            if self.config.reranker.enabled
            else None,
            reranker_revision=(
                self.config.reranker.model_revision if self.config.reranker.enabled else None
            ),
            freshness_policy=(
                self.config.freshness.policy_version if self.config.freshness.enabled else None
            ),
        )
