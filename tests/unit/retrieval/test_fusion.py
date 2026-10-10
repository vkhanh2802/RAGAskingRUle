from dataclasses import replace

import pytest

from regularag.retrieval.fusion import reciprocal_rank_fusion
from tests.unit.generation.test_service import _chunk


def _hit(name: str, score: float = 0.8):
    return replace(_chunk(), chunk_id=name, score=score)


def test_rrf_merges_common_evidence_and_reports_both_branch_ranks() -> None:
    dense = [_hit("a"), _hit("b")]
    keyword = [_hit("b", 0.05), _hit("c", 0.03)]

    results = reciprocal_rank_fusion(dense, keyword, 3)

    assert results[0].chunk_id == "b"
    assert results[0].score == pytest.approx(1 / 62 + 1 / 61)
    assert results[0].dense_rank == 2 and results[0].keyword_rank == 1
    assert results[0].dense_score == 0.8 and results[0].keyword_score == 0.05
    assert results[0].retrieval_branches == ("vector", "keyword")
    assert results[0].score_kind == "rrf"
    assert len({hit.chunk_id for hit in results}) == 3


def test_duplicate_branch_hits_do_not_inflate_rrf_and_empty_branch_is_supported() -> None:
    results = reciprocal_rank_fusion([_hit("a"), _hit("a"), _hit("b")], [], 2)

    assert results[0].score == pytest.approx(1 / 61)
    assert results[1].dense_rank == 2
    assert reciprocal_rank_fusion([], [], 5) == []


def test_rrf_ties_are_deterministic_and_favor_keyword_rank_then_chunk_id() -> None:
    first = reciprocal_rank_fusion([_hit("a")], [_hit("b")], 2)
    second = reciprocal_rank_fusion([_hit("a")], [_hit("b")], 2)

    assert [hit.chunk_id for hit in first] == ["b", "a"]
    assert first == second
