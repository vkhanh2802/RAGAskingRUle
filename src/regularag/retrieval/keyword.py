import re
import unicodedata
from dataclasses import dataclass, replace

import psycopg
from psycopg.rows import dict_row

from regularag.core.config import Settings
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.filters import METADATA_FILTER, RetrievalFilters, filter_parameters
from regularag.retrieval.repository import RetrievedChunk
from regularag.retrieval.sql import CHUNK_COLUMNS, READY_FILTER, retrieval_parameters

_STOP_WORDS = frozenset(
    {
        "toi",
        "cua",
        "cac",
        "nhung",
        "duoc",
        "cho",
        "theo",
        "quy",
        "dinh",
        "quyet",
        "truong",
        "hop",
        "nao",
        "la",
        "gi",
        "thi",
        "va",
        "voi",
        "ve",
        "mot",
        "co",
        "sinh",
        "vien",
        "bao",
        "nhieu",
        "can",
        "phai",
        "trong",
        "neu",
        "sau",
        "khi",
    }
)
_DOCUMENT_REF = re.compile(
    r"\b(\d{1,5})\s*/\s*(?:qd|tb)\s*[-–]?\s*dhcntt\b|"
    r"\b(?:quyet\s+dinh|quy\s+dinh|van\s+ban|thong\s+bao|qd|tb)\s*(?:so\s*)?(\d{1,5})\b"
)
_ARTICLE_REF = re.compile(r"\bdieu\s*(\d{1,3}[a-z]?)\b")


def normalize_vietnamese(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    return "".join(character for character in folded if not unicodedata.combining(character))


@dataclass(frozen=True, slots=True)
class KeywordQuery:
    normalized: str
    tsquery: str
    document_codes: tuple[str, ...]
    articles: tuple[str, ...]


def build_keyword_query(question: str) -> KeywordQuery:
    normalized = normalize_vietnamese(question)
    documents = tuple(
        dict.fromkeys(
            match.group(1) or match.group(2) for match in _DOCUMENT_REF.finditer(normalized)
        )
    )
    articles = tuple(dict.fromkeys(_ARTICLE_REF.findall(normalized)))
    words = re.findall(r"[^\W_]+", normalized, re.U)
    terms = list(dict.fromkeys(word for word in words if word not in _STOP_WORDS and len(word) > 1))
    # Only word lexemes enter this expression; user-supplied tsquery operators are discarded.
    expression = " | ".join(f"'{term}'" for term in terms[:80])
    if articles:
        article_query = " | ".join(f"('dieu' <-> '{article}')" for article in articles)
        expression = f"({expression}) & ({article_query})" if expression else article_query
    return KeywordQuery(normalized, expression, documents, articles)


class KeywordRepository:
    def __init__(self, settings: Settings, config: RagBaselineConfig) -> None:
        self.settings = settings
        self.config = config

    def search(
        self, question: str, limit: int, filters: RetrievalFilters | None = None
    ) -> list[RetrievedChunk]:
        if not 1 <= limit <= 100:
            raise ValueError("candidate retrieval limit must be between 1 and 100")
        query = build_keyword_query(question)
        if not query.tsquery:
            return []
        with psycopg.connect(
            str(self.settings.database_url),
            connect_timeout=self.settings.database_connect_timeout_seconds,
            row_factory=dict_row,
        ) as connection:
            rows = connection.execute(
                f"""
                WITH query AS (SELECT to_tsquery('simple', %(tsquery)s) AS expression)
                SELECT {CHUNK_COLUMNS}, ts_rank_cd(c.search_vector, query.expression, 32) AS score
                FROM chunks c JOIN documents d ON d.document_id = c.document_id CROSS JOIN query
                WHERE {READY_FILTER} AND {METADATA_FILTER}
                  AND c.search_vector @@ query.expression
                  AND (
                      %(codes)s::text[] = '{{}}'
                      OR split_part(d.document_number, '/', 1) = ANY(%(codes)s)
                  )
                ORDER BY score DESC, c.chunk_id
                LIMIT %(limit)s
                """,
                {
                    **retrieval_parameters(self.config),
                    **filter_parameters(filters),
                    "tsquery": query.tsquery,
                    "codes": list(query.document_codes),
                    "limit": limit,
                },
            ).fetchall()
        return [
            replace(
                RetrievedChunk(**row),
                score_kind="ts_rank_cd",
                retrieval_branches=("keyword",),
                rank=rank,
                keyword_rank=rank,
                keyword_score=float(row["score"]),
            )
            for rank, row in enumerate(rows, start=1)
        ]
