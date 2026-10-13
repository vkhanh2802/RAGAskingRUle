import os

import pytest


@pytest.fixture(autouse=True)
def ci_has_no_model_downloads(monkeypatch):
    """CI uses the existing fake models; an accidental real weights download must fail."""
    if os.getenv("REGULARAG_CI_NO_MODELS") != "1":
        return
    import huggingface_hub
    import huggingface_hub._snapshot_download
    import huggingface_hub.file_download

    def forbidden(*args, **kwargs):
        raise AssertionError("CI must mock model inference/downloads, never fetch weights")

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", forbidden)
    monkeypatch.setattr(huggingface_hub, "snapshot_download", forbidden)
    monkeypatch.setattr(huggingface_hub.file_download, "hf_hub_download", forbidden)
    monkeypatch.setattr(huggingface_hub._snapshot_download, "snapshot_download", forbidden)
