"""Fail closed on malformed payment IDs in Razorpay order history.

No external HTTP requests or production credentials are used.
"""
import pytest

from app.services import payments


@pytest.mark.parametrize("payment_id", [
    "pay_abc/def", "pay_abc?x=1", "pay_abc#fragment",
    "pay_abc def", "pay_abc\n", "pay_é", "pay_", "other_123",
])
def test_payment_history_rejects_noncanonical_ids(monkeypatch, payment_id):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "count": 1,
                "items": [{
                    "id": payment_id,
                    "order_id": "order_valid123",
                    "status": "failed",
                    "amount": 12000,
                    "currency": "INR",
                }],
            }

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(payments, "razorpay_enabled", lambda: True)
    monkeypatch.setattr(payments.httpx, "Client", Client)
    with pytest.raises(payments.PaymentProviderError, match="incomplete"):
        payments.list_razorpay_order_payments(provider_order_id="order_valid123")


def test_payment_history_accepts_canonical_id(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "count": 1,
                "items": [{
                    "id": "pay_valid_123",
                    "order_id": "order_valid123",
                    "status": "failed",
                    "amount": 12000,
                    "currency": "INR",
                }],
            }

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(payments, "razorpay_enabled", lambda: True)
    monkeypatch.setattr(payments.httpx, "Client", Client)
    assert payments.list_razorpay_order_payments(
        provider_order_id="order_valid123"
    )[0]["id"] == "pay_valid_123"
