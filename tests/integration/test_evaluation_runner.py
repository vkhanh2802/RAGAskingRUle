import json
import os
from pathlib import Path

import pytest

from regularag.evaluation import runner
from regularag.evaluation.dataset import fetch_chunks
from regularag.generation.local import GeneratedAnswer
from regularag.generation.service import AnswerService
from regularag.retrieval.keyword import KeywordRepository
from regularag.retrieval.pipeline import RetrievalPipeline
from regularag.retrieval.repository import PgVectorRepository
from tests.integration.test_evaluation_dataset import _evidence
from tests.integration.test_metadata_filters import QueryEmbedder
from tests.integration.test_metadata_filters import scoped as scoped
from tests.integration.test_vector_baseline import artifacts as artifacts
from tests.unit.generation.test_service import FakeGenerator
from tests.unit.test_evaluation_metrics import example

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("REGULARAG_RUN_DB_TESTS") != "1", reason="PostgreSQL opt-in"),
]


@pytest.fixture
def evaluated(database_settings, scoped, monkeypatch):
    config, ids = scoped
    config.generation.response_policy = "verified_passages"
    config.behaviour.enabled = True
    chunks = fetch_chunks(database_settings, config, {f"{did}:chunk:0000" for did in ids})
    span = _evidence(chunks[f"{ids[0]}:chunk:0000"])
    _, _, case, _, _ = example()
    fact = case.required_facts[0].model_copy(update={"statement": "SharedQuery fixture text."})
    case = case.model_copy(
        update={
            "question": "SharedQuery",
            "reference_answer": "SharedQuery fixture source.",
            "required_facts": (fact,),
        }
    )
    clarify = case.model_copy(
        update={
            "question_id": "D02",
            "question": "Sau ba học kỳ chưa đạt ngoại ngữ bị giới hạn thế nào?",
            "expected_status": "needs_clarification",
            "category": "clarification",
            "required_facts": (),
            "support_evidence_ids": (),
            "required_clarifications": ("cohort_year", "applies_to", "programmes"),
        }
    )
    lock = {key: "a" * 64 for key in ("dataset_sha256", "corpus_sha256", "held_out_sha256")}
    monkeypatch.setattr(
        runner, "verify_live_dataset", lambda *args: ([case, clarify], {"E1": span}, chunks, lock)
    )

    def build(settings, actual_config):
        embedder = QueryEmbedder()
        pipeline = RetrievalPipeline(
            actual_config,
            embedder,
            PgVectorRepository(settings, actual_config),
            KeywordRepository(settings, actual_config),
        )
        generator = FakeGenerator(
            GeneratedAnswer(
                "answered",
                "",
                (),
                "fixture",
                passage_ids=("P1",),
                usage_input_tokens=20,
                usage_output_tokens=9,
            )
        )
        return AnswerService(actual_config, embedder, pipeline, generator)

    monkeypatch.setattr(runner, "build_answer_service", build)
    return config


def test_one_command_outputs_and_model_free_rescore(
    database_settings, evaluated, tmp_path, monkeypatch
):
    output = tmp_path / "run"
    result = runner.run_evaluation(database_settings, evaluated, tmp_path, output)
    assert result["questions"] == 2 and result["reviewed"] == 0
    assert all(
        (output / filename).exists()
        for filename in (
            "config.json",
            "predictions.jsonl",
            "retrieval_metrics.json",
            "answer_metrics.json",
            "summary.md",
            "operational_metrics.json",
            "review_packet.md",
        )
    )
    metadata = json.loads((output / "config.json").read_text(encoding="utf-8"))
    assert metadata["postflight_integrity"] and metadata["held_out_inference_requests"] == 0
    predictions = [
        json.loads(line)
        for line in (output / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert predictions[0]["http_status"] == 200
    assert predictions[0]["usage"]["output_tokens"] == 9
    assert predictions[1]["response"]["status"] == "needs_clarification"
    assert predictions[1]["retrieved"] == [] and predictions[1]["usage"]["output_tokens"] == 0

    def no_models(*args):
        raise AssertionError("Re-scoring must not load or call models")

    monkeypatch.setattr(runner, "build_answer_service", no_models)
    scored = runner.rescore(database_settings, evaluated, tmp_path, output)
    assert scored["questions"] == 2
    decision_rows = {}
    for prediction in predictions:
        pids = [p["passage_id"] for p in prediction["response"]["evidence_passages"] if p["cited"]]
        decision_rows[prediction["question_id"]] = {
            "covered_fact_ids": ["F1"] if prediction["question_id"] == "D01" else [],
            "faithful_passage_ids": pids,
            "relevant_passage_ids": pids,
            "forbidden_claims_present": False,
            "behaviour_correct": True,
            "reviewer": "synthetic-test",
            "note": "Fixture fact/quoted claim and explicit missing scope reviewed.",
        }
    decisions = {"predictions_sha256": metadata["predictions_sha256"], "reviews": decision_rows}
    review_path = tmp_path / "decisions.json"
    review_path.write_text(json.dumps(decisions), encoding="utf-8")
    reviewed = runner.rescore(
        database_settings, evaluated, tmp_path, output, decisions_path=review_path
    )
    assert reviewed["reviewed"] == 2 and reviewed["answer"]["correctness"]["value"] == 1
    decisions["predictions_sha256"] = "f" * 64
    review_path.write_text(json.dumps(decisions), encoding="utf-8")
    with pytest.raises(ValueError, match="different predictions"):
        runner.rescore(database_settings, evaluated, tmp_path, output, decisions_path=review_path)
    with pytest.raises(ValueError, match="exists"):
        runner.run_evaluation(database_settings, evaluated, tmp_path, output)
    predictions[0]["response"]["answer"] += " changed"
    (output / "predictions.jsonl").write_text(
        "\n".join(json.dumps(row) for row in predictions), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="predictions drifted"):
        runner.rescore(database_settings, evaluated, tmp_path, output)


def test_preflight_failure_retains_failure_without_model_calls(
    database_settings, tmp_path, monkeypatch
):
    from regularag.retrieval.config import RagBaselineConfig

    def invalid(*args):
        raise ValueError("Frozen corpus drifted")

    def no_models(*args):
        raise AssertionError("Preflight must gate all inference")

    monkeypatch.setattr(runner, "verify_live_dataset", invalid)
    monkeypatch.setattr(runner, "build_answer_service", no_models)
    config = RagBaselineConfig.from_path(Path("configs/rag/baseline.json"))
    output = tmp_path / "failed"
    with pytest.raises(ValueError, match="drifted"):
        runner.run_evaluation(database_settings, config, tmp_path, output)
    failure = json.loads((output / "failure.json").read_text(encoding="utf-8"))
    assert failure["reason"] == "Frozen corpus drifted"
    assert not (output / "predictions.jsonl").exists()
