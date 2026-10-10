from dataclasses import dataclass
from pathlib import Path

import psycopg

from regularag.core.config import Settings


@dataclass(frozen=True, slots=True)
class MigrationResult:
    applied: tuple[str, ...]
    skipped: tuple[str, ...]


def apply_migrations(settings: Settings, migrations_directory: Path) -> MigrationResult:
    migration_paths = sorted(migrations_directory.glob("*.sql"))
    if not migration_paths:
        raise ValueError(f"No SQL migrations found in {migrations_directory}")

    applied: list[str] = []
    skipped: list[str] = []
    with psycopg.connect(str(settings.database_url)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        existing = {
            row[0] for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for migration_path in migration_paths:
            version = migration_path.stem
            if version in existing:
                skipped.append(version)
                continue
            connection.execute(migration_path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
            applied.append(version)

    return MigrationResult(tuple(applied), tuple(skipped))
