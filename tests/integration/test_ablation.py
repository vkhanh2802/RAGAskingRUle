import os

import pytest

from regularag.evaluation import ablation, runner
from regularag.evaluation.runner import write_json
from tests.integration.test_evaluation_runner import evaluated as evaluated
from tests.integration.test_metadata_filters import scoped as scoped
from tests.integration.test_vector_baseline import artifacts as artifacts

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("REGULARAG_RUN_DB_TESTS") != "1", reason="PostgreSQL opt-in"),
]


def test_matrix_preserves_runs_and_binds_grouped_manual_reviews(
    database_settings, evaluated, tmp_path, monkeypatch
):
    monkeypatch.setattr(ablation, "verify_live_dataset", runner.verify_live_dataset)
    root = tmp_path / "matrix"
    labels = ["vector_only", "keyword_only"]
    for label in labels:
        ablation.run_variant(root, tmp_path, database_settings, evaluated, label)
    packet = ablation.export_matrix_review(root, tmp_path, database_settings, labels)
    assert packet["predictions"] == 4
    groups = ablation.load_json(root / "review_groups.json")["groups"]
    reviews = {}
    for key, group in groups.items():
        claims = [f"C{i}" for i in range(1, len(group["claims"]) + 1)]
        reviews[key] = {
            "covered_fact_ids": ["F1"] if group["question_id"] == "D01" else [],
            "faithful_claim_ids": claims,
            "relevant_claim_ids": claims,
            "forbidden_claims_present": False,
            "behaviour_correct": True,
            "reviewer": "synthetic-test",
            "note": "Actual synthetic quote/fact or missing scope verified.",
        }
    path = tmp_path / "reviews.json"
    decisions = {"groups_sha256": packet["groups_sha256"], "reviews": reviews}
    write_json(path, decisions)
    applied = ablation.apply_matrix_reviews(root, tmp_path, database_settings, labels, path)
    assert applied["reviewed_predictions"] == 4
    compared = ablation.compare_matrix(root, tmp_path, database_settings, labels)
    assert all(v["answer"]["correctness"]["value"] == 1 for v in compared["variants"])
    assert compared["held_out_inference_requests"] == 0
    with pytest.raises(ValueError, match="registered"):
        ablation.run_variant(root, tmp_path, database_settings, evaluated, labels[0])
    decisions["groups_sha256"] = "f" * 64
    write_json(path, decisions)
    with pytest.raises(ValueError, match="different predictions"):
        ablation.apply_matrix_reviews(root, tmp_path, database_settings, labels, path)
    metadata_path = root / labels[0] / "config.json"
    metadata = ablation.load_json(metadata_path)
    metadata["hardware"]["logical_cpu_count"] = 999
    write_json(metadata_path, metadata)
    with pytest.raises(ValueError, match="Incompatible"):
        ablation.validated_jobs(root, tmp_path, database_settings, labels)
