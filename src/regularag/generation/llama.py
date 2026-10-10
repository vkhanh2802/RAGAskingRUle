import json
from dataclasses import replace

from regularag.generation.local import (
    GeneratedAnswer,
    QuoteSelectionPayload,
    parse_passage_selection,
    parse_quote_selection,
    prompt_passage_ids,
)
from regularag.generation.prompt import escape_prompt_data, system_prompt
from regularag.retrieval.config import GenerationConfig


def build_answer_grammar(passage_ids: tuple[str, ...] | None = None):
    from llama_cpp import LlamaGrammar

    if passage_ids is not None:
        schema = {
            "type": "object",
            "properties": {
                "passage_ids": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(passage_ids)},
                    "maxItems": 4,
                }
            },
            "required": ["passage_ids"],
            "additionalProperties": False,
        }
        return LlamaGrammar.from_json_schema(json.dumps(schema), verbose=False)
    schema = QuoteSelectionPayload.model_json_schema()
    # Keep JSON Schema references used by nested quote objects visible to the converter.
    definitions = schema.get("$defs", {})
    quote_item = definitions.get("EvidenceQuotePayload", {})
    # Enforce quote length in Pydantic; expanding 800 optional grammar rules is expensive.
    quote_item["properties"]["quote"].pop("maxLength", None)
    schema["properties"]["evidence_quotes"] = {
        "type": "array",
        "items": quote_item,
        "maxItems": 2,
    }
    return LlamaGrammar.from_json_schema(json.dumps(schema), verbose=False)


class LlamaCppGenerator:
    """Pinned GGUF CPU generation, with JSON grammar and exact ChatML token accounting."""

    def __init__(self, config: GenerationConfig) -> None:
        self.config = config
        self._model = None
        self._grammar = None

    def _load(self) -> None:
        if self._model is not None:
            return
        from huggingface_hub import hf_hub_download
        from llama_cpp import Llama

        grammar = (
            build_answer_grammar() if self.config.response_policy != "verified_passages" else None
        )
        model_path = hf_hub_download(
            repo_id=self.config.model_name,
            filename=self.config.gguf_filename,
            revision=self.config.model_revision,
        )
        self._model = Llama(
            model_path=model_path,
            n_ctx=self.config.max_input_tokens + self.config.max_new_tokens,
            n_batch=256,
            n_threads=self.config.cpu_threads,
            n_threads_batch=self.config.cpu_threads,
            n_gpu_layers=0,
            verbose=False,
        )
        self._grammar = grammar

    @property
    def input_token_limit(self) -> int:
        return self.config.max_input_tokens

    def _prompt_tokens(self, prompt: str) -> list[int]:
        self._load()
        # Keep data from introducing ChatML role delimiters.
        prompt = escape_prompt_data(prompt)
        rendered = (
            f"<|im_start|>system\n{system_prompt(self.config.response_policy)}<|im_end|>\n"
            f"<|im_start|>user\n{prompt}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        return self._model.tokenize(rendered.encode("utf-8"), add_bos=False, special=True)

    def count_prompt_tokens(self, prompt: str) -> int:
        return len(self._prompt_tokens(prompt))

    def generate(self, prompt: str) -> GeneratedAnswer:
        if self.config.response_policy == "verified_passages":
            return self._select_passages(prompt)
        prompt_tokens = self._prompt_tokens(prompt)
        if len(prompt_tokens) > self.input_token_limit:
            raise ValueError("generation prompt exceeds the input token budget")
        response = self._model.create_completion(
            prompt=prompt_tokens,
            max_tokens=self.config.max_new_tokens,
            temperature=0,
            grammar=self._grammar,
            stop=["<|im_end|>"],
        )
        return replace(
            parse_quote_selection(response["choices"][0]["text"].strip()),
            usage_input_tokens=len(prompt_tokens),
            usage_output_tokens=response.get("usage", {}).get("completion_tokens"),
        )

    def _select_passages(self, prompt: str) -> GeneratedAnswer:
        ids = prompt_passage_ids(prompt)
        if not ids:
            return parse_passage_selection('{"passage_ids":[]}', ())
        grammar = build_answer_grammar(ids)
        outputs = []
        input_tokens = 0
        output_tokens = []
        current_prompt = prompt
        for _ in range(self.config.structured_retries + 1):
            tokens = self._prompt_tokens(current_prompt)
            if len(tokens) > self.input_token_limit:
                if outputs:
                    break
                raise ValueError("generation prompt exceeds the input token budget")
            response = self._model.create_completion(
                prompt=tokens,
                max_tokens=self.config.max_new_tokens,
                temperature=0,
                grammar=grammar,
                stop=["<|im_end|>"],
            )
            raw = response["choices"][0]["text"].strip()
            outputs.append(raw)
            input_tokens += len(tokens)
            output_tokens.append(response.get("usage", {}).get("completion_tokens"))
            result = parse_passage_selection(raw, ids)
            if result.failure_reason is None:
                break
            # Retry only structurally invalid output. Empty/unsupported selections are not coerced.
            payload = json.loads(prompt)
            payload["format_reminder"] = "Chỉ trả JSON passage_ids; dùng ID trong passages hoặc []."
            current_prompt = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return replace(
            result,
            attempts=len(outputs),
            raw_attempts=tuple(outputs),
            usage_input_tokens=input_tokens,
            usage_output_tokens=sum(output_tokens)
            if all(value is not None for value in output_tokens)
            else None,
        )

    def release(self) -> None:
        if self._model is not None:
            self._model.close()
            self._model = None
        self._grammar = None
