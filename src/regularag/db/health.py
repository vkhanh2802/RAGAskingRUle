from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from regularag.core.config import Settings


@dataclass(frozen=True)
class DatabaseHealth:
    database: str
    server_version: str
    pgvector_version: str


class DatabaseUnavailableError(RuntimeError):
    """Raised when the database health query cannot complete."""


def check_database(settings: Settings) -> DatabaseHealth:
    try:
        connection = psycopg.connect(
            str(settings.database_url),
            connect_timeout=settings.database_connect_timeout_seconds,
            row_factory=dict_row,
        )
        with connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    current_database() AS database,
                    current_setting('server_version') AS server_version,
                    (
                        SELECT extversion
                        FROM pg_extension
                        WHERE extname = 'vector'
                    ) AS pgvector_version
                """
            )
            row = cursor.fetchone()
    except (OSError, psycopg.Error) as exc:
        raise DatabaseUnavailableError("database connection failed") from exc

    if row is None or row["pgvector_version"] is None:
        raise DatabaseUnavailableError("pgvector extension is unavailable")

    return DatabaseHealth(
        database=row["database"],
        server_version=row["server_version"],
        pgvector_version=row["pgvector_version"],
    )
