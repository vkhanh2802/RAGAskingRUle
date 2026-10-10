from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from regularag.ingestion.manifest import load_manifest
from regularag.retrieval.config import RagBaselineConfig

router = APIRouter(tags=["demo"])
WEB_DIRECTORY = Path(__file__).resolve().parents[1] / "web"


class DemoStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        # Windows registry MIME mappings can label .mjs as text/plain.
        if path.endswith(".mjs") and response.status_code in (200, 304):
            response.headers["content-type"] = "text/javascript; charset=utf-8"
        return response


class CatalogDocument(BaseModel):
    document_id: str
    document_number: str
    title: str
    source_url: str
    domain: str
    document_type: str
    issued_date: str
    legal_status: str


class DemoCatalog(BaseModel):
    documents: list[CatalogDocument]
    retrieval_mode: str
    top_k: int
    pipeline_version: str
    generation_model: str
    corpus_note: str


@router.get("/", include_in_schema=False)
def demo_page() -> FileResponse:
    return FileResponse(WEB_DIRECTORY / "index.html", media_type="text/html")


@router.get("/api/v1/demo/catalog", response_model=DemoCatalog)
def catalog(request: Request) -> DemoCatalog:
    settings = request.app.state.settings
    try:
        config = RagBaselineConfig.from_path(settings.rag_config_path)
        manifest = load_manifest(settings.source_manifest_path)
    except (OSError, ValueError) as error:
        raise HTTPException(503, "Danh mục nguồn hoặc cấu hình demo chưa sẵn sàng.") from error
    documents = [
        CatalogDocument(**{key: row.get(key, "") for key in CatalogDocument.model_fields})
        for document_id, row in manifest.items()
        if document_id in config.retrieval.eligible_document_ids
    ]
    return DemoCatalog(
        documents=documents,
        retrieval_mode=config.retrieval.mode,
        top_k=config.retrieval.top_k,
        pipeline_version=config.pipeline_version,
        generation_model=config.generation.model_name,
        corpus_note="Danh mục nguồn công khai đã đăng ký; mức publication/coverage được "
        "kiểm tra khi hỏi. Ngày mới nhất trong corpus không tự xác nhận hiệu lực pháp lý.",
    )
