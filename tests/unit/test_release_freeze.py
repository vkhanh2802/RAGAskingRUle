from copy import deepcopy
from pathlib import Path

import pytest

from regularag.evaluation.dataset import canonical_hash, verify_freeze
from regularag.evaluation.release import claim_held_out_run, inference_source_hash, verify_release
from regularag.evaluation.runner import write_json
from regularag.retrieval.config import RagBaselineConfig


def test_test_inference_requires_preexisting_exact_code_config_and_corpus_lock(tmp_path):
    config = RagBaselineConfig.from_path(Path("configs/rag/t4_4_development.json"))
    _, _, lock = verify_freeze(Path("data/evaluation/v1"))
    with pytest.raises(ValueError, match="prior reviewed"):
        verify_release(None, config, lock)
    release = {
        "version": "release-freeze-v1",
        "config_sha256": canonical_hash(config.model_dump(mode="json")),
        "runtime_source_sha256": inference_source_hash(),
        **{key: lock[key] for key in ("dataset_sha256", "held_out_sha256", "corpus_sha256")},
    }
    path = tmp_path / "freeze.json"
    write_json(path, release)
    verify_release(path, config, lock)
    for field in ("config_sha256", "runtime_source_sha256", "held_out_sha256", "corpus_sha256"):
        bad = deepcopy(release)
        bad[field] = "f" * 64
        write_json(path, bad)
        with pytest.raises(ValueError, match="differs"):
            verify_release(path, config, lock)


def test_one_test_run_claim_cannot_be_silently_replayed(tmp_path):
    path = tmp_path / "release.json"
    ledger = claim_held_out_run(path, tmp_path / "test-run")
    assert ledger.exists()
    with pytest.raises(ValueError, match="already claimed"):
        claim_held_out_run(path, tmp_path / "another-test-run")
