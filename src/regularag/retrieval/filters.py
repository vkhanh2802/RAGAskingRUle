import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DocumentId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]+$", max_length=100)]
MetadataTag = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=80)]


class RetrievalFilters(BaseModel):
    """AND between fields, OR within lists; absent fields impose no restriction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_ids: tuple[DocumentId, ...] = Field(default=(), max_length=20)
    domains: tuple[MetadataTag, ...] = Field(default=(), max_length=20)
    document_types: tuple[Literal["regulation", "decision", "procedure", "notice"], ...] = Field(
        default=(), max_length=4
    )
    applies_to: tuple[MetadataTag, ...] = Field(default=(), max_length=20)
    cohort_year: int | None = Field(default=None, ge=1980, le=2100, strict=True)
    as_of: date | None = None

    @field_validator("as_of", mode="before")
    @classmethod
    def validate_date(cls, value):
        if value is None or (isinstance(value, date) and not isinstance(value, datetime)):
            return value
        if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            return date.fromisoformat(value)
        raise ValueError("as_of must be an ISO calendar date YYYY-MM-DD")


METADATA_FILTER = """
    (%(filter_ids)s::text[] = '{}' OR d.document_id = ANY(%(filter_ids)s))
    AND (%(domains)s::text[] = '{}' OR d.domain = ANY(%(domains)s))
    AND (%(types)s::text[] = '{}' OR d.document_type = ANY(%(types)s))
    AND (%(audiences)s::text[] = '{}'
         OR string_to_array(d.applies_to, ';') && %(audiences)s::text[])
    AND (
        %(cohort)s::integer IS NULL OR (
            (d.cohort_from IS NOT NULL OR d.cohort_to IS NOT NULL)
            AND (d.cohort_from IS NULL OR d.cohort_from <= %(cohort)s)
            AND (d.cohort_to IS NULL OR d.cohort_to >= %(cohort)s)
        )
    )
    AND (
        %(as_of)s::date IS NULL OR (
            d.effective_from_date <= %(as_of)s
            AND (d.effective_to_date IS NULL OR d.effective_to_date >= %(as_of)s)
            AND (coalesce(d.metadata->>'effective_to', '') = ''
                 OR d.effective_to_date IS NOT NULL)
        )
    )
"""


def filter_parameters(filters: RetrievalFilters | None) -> dict:
    filters = filters or RetrievalFilters()
    return {
        "filter_ids": list(filters.document_ids),
        "domains": list(filters.domains),
        "types": list(filters.document_types),
        "audiences": list(filters.applies_to),
        "cohort": filters.cohort_year,
        "as_of": filters.as_of,
    }
