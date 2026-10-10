from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from regularag.db.health import DatabaseUnavailableError, check_database

router = APIRouter(tags=["health"])


class DatabaseHealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    name: str | None = None
    server_version: str | None = None
    pgvector_version: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    environment: str
    database: DatabaseHealthResponse


@router.get("/health", response_model=HealthResponse)
def health(request: Request, response: Response) -> HealthResponse:
    settings = request.app.state.settings

    try:
        database = check_database(settings)
    except DatabaseUnavailableError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="degraded",
            service=settings.service_name,
            environment=settings.environment,
            database=DatabaseHealthResponse(status="unavailable"),
        )

    return HealthResponse(
        status="ok",
        service=settings.service_name,
        environment=settings.environment,
        database=DatabaseHealthResponse(
            status="ok",
            name=database.database,
            server_version=database.server_version,
            pgvector_version=database.pgvector_version,
        ),
    )
