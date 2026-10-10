from threading import Lock

from fastapi import FastAPI

from regularag.api.ask import router as ask_router
from regularag.api.demo import WEB_DIRECTORY, DemoStaticFiles
from regularag.api.demo import router as demo_router
from regularag.api.health import router as health_router
from regularag.core.config import Settings, get_settings
from regularag.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    app = FastAPI(
        title="RegulaRAG API",
        version="0.1.0",
        docs_url="/docs" if resolved_settings.environment != "production" else None,
        redoc_url=None,
    )
    app.state.settings = resolved_settings
    app.state.answer_service = None
    app.state.answer_service_lock = Lock()
    app.include_router(health_router)
    app.include_router(ask_router)
    app.include_router(demo_router)
    app.mount("/assets", DemoStaticFiles(directory=WEB_DIRECTORY), name="demo-assets")
    return app


app = create_app()
