from dataclasses import replace
from typing import Literal

from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.embedding import Embedder
from regularag.retrieval.filters import RetrievalFilters
from regularag.retrieval.freshness import (
    FreshnessPolicy,
    PgFreshnessRepository,
    select_with_updates,
)
from regularag.retrieval.fusion import reciprocal_rank_fusion
from regularag.retrieval.keyword import build_keyword_query
from regularag.retrieval.registration import has_regular_credit_rule, registration_focus
from regularag.retrieval.repository import RetrievedChunk
from regularag.retrieval.reranker import CrossEncoderReranker, Reranker

RetrievalMode = Literal["vector", "keyword", "hybrid"]


def usable_evidence(chunk: RetrievedChunk, config: RagBaselineConfig) -> bool:
    if chunk.score_kind == "cosine_similarity":
        return chunk.score >= config.retrieval.minimum_score
    if chunk.score_kind == "ts_rank_cd":
        return chunk.score > config.retrieval.minimum_keyword_score
    if chunk.score_kind == "freshness_dependency":
        return chunk.freshness_status == "latest_verified_corpus" and not chunk.freshness_failure
    return chunk.score_kind == "rrf" and chunk.score > 0


class RetrievalPipeline:
    def __init__(
        self,
        config: RagBaselineConfig,
        embedder: Embedder,
        dense_repository,
        keyword_repository,
        reranker: Reranker | None = None,
        freshness: FreshnessPolicy | None = None,
    ) -> None:
        self.config = config
        self.embedder = embedder
        self.dense_repository = dense_repository
        self.keyword_repository = keyword_repository
        self.reranker = (
            reranker or CrossEncoderReranker(config.reranker) if config.reranker.enabled else None
        )
        self.freshness = freshness if config.freshness.enabled else None
        if config.freshness.enabled and self.freshness is None:
            settings = getattr(dense_repository, "settings", None)
            if settings is None:
                raise ValueError("freshness-enabled retrieval requires a document catalog")
            self.freshness = FreshnessPolicy(
                PgFreshnessRepository(settings, config),
                clause_scoped=config.freshness.policy_version == "clause-scoped-v2",
            )

    def release_models(self) -> None:
        import gc

        for model in (self.embedder, self.reranker):
            release = getattr(model, "release", None)
            if callable(release):
                release()
        gc.collect()

    def search(
        self,
        question: str,
        limit: int,
        mode: RetrievalMode | None = None,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievedChunk]:
        mode = mode or self.config.retrieval.mode
        if mode not in ("vector", "keyword", "hybrid") or not 1 <= limit <= 20:
            raise ValueError("Invalid retrieval mode or top-k")
        pool = self.ranked_candidates(question, mode, filters)
        return select_with_updates(pool, limit) if self.freshness is not None else pool[:limit]

    def ranked_candidates(
        self,
        question: str,
        mode: RetrievalMode | None = None,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievedChunk]:
        """Expose the actual ordered pool before top-k without another retrieval/model call."""
        pool = self.candidates(question, mode, filters)
        if self.reranker is not None and any(not hit.freshness_failure for hit in pool):
            pool = self.reranker.rerank(question, pool)
        if (
            self.freshness is not None
            and self.config.freshness.policy_version == "clause-scoped-v2"
            and pool
            and not pool[0].freshness_failure
            and pool[0].freshness_status == "unchanged_verified_clause"
        ):
            # Only a verified unchanged primary rule can discard lower-ranked blocked
            # candidates. Other primaries retain the context-wide freshness gate;
            # required companions still pass the selection/service budget guards.
            pool = [hit for hit in pool if not hit.freshness_failure]
        if (
            self.config.behaviour.enabled
            and self.config.behaviour.policy_version == "guarded-obligations-v2"
        ):
            from regularag.generation.passages import prioritize_support_sources

            pool = prioritize_support_sources(question, pool)
        return pool

    def candidates(
        self,
        question: str,
        mode: RetrievalMode | None = None,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievedChunk]:
        """Return the frozen first-stage pool for fair reranker on/off comparisons."""
        mode = mode or self.config.retrieval.mode
        if mode not in ("vector", "keyword", "hybrid"):
            raise ValueError("Invalid retrieval mode")
        pool_limit = (
            self.config.reranker.candidate_k
            if self.config.reranker.enabled
            else self.config.retrieval.candidate_k
        )
        candidates = max(pool_limit, self.config.retrieval.candidate_k, self.config.retrieval.top_k)
        dense = []
        keyword = []
        options = {"filters": filters} if filters is not None else {}
        dense_options = dict(options)
        if self.config.retrieval.document_reference_policy == "shared-query-refs-v1":
            codes = build_keyword_query(question).document_codes
            if codes:
                dense_options["document_codes"] = codes
        if mode in ("vector", "hybrid"):
            dense = [
                hit
                for hit in self.dense_repository.search(
                    self.embedder.embed_query(question), candidates, **dense_options
                )
                if usable_evidence(hit, self.config)
            ]
        if mode in ("keyword", "hybrid"):
            keyword = [
                hit
                for hit in self.keyword_repository.search(question, candidates, **options)
                if usable_evidence(hit, self.config)
            ]
        if mode == "vector":
            pool = dense[:pool_limit]
        elif mode == "keyword":
            pool = keyword[:pool_limit]
        else:
            pool = reciprocal_rank_fusion(
                dense,
                keyword,
                pool_limit,
                self.config.retrieval.rrf_k,
                self.config.retrieval.dense_weight,
                self.config.retrieval.keyword_weight,
            )
        pool = [replace(hit, first_stage_rank=rank) for rank, hit in enumerate(pool, 1)]
        if (
            self.freshness is not None
            and self.config.freshness.policy_version == "clause-scoped-v2"
            and registration_focus(question) == "regular"
        ):
            scoped = [hit for hit in pool if has_regular_credit_rule(hit.text)]
            if scoped:
                pool = scoped
        if self.freshness is not None:
            pool = select_with_updates(self.freshness.apply(pool, filters, question), pool_limit)
        return pool
