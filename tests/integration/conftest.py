from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from regularag.core.config import Settings
from regularag.db.migrations import apply_migrations

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def database_settings():
    settings = Settings()
    schema = f"regularag_test_{uuid4().hex}"
    with psycopg.connect(str(settings.database_url), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    options = urlencode({"options": f"-csearch_path={schema},public"})
    url = str(settings.database_url)
    separator = "&" if "?" in url else "?"
    isolated = settings.model_copy(update={"database_url": f"{url}{separator}{options}"})
    try:
        apply_migrations(isolated, ROOT / "scripts/db/migrations")
        yield isolated
    finally:
        with psycopg.connect(str(settings.database_url), autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
