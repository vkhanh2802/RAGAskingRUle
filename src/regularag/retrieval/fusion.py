from dataclasses import replace

from regularag.retrieval.repository import RetrievedChunk


def reciprocal_rank_fusion(
    dense: list[RetrievedChunk],
    keyword: list[RetrievedChunk],
    limit: int,
    k: int = 60,
    dense_weight: float = 1,
    keyword_weight: float = 1,
) -> list[RetrievedChunk]:
    if limit < 1 or k < 1 or dense_weight <= 0 or keyword_weight <= 0:
        raise ValueError("RRF needs positive limit, k and branch weights")
    combined: dict[str, RetrievedChunk] = {}
    for branch, hits, weight in (
        ("vector", dense, dense_weight),
        ("keyword", keyword, keyword_weight),
    ):
        seen = set()
        rank = 0
        for hit in hits:
            if hit.chunk_id in seen:
                continue
            seen.add(hit.chunk_id)
            rank += 1
            previous = combined.get(hit.chunk_id, hit)
            score = (previous.rrf_score or 0) + weight / (k + rank)
            combined[hit.chunk_id] = replace(
                previous,
                score=score,
                score_kind="rrf",
                rrf_score=score,
                retrieval_branches=tuple(
                    dict.fromkeys((*combined[hit.chunk_id].retrieval_branches, branch))
                )
                if hit.chunk_id in combined
                else (branch,),
                dense_rank=rank if branch == "vector" else previous.dense_rank,
                keyword_rank=rank if branch == "keyword" else previous.keyword_rank,
                dense_score=hit.score if branch == "vector" else previous.dense_score,
                keyword_score=hit.score if branch == "keyword" else previous.keyword_score,
            )
    ordered = sorted(
        combined.values(),
        key=lambda hit: (
            -hit.score,
            hit.keyword_rank if hit.keyword_rank is not None else float("inf"),
            hit.dense_rank if hit.dense_rank is not None else float("inf"),
            hit.chunk_id,
        ),
    )[:limit]
    return [replace(hit, rank=rank) for rank, hit in enumerate(ordered, start=1)]
