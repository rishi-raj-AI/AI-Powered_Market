import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.payments import verify_razorpay_webhook_signature

client = TestClient(app)


def _signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_verify_razorpay_webhook_signature(monkeypatch) -> None:
    secret = "test-webhook-secret-with-enough-entropy"
    body = b'{"event":"payment.captured"}'
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", secret)
    assert verify_razorpay_webhook_signature(
        raw_body=body,
        received_signature=_signature(body, secret),
    )
    assert not verify_razorpay_webhook_signature(
        raw_body=body,
        received_signature="0" * 64,
    )


def test_webhook_rejects_invalid_signature(monkeypatch) -> None:
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "another-test-webhook-secret-123456")
    response = client.post(
        "/api/v1/payments/webhook",
        content=b'{"event":"payment.captured"}',
        headers={"x-razorpay-signature": "bad-signature", "content-type": "application/json"},
    )
    assert response.status_code == 400


def test_webhook_accepts_valid_signed_event(monkeypatch) -> None:
    secret = "signed-webhook-test-secret-123456789"
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", secret)
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_unknown",
                    "order_id": "order_test_unknown",
                }
            }
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    response = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={
            "x-razorpay-signature": _signature(body, secret),
            "content-type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
