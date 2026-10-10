import json
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class EmbeddingConfig(BaseModel):
    model_name: str
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    dimension: int = Field(gt=0)
    device: Literal["cpu", "cuda"]
    batch_size: int = Field(gt=0)
    cpu_threads: int = Field(default=4, ge=1, le=32)
    pooling_version: Literal["window-mean-v1"] = "window-mean-v1"
    max_sequence_tokens: int = Field(gt=16)
    window_overlap_tokens: int = Field(ge=0)
    query_prefix: str
    document_prefix: str

    @model_validator(mode="after")
    def validate_window(self) -> "EmbeddingConfig":
        if self.window_overlap_tokens >= self.max_sequence_tokens:
            raise ValueError("embedding window overlap must be smaller than max sequence length")
        return self

    @property
    def fingerprint(self) -> str:
        payload = self.model_dump(exclude={"device", "batch_size", "cpu_threads"})
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(serialized.encode("utf-8")).hexdigest()


class RetrievalConfig(BaseModel):
    mode: Literal["vector", "keyword", "hybrid"] = "vector"
    top_k: int = Field(ge=1, le=20)
    candidate_k: int = Field(default=20, ge=1, le=100)
    minimum_score: float = Field(ge=-1, le=1)
    minimum_keyword_score: float = Field(default=0, ge=0)
    rrf_k: int = Field(default=60, ge=1)
    dense_weight: float = Field(default=1, gt=0)
    keyword_weight: float = Field(default=1, gt=0)
    keyword_query_version: Literal["vi-simple-v1"] = "vi-simple-v1"
    metadata_filter_version: Literal["evidence-metadata-v1"] = "evidence-metadata-v1"
    document_reference_policy: Literal["keyword-only-v1", "shared-query-refs-v1"] = (
        "keyword-only-v1"
    )
    eligible_document_ids: list[str] = Field(min_length=1)


class RerankerConfig(BaseModel):
    enabled: bool = False
    model_name: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    model_revision: str = Field(
        default="1427fd652930e4ba29e8149678df786c240d8825", pattern=r"^[0-9a-f]{40}$"
    )
    device: Literal["cpu", "cuda"] = "cpu"
    batch_size: int = Field(default=1, ge=1, le=32)
    cpu_threads: int = Field(default=2, ge=1, le=32)
    candidate_k: int = Field(default=30, ge=20, le=40)
    max_sequence_tokens: int = Field(default=512, ge=64, le=512)
    window_overlap_tokens: int = Field(default=32, ge=0)
    pooling_version: Literal["window-max-v1"] = "window-max-v1"

    @model_validator(mode="after")
    def validate_window(self) -> "RerankerConfig":
        if self.window_overlap_tokens >= self.max_sequence_tokens - 16:
            raise ValueError("reranker overlap must leave room for the question and passage")
        return self


class FreshnessConfig(BaseModel):
    enabled: bool = False
    policy_version: Literal["verified-relations-v1"] = "verified-relations-v1"


class BehaviourConfig(BaseModel):
    enabled: bool = False
    policy_version: Literal["clarify-scope-v1"] = "clarify-scope-v1"
    minimize_selected_passages: bool = True


class GenerationConfig(BaseModel):
    backend: Literal["transformers", "llama_cpp"] = "transformers"
    response_policy: Literal["abstractive", "verified_quotes", "verified_passages"] = "abstractive"
    model_name: str
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    device: Literal["cpu", "cuda"]
    dtype: Literal["float32", "bfloat16", "float16"] = "float32"
    gguf_filename: str | None = None
    max_new_tokens: int = Field(ge=32, le=1024)
    max_input_tokens: int = Field(default=4096, ge=256)
    cpu_threads: int = Field(default=4, ge=1, le=32)
    context_chunks: int = Field(ge=1, le=10)
    prompt_version: str
    max_passages: int = Field(default=8, ge=2, le=16)
    max_selected_passages: int = Field(default=4, ge=1, le=4)
    structured_retries: int = Field(default=1, ge=0, le=1)
    low_memory_mode: bool = False

    @model_validator(mode="after")
    def validate_backend(self) -> "GenerationConfig":
        if self.backend == "llama_cpp":
            if not self.gguf_filename or not self.gguf_filename.endswith(".gguf"):
                raise ValueError("llama_cpp requires a GGUF filename")
            if self.device != "cpu":
                raise ValueError("the baseline llama_cpp adapter uses CPU wheels")
        return self


class RagBaselineConfig(BaseModel):
    pipeline_version: str
    embedding: EmbeddingConfig
    retrieval: RetrievalConfig
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    freshness: FreshnessConfig = Field(default_factory=FreshnessConfig)
    behaviour: BehaviourConfig = Field(default_factory=BehaviourConfig)
    generation: GenerationConfig

    @classmethod
    def from_path(cls, path: Path) -> "RagBaselineConfig":
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
