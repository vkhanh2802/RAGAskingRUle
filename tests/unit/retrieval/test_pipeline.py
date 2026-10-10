from dataclasses import replace

from regularag.retrieval.pipeline import RetrievalPipeline
from tests.unit.generation.test_service import _chunk, _config


class CountingEmbedder:
    def __init__(self) -> None:
        self.calls = 0

    def embed_query(self, question: str):
        self.calls += 1
        return [1, 0]


class Repository:
    def __init__(self, hits):
        self.hits = hits

    def search(self, query, limit):
        return self.hits[:limit]


def test_keyword_mode_never_loads_or_calls_embedding_and_accepts_small_fts_scores() -> None:
    embedder = CountingEmbedder()
    hit = replace(_chunk(), score=0.01, score_kind="ts_rank_cd", keyword_score=0.01)
    pipeline = RetrievalPipeline(_config(), embedder, Repository([]), Repository([hit]))

    assert pipeline.search("Question", 5, "keyword") == [replace(hit, first_stage_rank=1)]
    assert embedder.calls == 0


def test_hybrid_excludes_low_similarity_dense_hits_before_fusion() -> None:
    dense = replace(_chunk(), chunk_id="weak_dense", score=0.1)
    keyword = replace(_chunk(), chunk_id="keyword", score=0.01, score_kind="ts_rank_cd")
    pipeline = RetrievalPipeline(
        _config(), CountingEmbedder(), Repository([dense]), Repository([keyword])
    )

    result = pipeline.search("Question", 5, "hybrid")

    assert [hit.chunk_id for hit in result] == ["keyword"]
    assert result[0].score_kind == "rrf" and result[0].dense_rank is None


def test_explicit_document_reference_is_forwarded_to_dense_before_limit_and_keeps_amendment_scope():
    class ScopedDense(Repository):
        def search(self, query, limit, document_codes=()):
            assert document_codes == ("1393",)
            return self.hits[:limit]

    config = _config()
    config.retrieval.document_reference_policy = "shared-query-refs-v1"
    hit = replace(_chunk(), document_number="1393/QĐ-ĐHCNTT")
    pipeline = RetrievalPipeline(config, CountingEmbedder(), ScopedDense([hit]), Repository([]))
    result = pipeline.search("Quyết định1393 học kỳ hè đăng ký bao nhiêu tín chỉ?", 1)
    assert result[0].chunk_id == hit.chunk_id
