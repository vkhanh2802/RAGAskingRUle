from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING, Protocol

from regularag.retrieval.config import RerankerConfig
from regularag.retrieval.repository import RetrievedChunk

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder


class Reranker(Protocol):
    def rerank(self, question: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]: ...


class CrossEncoderReranker:
    """Score every passage window; preserve retrieval scores separately from raw CE logits."""

    def __init__(self, config: RerankerConfig) -> None:
        self.config = config
        self._model: CrossEncoder | None = None

    def release(self) -> None:
        self._model = None

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            import torch
            from sentence_transformers import CrossEncoder

            torch.set_num_threads(self.config.cpu_threads)
            self._model = CrossEncoder(
                self.config.model_name,
                revision=self.config.model_revision,
                device=self.config.device,
                max_length=self.config.max_sequence_tokens,
                activation_fn=torch.nn.Identity(),
                trust_remote_code=False,
            )
            if self._model.num_labels != 1:
                raise ValueError("reranker must return one relevance logit per query/passage pair")
        return self._model

    def _windows(self, question: str, passage: str) -> list[str]:
        tokenizer = self.model.tokenizer
        query_tokens = tokenizer.encode(question, add_special_tokens=False, verbose=False)
        budget = (
            self.config.max_sequence_tokens
            - len(query_tokens)
            - tokenizer.num_special_tokens_to_add(pair=True)
        )
        if budget <= self.config.window_overlap_tokens + 8:
            raise ValueError("question leaves insufficient room for reranker passage windows")
        tokens = tokenizer.encode(passage, add_special_tokens=False, verbose=False)
        if not tokens:
            return [""]
        windows = []
        start = 0
        while start < len(tokens):
            end = min(start + budget, len(tokens))
            while end > start:
                text = tokenizer.decode(
                    tokens[start:end],
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False,
                )
                pair = tokenizer.encode(question, text, verbose=False)
                if len(pair) <= self.config.max_sequence_tokens:
                    break
                end -= 1
            if end <= start:
                raise ValueError("cannot fit passage text into the reranker token budget")
            windows.append(text)
            if end == len(tokens):
                break
            start = max(start + 1, end - self.config.window_overlap_tokens)
        return windows

    def rerank(self, question: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if not chunks:
            return []  # Disabled/empty requests do not load the model.
        if len(chunks) > self.config.candidate_k:
            raise ValueError("reranker candidate pool exceeds configured limit")
        pairs = []
        owners = []
        window_counts = []
        for index, chunk in enumerate(chunks):
            passage = f"{chunk.title}\nĐiều {chunk.article or '?'}\n{chunk.text}"
            windows = self._windows(question, passage)
            window_counts.append(len(windows))
            pairs.extend((question, text) for text in windows)
            owners.extend([index] * len(windows))
        # Sentence Transformers otherwise inherits the most recently loaded torch thread count.
        import torch

        torch.set_num_threads(self.config.cpu_threads)
        logits = self.model.predict(
            pairs, batch_size=self.config.batch_size, show_progress_bar=False
        )
        scores = [-math.inf] * len(chunks)
        for owner, raw_score in zip(owners, logits, strict=True):
            score = float(raw_score)
            if not math.isfinite(score):
                raise RuntimeError("reranker returned a nonfinite relevance score")
            scores[owner] = max(scores[owner], score)
        order = sorted(range(len(chunks)), key=lambda index: (-scores[index], index))
        return [
            replace(
                chunks[index],
                rank=rank,
                rerank_rank=rank,
                rerank_score=scores[index],
                rerank_windows=window_counts[index],
            )
            for rank, index in enumerate(order, 1)
        ]
