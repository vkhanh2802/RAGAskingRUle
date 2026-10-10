import json
from dataclasses import dataclass, replace
from datetime import date
from typing import Protocol

import psycopg
from psycopg.rows import dict_row

from regularag.core.config import Settings
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.filters import METADATA_FILTER, RetrievalFilters, filter_parameters
from regularag.retrieval.repository import RetrievedChunk
from regularag.retrieval.sql import CHUNK_COLUMNS, READY_FILTER, retrieval_parameters


def metadata_json(metadata: dict, key: str, default):
    value = metadata.get(key, default)
    return json.loads(value) if isinstance(value, str) else value


@dataclass(frozen=True, slots=True)
class DocumentVersion:
    document_id: str
    document_number: str
    source_sha256: str
    metadata: dict
    ready: bool
    matches_scope: bool
    coverage_status: str = "full"

    @property
    def issued_date(self) -> date | None:
        review = metadata_json(self.metadata, "_version_review", {})
        value = self.metadata.get("issued_date")
        if (
            review.get("source_sha256") != self.source_sha256
            or review.get("issued_date") != value
            or not review.get("issued_evidence")
        ):
            return None
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            return None

    @property
    def relations(self) -> tuple[dict, ...]:
        return tuple(
            relation
            for relation in metadata_json(self.metadata, "_document_relations", [])
            if relation.get("source_sha256") == self.source_sha256
            and relation.get("kind") in ("amends", "replaces")
            and relation.get("relation_evidence")
        )


class FreshnessRepository(Protocol):
    def catalog(self, filters: RetrievalFilters | None) -> list[DocumentVersion]: ...

    def evidence(
        self, version: DocumentVersion, relation: dict, filters: RetrievalFilters | None
    ) -> RetrievedChunk | None: ...


class PgFreshnessRepository:
    def __init__(self, settings: Settings, config: RagBaselineConfig) -> None:
        self.settings = settings
        self.config = config

    def catalog(self, filters: RetrievalFilters | None) -> list[DocumentVersion]:
        # Include blocked/out-of-allowlist versions: an unavailable known update must not
        # make an older document appear to be the latest retrievable version.
        with psycopg.connect(
            str(self.settings.database_url),
            connect_timeout=self.settings.database_connect_timeout_seconds,
            row_factory=dict_row,
        ) as connection:
            rows = connection.execute(
                f"""
                SELECT d.document_id, d.document_number, d.source_sha256, d.metadata,
                       d.coverage_status, ({METADATA_FILTER}) AS matches_scope,
                       d.ingestion_status = 'ready' AND d.retrieval_status = 'ready'
                       AND d.document_id = ANY(%(eligible_ids)s)
                       AND EXISTS (
                           SELECT 1 FROM chunks c WHERE c.document_id = d.document_id
                             AND c.embedding_model = %(model)s
                             AND c.embedding_revision = %(revision)s
                             AND c.embedding_fingerprint = %(fingerprint)s
                             AND c.quality_status = 'approved'
                       ) AS ready
                FROM documents d ORDER BY d.document_id
                """,
                {**retrieval_parameters(self.config), **filter_parameters(filters)},
            ).fetchall()
        return [DocumentVersion(**row) for row in rows]

    def evidence(self, version, relation, filters) -> RetrievedChunk | None:
        with psycopg.connect(
            str(self.settings.database_url),
            connect_timeout=self.settings.database_connect_timeout_seconds,
            row_factory=dict_row,
        ) as connection:
            row = connection.execute(
                f"""
                SELECT {CHUNK_COLUMNS}, 0.0::double precision AS score
                FROM chunks c JOIN documents d ON d.document_id = c.document_id
                WHERE {READY_FILTER} AND {METADATA_FILTER}
                  AND d.document_id = %(update_id)s AND d.source_sha256 = %(source_hash)s
                  AND c.chunk_id = %(chunk_id)s AND c.content_sha256 = %(content_hash)s
                """,
                {
                    **retrieval_parameters(self.config),
                    **filter_parameters(filters),
                    "update_id": version.document_id,
                    "source_hash": version.source_sha256,
                    "chunk_id": relation["evidence_chunk_id"],
                    "content_hash": relation["evidence_content_sha256"],
                },
            ).fetchone()
        return (
            replace(
                RetrievedChunk(**row),
                score_kind="freshness_dependency",
                retrieval_branches=("freshness",),
            )
            if row
            else None
        )


def _in_period(version: DocumentVersion, filters: RetrievalFilters | None, cutoff: date) -> bool:
    issued = version.issued_date
    if issued and issued > cutoff:
        return False
    effective = version.metadata.get("effective_from", "")
    if version.metadata.get("effective_evidence"):
        try:
            if date.fromisoformat(effective) > cutoff:
                return False
        except ValueError:
            pass  # An academic period is not a calendar date.
    if filters and filters.cohort_year is not None and version.metadata.get("cohort_evidence"):
        low = version.metadata.get("cohort_from")
        high = version.metadata.get("cohort_to")
        if low and filters.cohort_year < int(low) or high and filters.cohort_year > int(high):
            return False
    if filters and filters.applies_to:
        audiences = set(version.metadata.get("applies_to", "").split(";"))
        if audiences and not audiences.intersection(filters.applies_to):
            return False
    return True


def _affected(chunk: RetrievedChunk, relation: dict) -> bool:
    if relation["kind"] == "replaces":
        return True
    affected = relation["affected_clauses"]
    if chunk.article is None:
        return True
    if chunk.article not in affected:
        return False
    clauses = affected[chunk.article]
    # Unknown clause boundaries cannot certify that an affected article fragment is unchanged.
    return not clauses or not chunk.clauses or bool(set(clauses).intersection(chunk.clauses))


