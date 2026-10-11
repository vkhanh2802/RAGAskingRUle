import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from regularag.evaluation.dataset import canonical_hash
from regularag.evaluation.integrity import verify_live_dataset


def inference_source_hash():
    root = Path.cwd()
    paths = sorted((root / "src/regularag").rglob("*.py"))
    paths.append(root / "scripts/run_evaluation.py")
    return canonical_hash(
        {path.relative_to(root).as_posix(): sha256(path.read_bytes()).hexdigest() for path in paths}
    )


def verify_release(path, config, lock):
    if path is None:
        raise ValueError("Held-out inference requires a prior reviewed development release freeze")
    release = json.loads(path.read_text(encoding="utf-8"))
    if (
        release["version"] != "release-freeze-v1"
        or release["config_sha256"] != canonical_hash(config.model_dump(mode="json"))
        or release["runtime_source_sha256"] != inference_source_hash()
        or any(
            release[key] != lock[key]
            for key in ("dataset_sha256", "held_out_sha256", "corpus_sha256")
        )
    ):
        raise ValueError("Code/config/dataset/corpus differs from the pre-test release freeze")
    return release


def claim_held_out_run(path, output):
    ledger = path.with_name(path.stem + "-held-out-run.json")
    if ledger.exists():
        raise ValueError("Held-out run already claimed for this release; preserve its predictions")
    with ledger.open("x", encoding="utf-8") as file:
        json.dump(
            {
                "claimed_at": datetime.now(UTC).isoformat(),
                "run_directory": output.as_posix(),
                "protocol": "One complete40 held-out run after releasefreeze; no test tuning",
            },
            file,
        )
    return ledger


def freeze_release(settings, config, dataset, development_run, output):
    from regularag.evaluation.runner import rescore

    if output.exists():
        raise ValueError("Release freeze exists; never overwrite the pre-test decision")
    _, _, _, lock = verify_live_dataset(dataset, settings, config)
    meta = json.loads((development_run / "config.json").read_text(encoding="utf-8"))
    if (
        meta["split"] != "development"
        or len(meta["question_ids"]) != 60
        or meta["runtime_source_sha256"] != inference_source_hash()
        or meta["held_out_inference_requests"] != 0
    ):
        raise ValueError("Release needs complete development inference with the exact current code")
    rescore(
        settings,
        config,
        dataset,
        development_run,
        review_path=development_run / "answer_reviews.json",
    )
    answers = json.loads((development_run / "answer_metrics.json").read_text(encoding="utf-8"))
    if answers["overall"]["reviewed"] != 60:
        raise ValueError("Development manual review must be complete before test selection")
    release = {
        "version": "release-freeze-v1",
        "frozen_at": datetime.now(UTC).isoformat(),
        "config": config.model_dump(mode="json"),
        "config_sha256": canonical_hash(config.model_dump(mode="json")),
        "runtime_source_sha256": inference_source_hash(),
        **{key: lock[key] for key in ("dataset_sha256", "held_out_sha256", "corpus_sha256")},
        "development_run": development_run.as_posix(),
        "development_predictions_sha256": meta["predictions_sha256"],
        "development_review_sha256": answers["review_sha256"],
        "development_quality": answers["overall"],
        "held_out_requests_before_freeze": 0,
        "conditions": "Development-selected code/config fixed before held-out inference; "
        "all quality failures retained; no tuning from held-out questions or predictions",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as file:
        json.dump(release, file, ensure_ascii=False, indent=2)
        file.write("\n")
    verify_release(output, config, lock)
    return release
