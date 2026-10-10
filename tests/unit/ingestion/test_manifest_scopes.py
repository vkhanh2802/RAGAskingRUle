import csv
import json

from regularag.ingestion.manifest import load_manifest


def test_cohort_review_is_bound_to_source_hash_and_is_not_parsed_from_a_year(tmp_path):
    row = {
        "document_id": "doc",
        "document_number": "1/QD",
        "title": "Cohort2026",
        "source_url": "https://example.test",
        "sha256": "a" * 64,
        "legal_status": "unknown",
        "document_role": "standalone",
    }
    manifest = tmp_path / "documents.csv"
    with manifest.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    assert "cohort_from" not in load_manifest(manifest)["doc"]
    scopes = tmp_path / "cohort_scopes.csv"
    header = "document_id,source_sha256,cohort_from,cohort_to,cohort_evidence\n"
    scopes.write_text(header + f"doc,{'b' * 64},2026,,Explicit clause\n", encoding="utf-8")
    assert "cohort_from" not in load_manifest(manifest)["doc"]
    scopes.write_text(header + f"doc,{'a' * 64},2026,,Explicit clause\n", encoding="utf-8")
    assert load_manifest(manifest)["doc"]["cohort_from"] == "2026"
    reviews = tmp_path / "source_metadata_reviews.csv"
    header = (
        "document_id,source_sha256,effective_from,effective_evidence,"
        "applies_to,cohort_scope,metadata_note\n"
    )
    reviews.write_text(
        header + f"doc,{'b' * 64},2024-09-01,Explicit clause,undergraduate_regular,,note\n",
        encoding="utf-8",
    )
    assert "effective_from" not in load_manifest(manifest)["doc"]
    reviews.write_text(
        header + f"doc,{'a' * 64},2024-09-01,Explicit clause,undergraduate_regular,,note\n",
        encoding="utf-8",
    )
    assert load_manifest(manifest)["doc"]["effective_from"] == "2024-09-01"


def test_issue_dates_and_successor_reviews_are_bound_to_both_source_versions(tmp_path):
    rows = [
        {
            "document_id": document_id,
            "document_number": number,
            "title": number,
            "source_url": "https://example.test",
            "sha256": source_hash,
            "legal_status": "unknown",
            "document_role": "base" if document_id == "base" else "amendment",
            "issued_date": issued,
        }
        for document_id, number, source_hash, issued in (
            ("base", "1/QD", "a" * 64, "2024-01-01"),
            ("update", "2/QD", "b" * 64, "2025-01-01"),
        )
    ]
    manifest = tmp_path / "documents.csv"
    with manifest.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    versions = tmp_path / "document_versions.csv"
    versions.write_text(
        "document_id,source_sha256,issued_date,issued_evidence\n"
        + f"update,{'c' * 64},2025-01-01,PDF1 signature\n",
        encoding="utf-8",
    )
    assert "_version_review" not in load_manifest(manifest)["update"]
    versions.write_text(
        "document_id,source_sha256,issued_date,issued_evidence\n"
        + f"update,{'b' * 64},2025-01-01,PDF1 signature\n",
        encoding="utf-8",
    )
    relation = {
        "document_id": "update",
        "source_sha256": "b" * 64,
        "kind": "amends",
        "target_document_number": "1/QD",
        "target_source_sha256": "a" * 64,
        "affected_clauses_json": '{"14":["1"]}',
        "evidence_chunk_id": "update:chunk:1",
        "evidence_content_sha256": "d" * 64,
        "relation_evidence": "PDF1 explicitly updates oldarticle14",
    }
    with (tmp_path / "document_relations.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(relation))
        writer.writeheader()
        writer.writerow(relation)
    loaded = load_manifest(manifest)
    assert json.loads(loaded["update"]["_version_review"])["issued_date"] == "2025-01-01"
    assert json.loads(loaded["update"]["_document_relations"])[0]["affected_clauses"] == {
        "14": ["1"]
    }
    rows[0]["sha256"] = "e" * 64
    with manifest.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    assert "_document_relations" not in load_manifest(manifest)["update"]
