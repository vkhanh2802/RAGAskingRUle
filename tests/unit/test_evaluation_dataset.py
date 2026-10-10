import json
from hashlib import sha256
from pathlib import Path
from shutil import copyfile

import pytest
from pydantic import ValidationError

from regularag.evaluation.dataset import (
    EvaluationCase,
    EvidenceSpan,
    artifact_hash,
    canonical_hash,
    load_evaluation_cases,
    read_cases,
    read_evidence,
    validate_splits,
    verify_freeze,
    verify_spans,
)

DIRECTORY = Path(__file__).parents[2] / "data/evaluation/v1"


@pytest.fixture
def dataset():
    return read_cases(DIRECTORY / "questions.json"), read_evidence(DIRECTORY / "evidence.json")


def test_real_authored_category_split_and_legacy_counts(dataset):
    cases, evidence = dataset
    authored = json.loads((DIRECTORY / "authoring.json").read_text(encoding="utf-8"))
    validate_splits(cases, evidence, set(authored["exposed_rule_families"]))
    assert len([case for case in cases if case.origin.startswith("frozen-development30:")]) == 30
    assert len([case for case in cases if case.split == "test"]) == 40
    assert all(case.review_note and case.reference_answer for case in cases)


@pytest.mark.parametrize("kind", ["family", "paraphrase", "exposure"])
def test_split_leakage_cannot_be_hidden_by_renaming_a_question(dataset, kind):
    cases, evidence = dataset
    cases = list(cases)
    exposed = set()
    if kind == "family":
        cases[60] = cases[60].model_copy(update={"rule_families": cases[0].rule_families})
    elif kind == "paraphrase":
        cases[60] = cases[60].model_copy(update={"paraphrase_group": cases[0].paraphrase_group})
    else:
        exposed.update(cases[60].rule_families)
    with pytest.raises(ValueError, match="leakage|crosses|tuned"):
        validate_splits(cases, evidence, exposed)


@pytest.mark.parametrize(
    "change",
    [
        {"required_facts": []},
        {"support_evidence_ids": []},
        {"contrast_evidence_ids": ["summer"]},
        {"unknown": "ignored"},
    ],
)
def test_invalid_answer_support_contract_is_rejected(dataset, change):
    case = dataset[0][0].model_dump(mode="json")
    with pytest.raises(ValidationError):
        EvaluationCase.model_validate({**case, **change})


def test_contrast_evidence_is_not_promoted_to_gold_for_abstention(dataset):
    case = next(case for case in dataset[0] if case.question_id == "D43")
    assert case.contrast_evidence_ids and not case.support_evidence_ids
    with pytest.raises(ValidationError):
        EvaluationCase.model_validate(
            {**case.model_dump(mode="json"), "support_evidence_ids": ["class_size"]}
        )


def _bound_span():
    text = "Heading\nHọc kỳ hè tối đa 12 tín chỉ.\nEnd"
    excerpt = "Học kỳ hè tối đa 12 tín chỉ."
    row = {
        "chunk_id": "doc:chunk:0",
        "document_id": "doc",
        "document_number": "1/QĐ",
        "source_url": "https://example.test/doc",
        "source_sha256": "a" * 64,
        "content_sha256": sha256(text.encode()).hexdigest(),
        "text": text,
        "source_pdf_pages": [2, 3],
        "article": None,
        "clauses": [],
        "extraction_methods": ["pymupdf_text"],
        "quality_status": "approved",
    }
    span = EvidenceSpan.model_validate(
        {
            **{key: value for key, value in row.items() if key != "text"},
            "evidence_id": "E1",
            "excerpt": excerpt,
            "char_start": text.index(excerpt),
            "char_end": text.index(excerpt) + len(excerpt),
            "excerpt_sha256": sha256(excerpt.encode()).hexdigest(),
            "locator": "PDF2-3 approved chunk range",
        }
    )
    return row, span


@pytest.mark.parametrize(
    "field,value",
    [
        ("text", "Changed source text"),
        ("source_sha256", "b" * 64),
        ("article", "14"),
        ("source_pdf_pages", [9]),
        ("quality_status", "review_required"),
    ],
)
def test_source_hash_page_quality_or_invented_article_drift_fails(field, value):
    row, span = _bound_span()
    with pytest.raises(ValueError):
        verify_spans({"E1": span}, {row["chunk_id"]: {**row, field: value}})


def test_unicode_offsets_and_excerpt_hash_are_verified():
    row, span = _bound_span()
    verify_spans({"E1": span}, {row["chunk_id"]: row})
    with pytest.raises(ValidationError):
        EvidenceSpan.model_validate({**span.model_dump(), "char_end": span.char_end + 1})
    with pytest.raises(ValidationError):
        EvidenceSpan.model_validate({**span.model_dump(), "excerpt_sha256": "b" * 64})


@pytest.fixture
def sealed(tmp_path, dataset):
    for name in ("questions.json", "evidence.json", "authoring.json", "manual_review.csv"):
        copyfile(DIRECTORY / name, tmp_path / name)
    cases, evidence = dataset
    values = [case.model_dump(mode="json") for case in cases]
    lock = {
        "dataset_sha256": canonical_hash(values),
        "held_out_sha256": canonical_hash([case for case in values if case["split"] == "test"]),
        "evidence_sha256": canonical_hash(
            [span.model_dump(mode="json") for span in evidence.values()]
        ),
        "files": {
            name: artifact_hash(tmp_path / name) for name in ("authoring.json", "manual_review.csv")
        },
    }
    (tmp_path / "freeze.json").write_text(json.dumps(lock), encoding="utf-8")
    return tmp_path


def test_evaluation_loader_defaults_to_development_and_requires_explicit_test(sealed):
    assert len(load_evaluation_cases(sealed)) == 60
    assert len(load_evaluation_cases(sealed, "test")) == 40
    with pytest.raises(ValueError):
        load_evaluation_cases(sealed, "all")


@pytest.mark.parametrize("file", ["questions.json", "evidence.json", "authoring.json"])
def test_sealed_labels_evidence_and_exposure_rules_cannot_be_silently_rebound(sealed, file):
    path = sealed / file
    value = json.loads(path.read_text(encoding="utf-8"))
    if file == "questions.json":
        value[-1]["reference_answer"] += " Changed gold."
    elif file == "evidence.json":
        value[0]["locator"] += " Invented article."
    else:
        value["exposed_rule_families"] = []
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="drifted"):
        verify_freeze(sealed)