def select_with_updates(chunks: list[RetrievedChunk], limit: int) -> list[RetrievedChunk]:
    """Reserve companion slots before unrelated lower-ranked chunks; never expand user limits."""
    lookup = {chunk.chunk_id: chunk for chunk in chunks}
    selected: list[RetrievedChunk] = []
    selected_ids = set()
    for chunk in chunks:
        if chunk.chunk_id in selected_ids:
            continue
        group = [chunk] + [
            lookup[chunk_id]
            for chunk_id in chunk.required_update_chunk_ids
            if chunk_id in lookup and chunk_id not in selected_ids and chunk_id != chunk.chunk_id
        ]
        if len(selected) + len(group) > limit:
            if selected:
                continue
            group = group[:limit]  # The service detects missing required evidence and abstains.
        for item in group:
            if item.chunk_id not in selected_ids:
                selected.append(item)
                selected_ids.add(item.chunk_id)
        if len(selected) == limit:
            break
    return [replace(chunk, rank=rank) for rank, chunk in enumerate(selected, 1)]


class FreshnessPolicy:
    """Prefer verified successors within a document family, never global newest-date sorting."""

    def __init__(self, repository: FreshnessRepository) -> None:
        self.repository = repository

    def apply(
        self, chunks: list[RetrievedChunk], filters: RetrievalFilters | None
    ) -> list[RetrievedChunk]:
        versions = self.repository.catalog(filters)
        numbers = {version.document_number: version for version in versions}
        cutoff = filters.as_of if filters and filters.as_of else date.today()
        updates: dict[str, list[tuple[DocumentVersion, dict]]] = {}
        for version in versions:
            if not _in_period(version, filters, cutoff):
                continue
            for relation in version.relations:
                target = numbers.get(relation["target_document_number"])
                if target and relation.get("target_source_sha256") != target.source_sha256:
                    continue
                updates.setdefault(relation["target_document_number"], []).append(
                    (version, relation)
                )

        def successors(number: str, seen: frozenset[str] = frozenset()):
            if number in seen:
                raise ValueError("Cycle in verified document relationships")
            found = []
            for update, relation in updates.get(number, []):
                found.append((update, relation))
                found.extend(successors(update.document_number, seen | {number}))
            return found

        evidence_cache: dict[str, RetrievedChunk | None] = {}
        candidates: dict[str, RetrievedChunk] = {}
        for chunk in chunks:
            version = numbers.get(chunk.document_number)
            if version is None or version.issued_date is None:
                candidates[chunk.chunk_id] = replace(
                    chunk,
                    freshness_status="blocked_latest",
                    freshness_failure="unverified_issue_date",
                )
                continue
            if not _in_period(version, filters, cutoff):
                continue
            if version.metadata.get("source_check_status") in ("source_changed", "not_listed"):
                candidates[chunk.chunk_id] = replace(
                    chunk,
                    freshness_status="blocked_latest",
                    freshness_failure="portal_source_drift",
                )
                continue
            related = successors(chunk.document_number)
            latest = max(
                [version] + [update for update, _ in related],
                key=lambda item: item.issued_date or date.max,
            )
            failure = None
            if chunk.document_role == "base" and chunk.related_document_number:
                known = numbers.get(chunk.related_document_number)
                if not related and (known is None or _in_period(known, filters, cutoff)):
                    failure = "unverified_update_relation"
            required = []
            for update, relation in related:
                if update.metadata.get("source_check_status") in ("source_changed", "not_listed"):
                    failure = "portal_source_drift"
                elif update.issued_date is None:
                    failure = "unverified_update_date"
                elif not update.matches_scope:
                    failure = "latest_excluded_by_filters"
                elif not update.ready or (
                    relation["kind"] == "amends" and update.coverage_status != "full"
                ):
                    failure = "latest_evidence_unavailable"
                evidence_id = relation["evidence_chunk_id"]
                if evidence_id not in evidence_cache:
                    evidence_cache[evidence_id] = (
                        self.repository.evidence(update, relation, filters) if not failure else None
                    )
                evidence = evidence_cache[evidence_id]
                if evidence is None:
                    failure = failure or "latest_evidence_changed"
                else:
                    required.append(evidence_id)
                    candidates.setdefault(
                        evidence_id,
                        replace(
                            evidence,
                            first_stage_rank=chunk.first_stage_rank,
                            freshness_status="latest_verified_corpus",
                            latest_document_number=update.document_number,
                            latest_issued_date=update.issued_date.isoformat(),
                        ),
                    )
            direct = updates.get(chunk.document_number, [])
            if not failure and any(_affected(chunk, relation) for _, relation in direct):
                continue  # The old amended clause is never offered to the generator.
            candidates[chunk.chunk_id] = replace(
                chunk,
                freshness_status=(
                    "blocked_latest"
                    if failure
                    else "historical"
                    if filters and filters.as_of
                    else "base_with_amendment"
                    if related
                    else "latest_verified_corpus"
                ),
                latest_document_number=latest.document_number,
                latest_issued_date=latest.issued_date.isoformat() if latest.issued_date else None,
                required_update_chunk_ids=tuple(dict.fromkeys(required)),
                freshness_failure=failure,
                amendment_required=bool(related) if chunk.document_role == "base" else True,
            )
        return list(candidates.values())
