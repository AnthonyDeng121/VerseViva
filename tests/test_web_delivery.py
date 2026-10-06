from pathlib import Path

from fastapi.testclient import TestClient

from server.main import app


def test_built_h5_is_served_from_same_origin_when_available() -> None:
    index = Path("web/dist/index.html")
    if not index.is_file():
        return

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div id="root"></div>' in response.text


def test_api_remains_available_beside_static_h5() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
