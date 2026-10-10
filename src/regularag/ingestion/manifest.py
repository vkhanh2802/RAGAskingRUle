import csv
import json
import re
from datetime import date
from pathlib import Path


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    documents: dict[str, dict[str, str]] = {}
    numbers: set[str] = set()
    required = (
        "document_id",
        "document_number",
        "title",
        "source_url",
        "sha256",
        "legal_status",
        "document_role",
    )
    with path.open(encoding="utf-8-sig", newline="") as manifest_file:
        for row in csv.DictReader(manifest_file):
            if any(not row.get(key) for key in required):
                raise ValueError("Manifest is missing required document metadata")
            if not re.fullmatch(r"[A-Za-z0-9_-]+", row["document_id"]):
                raise ValueError("Document ID must be a path-safe identifier")
            if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
                raise ValueError(f"Invalid source hash in manifest: {row['document_id']}")
            if row["document_id"] in documents or row["document_number"] in numbers:
                raise ValueError("Manifest contains duplicate document identity or number")
            row.setdefault("related_document_number", "")
            documents[row["document_id"]] = row
            numbers.add(row["document_number"])
    if not documents:
        raise ValueError("Manifest is empty")
    metadata_reviews = path.with_name("source_metadata_reviews.csv")
    if metadata_reviews.is_file():
        seen_metadata = set()
        with metadata_reviews.open(encoding="utf-8-sig", newline="") as file:
            for review in csv.DictReader(file):
                document = documents.get(review["document_id"])
                if document is None or document["sha256"] != review["source_sha256"]:
                    continue
                if review["document_id"] in seen_metadata:
                    raise ValueError("Duplicate source metadata review")
                seen_metadata.add(review["document_id"])
                for key in (
                    "effective_from",
                    "effective_evidence",
                    "applies_to",
                    "cohort_scope",
                    "metadata_note",
                ):
                    document[key] = review.get(key, "")
    scopes_path = path.with_name("cohort_scopes.csv")
    if scopes_path.exists():
        seen_scopes = set()
        with scopes_path.open(encoding="utf-8-sig", newline="") as scopes_file:
            for scope in csv.DictReader(scopes_file):
                document = documents.get(scope["document_id"])
                if document is None or document["sha256"] != scope["source_sha256"]:
                    continue  # Stale or unrelated review cannot assign a cohort range.
                if scope["document_id"] in seen_scopes:
                    raise ValueError("Duplicate cohort scope review")
                seen_scopes.add(scope["document_id"])
                bounds = [scope.get("cohort_from", ""), scope.get("cohort_to", "")]
                if not any(bounds) or not scope.get("cohort_evidence", "").strip():
                    raise ValueError("Cohort scope requires explicit bounds and evidence")
                if any(
                    value
                    and (not re.fullmatch(r"[0-9]{4}", value) or not 1980 <= int(value) <= 2100)
                    for value in bounds
                ):
                    raise ValueError("Invalid reviewed cohort range")
                if all(bounds) and int(bounds[0]) > int(bounds[1]):
                    raise ValueError("Invalid reviewed cohort range")
                document.update(
                    {
                        key: scope.get(key, "")
                        for key in ("cohort_from", "cohort_to", "cohort_evidence")
                    }
                )
    versions_path = path.with_name("document_versions.csv")
    if versions_path.is_file():
        seen_versions = set()
        with versions_path.open(encoding="utf-8-sig", newline="") as file:
            for review in csv.DictReader(file):
                document = documents.get(review["document_id"])
                if document is None or document["sha256"] != review["source_sha256"]:
                    continue
                if review["document_id"] in seen_versions:
                    raise ValueError("Duplicate document version review")
                seen_versions.add(review["document_id"])
                issued = review["issued_date"]
                if (
                    not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", issued)
                    or date.fromisoformat(issued).isoformat() != issued
                    or not review.get("issued_evidence", "").strip()
                    or issued != document.get("issued_date")
                ):
                    raise ValueError("Document version review must verify the manifest issue date")
                document["_version_review"] = json.dumps(review, ensure_ascii=False)
    relations_path = path.with_name("document_relations.csv")
    if relations_path.is_file():
        relations: dict[str, list[dict]] = {}
        with relations_path.open(encoding="utf-8-sig", newline="") as file:
            for relation in csv.DictReader(file):
                document = documents.get(relation["document_id"])
                if document is None or document["sha256"] != relation["source_sha256"]:
                    continue
                target = next(
                    (
                        row
                        for row in documents.values()
                        if row["document_number"] == relation["target_document_number"]
                    ),
                    None,
                )
                if target and target["sha256"] != relation["target_source_sha256"]:
                    continue  # A changed base requires a new relationship review.
                if (
                    relation["kind"] not in ("amends", "replaces")
                    or not relation.get("relation_evidence", "").strip()
                ):
                    raise ValueError("Relationship needs a verified amendment/replacement witness")
                if relation["target_document_number"] == document["document_number"]:
                    raise ValueError("Document cannot amend or replace itself")
                affected = json.loads(relation["affected_clauses_json"])
                if not isinstance(affected, dict) or any(
                    not re.fullmatch(r"[0-9]+[a-z]?", article)
                    or not isinstance(clauses, list)
                    or any(not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", c) for c in clauses)
                    for article, clauses in affected.items()
                ):
                    raise ValueError("Invalid reviewed article/clause mapping")
                if relation["kind"] == "amends" and not affected:
                    raise ValueError("Amendment requires affected article/clause mapping")
                if not re.fullmatch(r"[0-9a-f]{64}", relation["evidence_content_sha256"]):
                    raise ValueError("Relationship must bind an evidence chunk hash")
                if not relation["evidence_chunk_id"].startswith(document["document_id"] + ":"):
                    raise ValueError("Relationship evidence must belong to the updating source")
                owned = relations.setdefault(document["document_id"], [])
                if any(
                    r["target_document_number"] == relation["target_document_number"] for r in owned
                ):
                    raise ValueError("Duplicate document relationship")
                owned.append({**relation, "affected_clauses": affected})
        for document_id, owned in relations.items():
            documents[document_id]["_document_relations"] = json.dumps(owned, ensure_ascii=False)
    checks_path = path.with_name("source_freshness_checks.csv")
    if checks_path.is_file():
        with checks_path.open(encoding="utf-8-sig", newline="") as file:
            for check in csv.DictReader(file):
                document = documents.get(check["document_id"])
                if (
                    document
                    and document["sha256"] == check["source_sha256"]
                    and check["check_status"] in ("unchanged", "source_changed", "not_listed")
                ):
                    status = check["check_status"]
                    if status == "unchanged" and check["remote_sha256"] != document["sha256"]:
                        status = "source_changed"
                    document["source_check_status"] = status
                    if status == "unchanged":
                        document["source_checked_at"] = check["checked_at"]
    return documents
