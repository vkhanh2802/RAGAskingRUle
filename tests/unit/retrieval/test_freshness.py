from dataclasses import replace

import pytest

from regularag.generation.local import GeneratedAnswer
from regularag.generation.service import AnswerService
from regularag.retrieval.filters import RetrievalFilters
from regularag.retrieval.freshness import DocumentVersion, FreshnessPolicy, select_with_updates
from tests.unit.generation.test_service import (
    FakeEmbedder,
    FakeGenerator,
    FakeRetriever,
    _chunk,
    _config,
)


def version(number="1/QD", issued="2024-01-01", **changes):
    metadata = {
        "issued_date": issued,
        "_version_review": {
            "source_sha256": "a" * 64,
            "issued_date": issued,
            "issued_evidence": "Signature on PDF1",
        },
    }
    return DocumentVersion("doc", number, "a" * 64, metadata, True, True, **changes)


def relation(kind="amends", target="1/QD"):
    return {
        "source_sha256": "a" * 64,
        "target_source_sha256": "a" * 64,
        "target_document_number": target,
        "kind": kind,
        "affected_clauses": {"14": ["1"]},
        "evidence_chunk_id": "update:chunk:1",
        "evidence_content_sha256": "b" * 64,
        "relation_evidence": "Explicit amendment in article1",
    }


class Catalog:
    def __init__(self, versions, evidence):
        self.versions = versions
        self.update = evidence

    def catalog(self, filters):
        return self.versions

    def evidence(self, version, relation, filters):
        return self.update


def family(kind="amends"):
    base = version()
    update = version("2/QD", "2025-01-01")
    update.metadata["_document_relations"] = [relation(kind)]
    evidence = replace(
        _chunk(), chunk_id="update:chunk:1", document_number="2/QD", text="New cap is 12."
    )
    chunk = replace(
        _chunk(),
        document_role="base",
        related_document_number="2/QD",
        related_document_ready=True,
        article="14",
        clauses=("1",),
        text="Old cap is 10.",
    )
    return base, update, evidence, chunk


@pytest.mark.parametrize("kind", ["amends", "replaces"])
def test_old_affected_evidence_is_replaced_even_if_new_version_missed_first_stage(kind):
    base, update, evidence, chunk = family(kind)
    unrelated = version("99/QD", "2026-01-01")
    hits = FreshnessPolicy(Catalog([base, update, unrelated], evidence)).apply([chunk], None)
    assert [hit.chunk_id for hit in hits] == [evidence.chunk_id]
    assert hits[0].latest_document_number == "2/QD"


def test_unmodified_clause_keeps_base_and_reserves_the_verified_update_in_context():
    base, update, evidence, chunk = family()
    chunk = replace(chunk, article="15", clauses=("2",))
    hits = FreshnessPolicy(Catalog([base, update], evidence)).apply([chunk], None)
    base_hit = next(hit for hit in hits if hit.document_number == "1/QD")
    distracting = replace(_chunk(), chunk_id="unrelated", document_number="other")
    selected = select_with_updates([base_hit, distracting, hits[0]], 2)
    assert [hit.document_number for hit in selected] == ["1/QD", "2/QD"]
    assert base_hit.latest_issued_date == "2025-01-01"
    assert base_hit.required_update_chunk_ids == (evidence.chunk_id,)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"ready": False}, "latest_evidence_unavailable"),
        ({"coverage_status": "partial"}, "latest_evidence_unavailable"),
        ({"matches_scope": False}, "latest_excluded_by_filters"),
    ],
)
def test_unavailable_or_filtered_latest_version_never_silently_falls_back_to_old_rule(
    change, expected
):
    base, update, evidence, chunk = family()
    policy = FreshnessPolicy(Catalog([base, replace(update, **change)], evidence))
    hits = policy.apply([chunk], None)
    assert len(hits) == 1 and hits[0].freshness_failure == expected


def test_historical_cutoff_does_not_apply_a_future_amendment_or_legacy_amendment_gate():
    base, update, evidence, chunk = family()
    hits = FreshnessPolicy(Catalog([base, update], evidence)).apply(
        [chunk], RetrievalFilters(as_of="2024-06-01")
    )
    assert len(hits) == 1 and hits[0].text == "Old cap is 10."
    assert hits[0].amendment_required is False
    assert hits[0].freshness_status == "historical"
    assert hits[0].latest_document_number == "1/QD"


def test_relationship_or_version_review_cannot_survive_changed_source_hash():
    base, update, evidence, chunk = family()
    changed = replace(update, source_sha256="c" * 64)
    assert changed.issued_date is None and not changed.relations
    hits = FreshnessPolicy(Catalog([base, changed], evidence)).apply([chunk], None)
    assert hits[0].freshness_failure == "unverified_update_relation"


def test_changed_bound_update_chunk_abstains_instead_of_using_old_clause():
    base, update, _, chunk = family()
    hits = FreshnessPolicy(Catalog([base, update], None)).apply([chunk], None)
    assert hits[0].freshness_failure == "latest_evidence_changed"


@pytest.mark.parametrize("changed_source", ["base", "update"])
def test_known_remote_source_drift_blocks_current_answers_after_metadata_refresh(changed_source):
    base, update, evidence, chunk = family()
    changed = base if changed_source == "base" else update
    changed.metadata["source_check_status"] = "source_changed"
    hits = FreshnessPolicy(Catalog([base, update], evidence)).apply([chunk], None)
    assert len(hits) == 1 and hits[0].freshness_failure == "portal_source_drift"


def test_cyclic_update_relationships_are_rejected():
    base, update, evidence, chunk = family()
    base.metadata["_document_relations"] = [relation(target="2/QD")]
    with pytest.raises(ValueError, match="Cycle"):
        FreshnessPolicy(Catalog([base, update], evidence)).apply([chunk], None)


@pytest.mark.parametrize("budget_removes_update", [False, True])
def test_service_cannot_generate_after_latest_update_is_lost_by_top_k_or_token_budget(
    budget_removes_update,
):
    class UnusedGenerator(FakeGenerator):
        @property
        def input_token_limit(self):
            return 550

        def count_prompt_tokens(self, prompt):
            return len(prompt)

        def generate(self, prompt):
            raise AssertionError("Missing newest evidence must not reach generation")

    config = _config()
    config.freshness.enabled = True
    base = replace(
        _chunk(),
        freshness_status="base_with_amendment",
        required_update_chunk_ids=("update",),
        text="Base.",
    )
    update = replace(_chunk(), chunk_id="update", text="Long update. " * 100)
    chunks = [base, update] if budget_removes_update else [base]
    service = AnswerService(
        config,
        FakeEmbedder(),
        FakeRetriever(chunks),
        UnusedGenerator(GeneratedAnswer("answered", "Answer [S1]", ("S1",), "raw")),
    )
    result = service.ask("Question")
    assert result.status == "insufficient_evidence"
    assert result.failure_reason == "latest_not_in_context"
    assert not any(source.cited for source in result.sources)
