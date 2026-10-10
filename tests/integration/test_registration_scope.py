import json
import os
from hashlib import sha256

import psycopg
import pytest
from psycopg.types.json import Jsonb

from regularag.generation.local import GeneratedAnswer
from regularag.generation.service import AnswerService
from regularag.retrieval.filters import RetrievalFilters
from regularag.retrieval.keyword import KeywordRepository
from regularag.retrieval.pipeline import RetrievalPipeline
from regularag.retrieval.repository import PgVectorRepository
from tests.integration.test_freshness import family as family
from tests.integration.test_vector_baseline import artifacts as artifacts
from tests.unit.generation.test_service import FakeGenerator
from tests.unit.retrieval.test_registration_scope import QUESTION, TEXT

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("REGULARAG_RUN_DB_TESTS") != "1", reason="PostgreSQL opt-in"),
]


@pytest.mark.parametrize("summer", [False, True])
def test_sql_old_only_filter_can_answer_unchanged_main_but_not_amended_summer(
    database_settings, family, summer
):
    config, ids, embedder, _ = family
    config.freshness.policy_version = "clause-scoped-v2"
    config.generation.response_policy = "verified_passages"
    with psycopg.connect(str(database_settings.database_url)) as connection:
        connection.execute(
            "UPDATE chunks SET text=%s,content_sha256=%s,article='14',clauses=%s "
            "WHERE document_id=%s",
            (TEXT, sha256(TEXT.encode()).hexdigest(), Jsonb(["1", "2"]), ids[0]),
        )
        metadata = connection.execute(
            "SELECT metadata FROM documents WHERE document_id=%s", (ids[1],)
        ).fetchone()[0]
        metadata["_document_relations"][0]["affected_clauses"] = {"14": ["1"]}
        metadata["_document_relations"][0]["relation_evidence"] = (
            "Verified article14clause1itemb amendment"
        )
        connection.execute(
            "UPDATE documents SET metadata=%s WHERE document_id=%s", (Jsonb(metadata), ids[1])
        )

    class Selector(FakeGenerator):
        def generate(self, prompt):
            assert not summer, "A filtered applicable update must block before generation"
            assert "học kỳ hè" not in json.loads(prompt)["passages"][0]["text"]
            return GeneratedAnswer("answered", "", (), "raw", passage_ids=("P1",))

    pipeline = RetrievalPipeline(
        config,
        embedder,
        PgVectorRepository(database_settings, config),
        KeywordRepository(database_settings, config),
    )
    service = AnswerService(config, embedder, pipeline, Selector(None))
    question = "ĐTBC>=8 đăng ký học kỳ hè bao nhiêu tín chỉ?" if summer else QUESTION
    filters = RetrievalFilters(document_ids=[ids[0]])
    result = service.ask(question, retrieval_mode="vector", filters=filters)
    assert result.applied_filters == filters
    if summer:
        assert (
            result.status == "insufficient_evidence"
            and result.failure_reason == "latest_excluded_by_filters"
        )
    else:
        assert result.status == "answered" and "30 tín chỉ" in result.answer
        assert result.sources[0].document_id == ids[0] and result.sources[0].evidence_char_ranges
