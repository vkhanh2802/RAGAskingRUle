from copy import deepcopy
from pathlib import Path

import pytest

from regularag.evaluation.ablation import (
    VARIANTS,
    fixed_config_hash,
    groups_signature,
    review_groups,
    selection_key,
    semantic_bundle,
    variant_config,
)
from regularag.retrieval.config import RagBaselineConfig
from tests.unit.test_evaluation_metrics import example


def base():
    return RagBaselineConfig.from_path(Path("configs/rag/baseline.json"))


def test_four_variants_only_change_the_declared_retrieval_axes():
    original = base()
    digest = fixed_config_hash(original)
    for name, (mode, rerank) in VARIANTS.items():
        config = variant_config(original, name)
        assert config.retrieval.mode == mode and config.reranker.enabled == rerank
        assert fixed_config_hash(config) == digest
        assert config.generation == original.generation
    assert original.retrieval.mode == "hybrid" and original.reranker.enabled


@pytest.mark.parametrize("top_k", [0, 21, True, 8.5])
def test_top_k_sweep_rejects_invalid_values(top_k):
    with pytest.raises(ValueError, match="top-k"):
        variant_config(base(), "hybrid_rrf", top_k)


def test_budget_or_llm_changes_are_not_hidden_as_retrieval_ablation():
    first = base()
    changed = first.model_copy(deep=True)
    changed.generation.context_chunks += 1
    assert fixed_config_hash(changed, True) != fixed_config_hash(first, True)
    changed = first.model_copy(deep=True)
    changed.generation.model_revision = "b" * 40
    assert fixed_config_hash(changed, True) != fixed_config_hash(first, True)
    top_k = variant_config(first, "hybrid_rrf", 4)
    assert fixed_config_hash(top_k) != fixed_config_hash(first)
    assert fixed_config_hash(top_k, True) == fixed_config_hash(first, True)


def prediction():
    _, _, _, value, _ = example()
    return {**value, "question_id": "D01", "request": {"question": "summer cap"}}


def test_identical_semantics_can_map_new_local_pid_sid_without_reusing_response_hash():
    one = prediction()
    two = deepcopy(one)
    two["response"]["sources"][0]["source_id"] = "S2"
    two["response"]["evidence_passages"][0].update(passage_id="P4", source_id="S2")
    two["response"]["answer"] = two["response"]["answer"].replace("[S1]", "[S2]")
    two["response"]["generation_ms"] = 999.0
    assert semantic_bundle(one)[0] == semantic_bundle(two)[0]
    groups = review_groups({"left": {"predictions": [one]}, "right": {"predictions": [two]}})
    group = next(iter(groups.values()))
    assert len(groups) == 1
    assert (
        group["members"]["left"]["response_sha256"] != group["members"]["right"]["response_sha256"]
    )
    assert group["members"]["right"]["claim_to_passage"] == {"C1": "P4"}


@pytest.mark.parametrize("kind", ["source", "range", "scope", "question", "condition"])
def test_review_group_never_equates_different_source_scope_or_claim_content(kind):
    one = prediction()
    two = deepcopy(one)
    if kind == "source":
        two["response"]["sources"][0]["source_url"] = "https://example.test/other"
    elif kind == "range":
        two["response"]["evidence_passages"][0]["char_start"] += 1
    elif kind == "scope":
        two["response"]["resolved_scope"] = {"cohort_year": 2025}
    elif kind == "question":
        two["request"]["question"] = "other question"
    else:
        two["response"]["evidence_passages"][0]["text"] += " missing condition"
    assert semantic_bundle(one)[0] != semantic_bundle(two)[0]


def test_group_signature_binds_every_actual_response_including_new_variants():
    one = prediction()
    left = review_groups({"left": {"predictions": [one]}})
    both = review_groups({"left": {"predictions": [one]}, "right": {"predictions": [one]}})
    assert groups_signature(left) != groups_signature(both)


def test_quality_precedes_speed_and_unknown_is_not_a_perfect_score():
    def row(name, correct, precision, p95):
        return {
            "label": name,
            "answer": {
                "correctness": {"value": correct},
                "required_fact_recall": {"value": correct},
                "citation_support_precision": {"value": precision},
            },
            "operations": {"stages": {"end_to_end_ms": {"p95": p95, "p50": p95}}},
        }

    rows = [
        row("fast", 0.5, 1.0, 1),
        row("complete", 0.8, 0.7, 20),
        row("unknown", None, None, 0.1),
    ]
    assert sorted(rows, key=selection_key)[0]["label"] == "complete"
