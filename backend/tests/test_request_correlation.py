from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_request_id_is_preserved_on_response() -> None:
    request_id = "test-correlation-123"
    response = client.get("/", headers={"X-Request-ID": request_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


def test_request_id_is_generated_when_missing() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
