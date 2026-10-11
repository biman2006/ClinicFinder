from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "clinic-discovery-api"}


def test_health_allows_configured_frontend_origin() -> None:
    response = client.get(
        "/health",
        headers={"Origin": "http://127.0.0.1:5500"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5500"
