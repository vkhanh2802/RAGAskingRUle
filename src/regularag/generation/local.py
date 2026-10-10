import json
import re
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from regularag.generation.prompt import escape_prompt_data, system_prompt
from regularag.retrieval.config import GenerationConfig

AnswerStatus = Literal["answered", "insufficient_evidence", "needs_clarification"]
_SOURCE_ID_PATTERN = re.compile(r"^S[1-9]\d*$")


@dataclass(frozen=True, slots=True)
class EvidenceQuote:
    source_id: str
    quote: str


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    status: AnswerStatus
    answer: str
    source_ids: tuple[str, ...]
    raw_output: str
    failure_reason: str | None = None
    evidence_quotes: tuple[EvidenceQuote, ...] = ()
    passage_ids: tuple[str, ...] = ()
    attempts: int = 1
    raw_attempts: tuple[str, ...] = ()


class Generator(Protocol):
    @property
    def input_token_limit(self) -> int: ...

    def count_prompt_tokens(self, prompt: str) -> int: ...

    def generate(self, prompt: str) -> GeneratedAnswer: ...


class EvidenceQuotePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    quote: str = Field(min_length=1, max_length=800)


class GenerationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    status: AnswerStatus
    answer: str = Field(min_length=1)
    source_ids: list[str]
    evidence_quotes: list[EvidenceQuotePayload] = Field(default_factory=list, max_length=2)


class QuoteSelectionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_quotes: list[EvidenceQuotePayload] = Field(max_length=2)


class PassageSelectionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    passage_ids: list[str] = Field(max_length=4)

    @model_validator(mode="after")
    def validate_ids(self) -> "PassageSelectionPayload":
        if len(set(self.passage_ids)) != len(self.passage_ids) or any(
            not re.fullmatch(r"P[1-9][0-9]*", pid) for pid in self.passage_ids
        ):
            raise ValueError("Passage IDs must be unique backend identifiers")
        return self


def prompt_passage_ids(prompt: str) -> tuple[str, ...]:
    payload = json.loads(prompt)
    ids = tuple(item["passage_id"] for item in payload["passages"])
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r"P[1-9][0-9]*", pid) for pid in ids):
        raise ValueError("Invalid backend passage registry")
    return ids


def parse_passage_selection(raw_output: str, allowed_ids: tuple[str, ...]) -> GeneratedAnswer:
    try:
        payload = PassageSelectionPayload.model_validate(json.loads(raw_output))
    except json.JSONDecodeError:
        return invalid_generated_answer(raw_output, "invalid_json")
    except ValidationError:
        return invalid_generated_answer(raw_output, "invalid_schema")
    if not set(payload.passage_ids).issubset(allowed_ids):
        return invalid_generated_answer(raw_output, "invalid_passage_ids")
    return GeneratedAnswer(
        "answered" if payload.passage_ids else "insufficient_evidence",
        "",
        (),
        raw_output,
        passage_ids=tuple(payload.passage_ids),
    )


def parse_quote_selection(raw_output: str) -> GeneratedAnswer:
    start, end = raw_output.find("{"), raw_output.rfind("}")
    if start < 0 or end <= start:
        return invalid_generated_answer(raw_output, "invalid_json")
    try:
        payload = QuoteSelectionPayload.model_validate(json.loads(raw_output[start : end + 1]))
    except (json.JSONDecodeError, ValidationError):
        return invalid_generated_answer(raw_output, "invalid_schema")
    quotes = tuple(EvidenceQuote(quote.source_id, quote.quote) for quote in payload.evidence_quotes)
    return GeneratedAnswer(
        status="answered" if quotes else "insufficient_evidence",
        answer="Đoạn trích liên quan.",
        source_ids=tuple(dict.fromkeys(quote.source_id for quote in quotes)),
        raw_output=raw_output,
        evidence_quotes=quotes,
    )


def invalid_generated_answer(raw_output: str, reason: str) -> GeneratedAnswer:
    return GeneratedAnswer(
        status="insufficient_evidence",
        answer="Mô hình baseline không tạo được câu trả lời có cấu trúc và citation hợp lệ.",
        source_ids=(),
        raw_output=raw_output,
        failure_reason=reason,
    )


def parse_generated_answer(raw_output: str) -> GeneratedAnswer:
    start = raw_output.find("{")
    end = raw_output.rfind("}")
    if start < 0 or end <= start:
        return invalid_generated_answer(raw_output, "invalid_json")

    try:
        payload = GenerationPayload.model_validate(json.loads(raw_output[start : end + 1]))
    except (json.JSONDecodeError, ValidationError):
        return invalid_generated_answer(raw_output, "invalid_schema")
    if not payload.answer.strip() or any(
        not _SOURCE_ID_PATTERN.fullmatch(source_id) for source_id in payload.source_ids
    ):
        return invalid_generated_answer(raw_output, "invalid_source_id")
    return GeneratedAnswer(
        status=payload.status,
        answer=payload.answer.strip(),
        source_ids=tuple(dict.fromkeys(payload.source_ids)),
        raw_output=raw_output,
        evidence_quotes=tuple(
            EvidenceQuote(quote.source_id, quote.quote) for quote in payload.evidence_quotes
        ),
    )


class TransformersGenerator:
    def __init__(self, config: GenerationConfig) -> None:
        self.config = config
        self._tokenizer = None
        self._model = None

    def _load_tokenizer(self) -> None:
        if self._tokenizer is not None:
            return
        from transformers import AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name,
            revision=self.config.model_revision,
        )

    @property
    def input_token_limit(self) -> int:
        self._load_tokenizer()
        return min(
            self.config.max_input_tokens,
            self._tokenizer.model_max_length - self.config.max_new_tokens,
        )

    def _render_prompt(self, prompt: str) -> str:
        self._load_tokenizer()
        return self._tokenizer.apply_chat_template(
            [
                {"role": "system", "content": system_prompt(self.config.response_policy)},
                {"role": "user", "content": escape_prompt_data(prompt)},
            ],
            tokenize=False,
            add_generation_prompt=True,
        )

    def count_prompt_tokens(self, prompt: str) -> int:
        rendered = self._render_prompt(prompt)
        return len(self._tokenizer.encode(rendered, add_special_tokens=False, verbose=False))

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM

        self._load_tokenizer()
        torch.set_num_threads(self.config.cpu_threads)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            revision=self.config.model_revision,
            dtype=getattr(torch, self.config.dtype),
        ).to(self.config.device)
        self._model.eval()

    def generate(self, prompt: str) -> GeneratedAnswer:
        import torch

        if self.count_prompt_tokens(prompt) > self.input_token_limit:
            raise ValueError("generation prompt exceeds the input token budget")
        self._load()
        if self._tokenizer is None or self._model is None:
            raise RuntimeError("generation model failed to load")

        model_inputs = self._tokenizer(
            self._render_prompt(prompt), return_tensors="pt", add_special_tokens=False
        ).to(self.config.device)
        with torch.inference_mode():
            output_ids = self._model.generate(
                **model_inputs,
                max_new_tokens=self.config.max_new_tokens,
                do_sample=False,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        generated_ids = output_ids[0, model_inputs["input_ids"].shape[1] :]
        raw_output = self._tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
        if self.config.response_policy == "verified_passages":
            return parse_passage_selection(raw_output, prompt_passage_ids(prompt))
        if self.config.response_policy == "verified_quotes":
            return parse_quote_selection(raw_output)
        return parse_generated_answer(raw_output)

    def release(self) -> None:
        self._model = None
