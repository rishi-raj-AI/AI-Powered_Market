from fastapi.testclient import TestClient

from app.main import app


def test_request_id_is_generated_and_returned() -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_request_id_is_propagated_from_caller() -> None:
    response = TestClient(app).get("/", headers={"X-Request-ID": "order-delivery-payment-123"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "order-delivery-payment-123"
