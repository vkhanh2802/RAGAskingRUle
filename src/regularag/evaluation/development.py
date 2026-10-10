import csv
import json
from hashlib import sha256
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from regularag.retrieval.filters import RetrievalFilters
from regularag.retrieval.sql import READY_FILTER, retrieval_parameters


class CachedQueries:
    """Encode once so compared conditions use exactly the same query vector."""

    def __init__(self, embedder) -> None:
        self.embedder = embedder
        self.cache = {}

    def embed_query(self, question: str):
        if question not in self.cache:
            self.cache[question] = self.embedder.embed_query(question)
        return self.cache[question]


def load_questions(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    seen = set()
    for row in rows:
        if None in row or row["question_id"] in seen or row["split"] != "development":
            raise ValueError("Invalid development schema, split or duplicate question ID")
        seen.add(row["question_id"])
        if any(
            not row.get(key, "").strip()
            for key in (
                "question",
                "answer",
                "paraphrase_group",
                "evidence_ids",
                "evidence_locator",
            )
        ):
            raise ValueError("Development questions require answers and located evidence")
        row["filters"] = RetrievalFilters.model_validate_json(row.pop("filters_json")).model_dump(
            mode="json"
        )
        row["evidence_ids"] = list(dict.fromkeys(row["evidence_ids"].split(";")))
    if not rows:
        raise ValueError("No development questions")
    return rows


def dataset_hash(questions: list[dict]) -> str:
    payload = json.dumps(questions, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def fetch_evidence(settings, config, questions: list[dict]) -> dict:
    ids = sorted({chunk for question in questions for chunk in question["evidence_ids"]})
    with psycopg.connect(str(settings.database_url), row_factory=dict_row) as connection:
        rows = connection.execute(
            f"""
            SELECT c.chunk_id, c.document_id, d.document_number, d.source_url,
                   d.source_sha256, c.content_sha256, c.source_pdf_pages,
                   c.article, c.clauses, c.extraction_methods, c.quality_status
            FROM chunks c JOIN documents d ON d.document_id = c.document_id
            WHERE {READY_FILTER} AND c.chunk_id = ANY(%(ids)s)
            ORDER BY c.chunk_id
            """,
            {**retrieval_parameters(config), "ids": ids},
        ).fetchall()
    evidence = {row["chunk_id"]: row for row in rows}
    if set(evidence) != set(ids):
        raise ValueError("Gold evidence is absent or outside the approved indexed corpus")
    return evidence


def verify_evidence(snapshot: dict, current: dict) -> None:
    if snapshot != current:
        raise ValueError("Stale development evidence binding; review before evaluating")
