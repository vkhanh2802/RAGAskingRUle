from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Protocol

import numpy as np
from numpy.typing import NDArray

from regularag.retrieval.config import EmbeddingConfig

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

FloatVector = NDArray[np.float32]


class Embedder(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: list[str]) -> list[FloatVector]: ...

    def embed_query(self, text: str) -> FloatVector: ...


class SentenceTransformerEmbedder:
    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config
        self._model: SentenceTransformer | None = None

    def release(self) -> None:
        self._model = None

    @property
    def dimension(self) -> int:
        return self.config.dimension

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            import torch
            from sentence_transformers import SentenceTransformer

            torch.set_num_threads(self.config.cpu_threads)
            self._model = SentenceTransformer(
                self.config.model_name,
                revision=self.config.model_revision,
                device=self.config.device,
            )
            actual_dimension = self._model.get_embedding_dimension()
            if actual_dimension != self.config.dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.config.dimension}, "
                    f"got {actual_dimension}"
                )
            if self.config.max_sequence_tokens > self._model.max_seq_length:
                raise ValueError("embedding token limit exceeds the model's supported length")
            self._model.max_seq_length = self.config.max_sequence_tokens
        return self._model

    def _document_windows(self, text: str) -> list[str]:
        tokenizer = self.model.tokenizer
        prefix_tokens = tokenizer.encode(self.config.document_prefix, add_special_tokens=False)
        special_tokens = tokenizer.num_special_tokens_to_add(pair=False)
        window_size = self.config.max_sequence_tokens - len(prefix_tokens) - special_tokens
        if window_size <= self.config.window_overlap_tokens:
            raise ValueError("embedding window has no room for document tokens")

        token_ids = tokenizer.encode(text, add_special_tokens=False, verbose=False)
        if not token_ids:
            return [self.config.document_prefix]
        windows: list[str] = []
        start = 0
        while start < len(token_ids):
            end = min(start + window_size, len(token_ids))
            while end > start:
                window = (
                    self.config.document_prefix
                    + tokenizer.decode(
                        token_ids[start:end],
                        skip_special_tokens=True,
                        clean_up_tokenization_spaces=False,
                    ).strip()
                )
                # Decoding and re-encoding can change tokenization at the prefix boundary.
                encoded_length = len(tokenizer.encode(window, verbose=False))
                if encoded_length <= self.config.max_sequence_tokens:
                    break
                end -= 1
            if end <= start:
                raise ValueError("cannot fit any document text into the embedding window")
            windows.append(window)
            if end == len(token_ids):
                break
            start = max(start + 1, end - self.config.window_overlap_tokens)
        return windows

    def embed_documents(self, texts: list[str]) -> list[FloatVector]:
        if not texts:
            return []

        windows: list[str] = []
        owners: list[int] = []
        for owner, text in enumerate(texts):
            document_windows = self._document_windows(text)
            windows.extend(document_windows)
            owners.extend([owner] * len(document_windows))

        encoded = self.model.encode(
            windows,
            batch_size=self.config.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=True,
        ).astype(np.float32)
        grouped: dict[int, list[FloatVector]] = defaultdict(list)
        for owner, vector in zip(owners, encoded, strict=True):
            grouped[owner].append(vector)

        document_vectors: list[FloatVector] = []
        for owner in range(len(texts)):
            vector = np.mean(grouped[owner], axis=0, dtype=np.float32)
            norm = np.linalg.norm(vector)
            if norm == 0:
                raise ValueError(f"Embedding model returned a zero vector for document {owner}")
            document_vectors.append((vector / norm).astype(np.float32))
        return document_vectors

    def embed_query(self, text: str) -> FloatVector:
        query = self.config.query_prefix + text
        if len(self.model.tokenizer.encode(query, verbose=False)) > self.config.max_sequence_tokens:
            raise ValueError("question exceeds the embedding model's token limit")
        vector = self.model.encode(
            query,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype(np.float32)
        if vector.shape != (self.config.dimension,):
            raise ValueError(f"Unexpected query embedding shape: {vector.shape}")
        return vector
