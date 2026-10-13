import sys
from pathlib import Path

from regularag.ingestion.pipeline import BaselineIngestionConfig
from regularag.retrieval.config import RagBaselineConfig
from scripts import download_models


def test_bootstrap_specs_preserve_model_revisions_and_only_download_bge_tokenizer():
    config = RagBaselineConfig.from_path(Path("configs/rag/final.json"))
    ingestion = BaselineIngestionConfig.from_path(Path("configs/ingestion/baseline.json"))
    specs = download_models.specifications(config, ingestion)
    assert [s["component"] for s in specs] == ["tokenizer", "embedding", "reranker", "generation"]
    assert specs[0]["revision"] == ingestion.tokenizer_revision
    assert not any(p.endswith(("bin", "safetensors")) for p in specs[0]["patterns"])
    for spec in specs[1:]:
        assert spec["revision"] == getattr(config, spec["component"]).model_revision
    assert specs[-1]["filename"] == config.generation.gguf_filename


def test_check_only_never_downloads_and_reports_missing_cache(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["download_models.py", "--check-only"])
    monkeypatch.setattr(download_models, "try_to_load_from_cache", lambda *args, **kwargs: None)

    def no_download(*args, **kwargs):
        raise AssertionError("Check-only must not fetch model weights")

    monkeypatch.setattr(download_models, "hf_hub_download", no_download)
    monkeypatch.setattr(download_models, "snapshot_download", no_download)
    assert download_models.main() == 1
    assert '"ready": false' in capsys.readouterr().out


def test_explicit_download_uses_exact_pins_and_checks_cache_afterward(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["download_models.py"])
    monkeypatch.setattr(
        download_models, "try_to_load_from_cache", lambda *args, **kwargs: "/cache/file"
    )
    monkeypatch.setattr(download_models, "snapshot_download", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(download_models, "hf_hub_download", lambda **kwargs: calls.append(kwargs))
    assert download_models.main() == 0
    assert len(calls) == 4 and all(len(call["revision"]) == 40 for call in calls)
    assert "allow_patterns" in calls[0] and "filename" in calls[-1]


def test_component_filter_does_not_load_other_models(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["download_models.py", "--component", "generation"])
    monkeypatch.setattr(
        download_models, "try_to_load_from_cache", lambda *args, **kwargs: "/cache/file"
    )
    monkeypatch.setattr(download_models, "hf_hub_download", lambda **kwargs: calls.append(kwargs))

    def no_snapshot(*args, **kwargs):
        raise AssertionError("Single GGUF request must not download other model repositories")

    monkeypatch.setattr(download_models, "snapshot_download", no_snapshot)
    assert download_models.main() == 0 and len(calls) == 1
