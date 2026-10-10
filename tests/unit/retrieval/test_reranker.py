from dataclasses import replace

import numpy as np
import pytest

from regularag.retrieval.config import RerankerConfig
from regularag.retrieval.pipeline import RetrievalPipeline, usable_evidence
from regularag.retrieval.reranker import CrossEncoderReranker
from tests.unit.generation.test_service import _chunk, _config
from tests.unit.retrieval.test_pipeline import CountingEmbedder, Repository


class CharacterTokenizer:
    def encode(self, first, second=None, add_special_tokens=True, **options):
        text = first + (second or "")
        return [ord(char) for char in text] + ([0, 0] if add_special_tokens else [])

    def decode(self, tokens, **options):
        return "".join(chr(token) for token in tokens)

    def num_special_tokens_to_add(self, pair):
        return 2


class TailModel:
    tokenizer = CharacterTokenizer()

    def __init__(self):
        self.pairs = []

    def predict(self, pairs, **options):
        self.pairs = pairs
        return np.array([3.0 if "TAIL_TARGET" in passage else -4.0 for _, passage in pairs])


def test_all_windows_are_scored_including_relevant_tail_and_provenance_is_preserved():
    reranker = CrossEncoderReranker(
        RerankerConfig(max_sequence_tokens=64, window_overlap_tokens=16)
    )
    model = TailModel()
    reranker._model = model
    first = replace(_chunk(), text="Distractor", rrf_score=0.03, dense_rank=1)
    second = replace(
        _chunk(), chunk_id="tail", text="x" * 180 + "TAIL_TARGET", rrf_score=0.01, keyword_rank=2
    )
    hits = reranker.rerank("Query", [first, second])
    assert [hit.chunk_id for hit in hits] == ["tail", first.chunk_id]
    assert hits[0].rerank_score == 3.0 and hits[0].rerank_windows > 1
    assert hits[0].rrf_score == 0.01 and hits[0].keyword_rank == 2
    assert all(len(model.tokenizer.encode(*pair)) <= 64 for pair in model.pairs)
    assert hits[1].rerank_score == -4.0 and usable_evidence(hits[1], _config())


def test_empty_pool_never_loads_model_and_oversized_query_is_not_silently_truncated():
    reranker = CrossEncoderReranker(RerankerConfig(max_sequence_tokens=64))
    assert reranker.rerank("Query", []) == [] and reranker._model is None
    reranker._model = TailModel()
    with pytest.raises(ValueError, match="question"):
        reranker.rerank("x" * 60, [_chunk()])


def test_invalid_model_logits_fail_closed():
    class InvalidModel(TailModel):
        def predict(self, pairs, **options):
            return np.full(len(pairs), np.nan)

    reranker = CrossEncoderReranker(RerankerConfig())
    reranker._model = InvalidModel()
    with pytest.raises(RuntimeError, match="nonfinite"):
        reranker.rerank("Query", [_chunk()])


def test_pipeline_reranks_candidates_before_top_k_and_disabled_mode_never_calls_reranker():
    class ReversingReranker:
        def __init__(self):
            self.calls = 0
            self.pool_size = 0

        def rerank(self, question, chunks):
            self.calls += 1
            self.pool_size = len(chunks)
            return list(reversed(chunks))

    config = _config()
    config.reranker.enabled = True
    hits = [replace(_chunk(), chunk_id=f"hit{index}") for index in range(25)]
    reranker = ReversingReranker()
    pipeline = RetrievalPipeline(
        config, CountingEmbedder(), Repository(hits), Repository([]), reranker=reranker
    )
    assert pipeline.search("Query", 1)[0].chunk_id == "hit24"
    assert reranker.pool_size == 25
    config.reranker.enabled = False
    pipeline = RetrievalPipeline(
        config, CountingEmbedder(), Repository(hits), Repository([]), reranker=reranker
    )
    assert pipeline.search("Query", 1)[0].chunk_id == "hit0" and reranker.calls == 1
