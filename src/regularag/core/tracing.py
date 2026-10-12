"""Request-local, bounded metadata traces. No question, source text or model output."""

import json
import logging
import math
import re
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from hashlib import sha256
from time import perf_counter
from uuid import uuid4

TRACE_VERSION = "pipeline-trace-v1"
MAX_SPANS = 64
MAX_ROWS = 100
_FIELDS = {
    "route",
    "method",
    "http_status",
    "implementation",
    "mode",
    "top_k",
    "candidate_limit",
    "configured_model",
    "model_revision",
    "prompt_version",
    "response_policy",
    "filter_fields",
    "scope_fields",
    "topic",
    "required_fields",
    "failure_reason",
    "question_length",
    "dimension",
    "configured_dimension",
    "budget_input_tokens",
    "budget_limit",
    "max_passages",
    "max_selected_passages",
    "required_support",
    "selected_passage_ids",
    "resolved_passage_ids",
    "cited_passage_ids",
    "cited_source_ids",
    "passage_count",
    "removed_count",
    "ordering_policy",
    "dense_count",
    "keyword_count",
    "status",
    "attempts",
    "reason",
    "error_type",
}
_trace: ContextVar["RequestTrace | None"] = ContextVar("regularag_trace", default=None)
_parent: ContextVar[str | None] = ContextVar("regularag_span", default=None)


def _bounded(value):
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return value[:160]
    if isinstance(value, (list, tuple)):
        return [_bounded(item) for item in value[:MAX_ROWS]]
    return None


def _ids(values, prefix=None):
    pattern = rf"{prefix}[1-9][0-9]*" if prefix else r"[A-Za-z0-9_.:-]{1,128}"
    return [str(value) for value in values if re.fullmatch(pattern, str(value))][:MAX_ROWS]


@dataclass
class Span:
    name: str
    span_id: str = ""
    parent_span_id: str | None = None
    start_ms: float = 0
    duration_ms: float = 0
    status: str = "completed"
    error_type: str | None = None
    attributes: dict = field(default_factory=dict)

    def fields(self, **values):
        if self.span_id:
            self.attributes.update({k: _bounded(v) for k, v in values.items() if k in _FIELDS})

    def chunks(self, label, chunks):
        if not self.span_id or label not in (
            "input_chunks",
            "output_chunks",
            "first_stage_chunks",
            "returned_chunks",
            "eligible_chunks",
            "context_chunks",
        ):
            return
        records = []
        for order, chunk in enumerate(chunks[:MAX_ROWS], 1):
            records.append(
                {
                    "chunk_id": _ids([chunk.chunk_id])[0] if _ids([chunk.chunk_id]) else None,
                    "order": order,
                    **{
                        key: _bounded(getattr(chunk, key, None))
                        for key in (
                            "document_id",
                            "first_stage_rank",
                            "dense_rank",
                            "keyword_rank",
                            "score_kind",
                            "score",
                            "dense_score",
                            "keyword_score",
                            "rrf_score",
                            "rerank_rank",
                            "rerank_score",
                            "rerank_windows",
                            "freshness_status",
                            "freshness_failure",
                            "evidence_char_ranges",
                        )
                    },
                    "required_update_chunk_ids": _ids(chunk.required_update_chunk_ids),
                }
            )
        self.attributes[label] = records
        self.attributes[label + "_count"] = len(chunks)
        self.attributes[label + "_omitted"] = max(0, len(chunks) - MAX_ROWS)

    def passages(self, passages):
        if self.span_id:
            self.attributes["passages"] = [
                {
                    "passage_id": p.passage_id,
                    "source_id": p.source_id,
                    "chunk_id": p.chunk_id,
                    "char_start": p.char_start,
                    "char_end": p.char_end,
                    "text_sha256": p.text_sha256,
                    "required_passage_ids": list(p.required_passage_ids),
                }
                for p in passages[:16]
            ]
            self.attributes["passage_count"] = len(passages)

    def payload(self):
        return {
            "name": self.name,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_ms": self.start_ms,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error_type": self.error_type,
            "attributes": self.attributes,
        }


