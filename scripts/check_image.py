"""Inspect packaged runtime inputs without loading weights or reading configuration secrets."""

import json
import os
from pathlib import Path

import llama_cpp
import torch

from regularag.api.demo import WEB_DIRECTORY
from regularag.generation.llama import build_answer_grammar


def main():
    assert os.getuid() == 10001
    assert not Path(".env").exists()
    assert not any(Path("data/raw").rglob("*.pdf"))
    assert not any(Path("data/processed").rglob("*.jsonl"))
    assert (WEB_DIRECTORY / "index.html").is_file()
    assert (WEB_DIRECTORY / "app.mjs").is_file()
    assert build_answer_grammar(("P1", "P2")) is not None
    assert not torch.cuda.is_available()
    print(
        json.dumps(
            {
                "valid": True,
                "uid": os.getuid(),
                "packaged_ui": True,
                "torch_version": torch.__version__,
                "llama_cpp_version": llama_cpp.__version__,
                "source_pdfs_in_image": 0,
                "processed_traces_in_image": 0,
                "conditions": "Inspect bare image, not mounted operator assets/cache. "
                "No weights inference.",
            }
        )
    )


if __name__ == "__main__":
    main()
