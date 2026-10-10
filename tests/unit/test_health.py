from unittest.mock import Mock

from fastapi.testclient import TestClient

from regularag.api import health as health_module
from regularag.core.config import Settings
from regularag.db.health import DatabaseHealth, DatabaseUnavailableError
from regularag.main import create_app


def test_health_reports_database_and_pgvector(monkeypatch) -> None:
    database_health = DatabaseHealth(
        database="regularag",
        server_version="17.6",
        pgvector_version="0.8.1",
    )
    monkeypatch.setattr(
        health_module,
        "check_database",
        Mock(return_value=database_health),
    )

    app = create_app(Settings(environment="test"))
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "regularag-api",
        "environment": "test",
        "database": {
            "status": "ok",
            "name": "regularag",
            "server_version": "17.6",
            "pgvector_version": "0.8.1",
        },
    }


def test_health_is_degraded_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        health_module,
        "check_database",
        Mock(side_effect=DatabaseUnavailableError("database connection failed")),
    )

    app = create_app(Settings(environment="test"))
    response = TestClient(app).get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == {
        "status": "unavailable",
        "name": None,
        "server_version": None,
        "pgvector_version": None,
    }