@dataclass
class RequestTrace:
    enabled: bool = True
    request_id: str = field(default_factory=lambda: str(uuid4()))
    started: float = field(default_factory=perf_counter)
    spans: list[Span] = field(default_factory=list)
    omitted_spans: int = 0
    metadata: dict = field(default_factory=dict)
    usage: dict = field(
        default_factory=lambda: {
            "generation_called": False,
            "input_tokens": 0,
            "output_tokens": 0,
        }
    )
    result: dict = field(default_factory=dict)

    def configure(self, config, generator):
        if not self.enabled:
            return
        serialized = json.dumps(
            config.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self.metadata = {
            "pipeline_version": config.pipeline_version,
            "config_sha256": sha256(serialized.encode()).hexdigest(),
            "prompt_version": config.generation.prompt_version,
            "response_policy": config.generation.response_policy,
            "generation_backend": config.generation.backend,
            "generator_implementation": type(generator).__name__,
            "models": {
                name: {
                    "name": getattr(config, name).model_name,
                    "revision": getattr(config, name).model_revision,
                }
                for name in ("embedding", "reranker", "generation")
            },
            "reranker_enabled": config.reranker.enabled,
            "freshness_policy": config.freshness.policy_version
            if config.freshness.enabled
            else None,
            "behaviour_policy": config.behaviour.policy_version
            if config.behaviour.enabled
            else None,
        }

    def generated(self, result=None):
        if not self.enabled:
            return
        self.usage = {
            "generation_called": True,
            "input_tokens": result.usage_input_tokens if result else None,
            "output_tokens": result.usage_output_tokens if result else None,
        }

    def finish_answer(self, result):
        if not self.enabled:
            return
        self.result = {
            "status": result.status,
            "failure_reason": result.failure_reason,
            "context_chunk_ids": _ids([source.chunk_id for source in result.sources]),
            "cited_source_ids": _ids([s.source_id for s in result.sources if s.cited], "S"),
            "cited_passage_ids": _ids(
                [p.passage_id for p in result.evidence_passages if p.cited], "P"
            ),
            "required_clarification_fields": list(result.clarification.required_fields)
            if result.clarification
            else [],
        }

    def payload(self):
        return {
            "trace_version": TRACE_VERSION,
            "request_id": self.request_id,
            "duration_ms": round((perf_counter() - self.started) * 1000, 3),
            "metadata": self.metadata,
            "spans": [
                s.payload() for s in sorted(self.spans, key=lambda s: (s.start_ms, int(s.span_id)))
            ],
            "omitted_spans": self.omitted_spans,
            "usage": self.usage,
            "result": self.result,
            "api_cost": {"currency": "VND", "total": 0 if self.metadata else None},
            "hosting_compute_cost": None,
            "timing_note": "Parent spans include children; durations are not additive. Queue wait "
            "and context budgeting/model loading are distinct from generate.",
        }

    def emit(self):
        if self.enabled:
            # A telemetry sink failure must not change the inference result.
            with suppress(Exception):
                logging.getLogger("regularag.trace").info(
                    "pipeline trace", extra={"request_id": self.request_id, "trace": self.payload()}
                )


def current_trace():
    return _trace.get()


def request_id():
    return trace.request_id if (trace := current_trace()) else None


@contextmanager
def request_trace(enabled=True):
    trace = RequestTrace(enabled=enabled)
    token = _trace.set(trace)
    parent = _parent.set(None)
    try:
        yield trace
    finally:
        _parent.reset(parent)
        _trace.reset(token)


@contextmanager
def stage(name, started=None):
    trace = current_trace()
    if trace is None or not trace.enabled or len(trace.spans) >= MAX_SPANS:
        if trace and trace.enabled:
            trace.omitted_spans += 1
        yield Span(name)
        return
    started = perf_counter() if started is None else started
    span = Span(
        name, str(len(trace.spans) + 1), _parent.get(), round((started - trace.started) * 1000, 3)
    )
    trace.spans.append(span)
    parent = _parent.set(span.span_id)
    try:
        yield span
    except BaseException as error:
        span.status = "failed"
        span.error_type = type(error).__name__
        raise
    finally:
        span.duration_ms = round((perf_counter() - started) * 1000, 3)
        _parent.reset(parent)


def skipped(name, reason):
    with stage(name) as span:
        span.status = "skipped"
        span.fields(reason=reason)
    span.duration_ms = 0


def trace_stage(name):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with stage(name):
                return function(*args, **kwargs)

        return wrapped

    return decorate
