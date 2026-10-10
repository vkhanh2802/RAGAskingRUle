from fastapi.testclient import TestClient

from regularag.core.config import Settings
from regularag.main import create_app


def test_demo_assets_and_catalog_are_available_without_loading_models():
    app = create_app(Settings(environment="test"))
    client = TestClient(app)
    page = client.get("/")
    assert page.status_code == 200 and 'lang="vi"' in page.text
    assert 'id="ask-form"' in page.text and 'id="source-list"' in page.text
    for asset in ("app.css", "app.mjs", "contract.mjs", "mark.svg"):
        assert client.get("/assets/" + asset).status_code == 200
    assert client.get("/assets/app.mjs").headers["content-type"].startswith("text/javascript")
    catalog = client.get("/api/v1/demo/catalog")
    assert catalog.status_code == 200
    assert len(catalog.json()["documents"]) == 15
    assert app.state.answer_service is None
    assert not {"local_path", "sha256", "_version_review"} & set(catalog.json()["documents"][0])


def test_catalog_failure_is_controlled_and_does_not_expose_local_paths(tmp_path):
    app = create_app(
        Settings(environment="test", source_manifest_path=tmp_path / "private-path.csv")
    )
    response = TestClient(app).get("/api/v1/demo/catalog")
    assert response.status_code == 503 and "private-path" not in response.text


def test_static_mount_never_serves_env_raw_or_heldout_files():
    client = TestClient(create_app(Settings(environment="test")))
    for path in (
        "/assets/.env",
        "/assets/data/evaluation/v1/questions.json",
        "/assets/%2e%2e/core/config.py",
        "/data/evaluation/v1/questions.json",
    ):
        assert client.get(path).status_code == 404
