"""Provider payment history must reject ambiguous identities before downstream use."""
import pytest

from app.services import payments


@pytest.mark.parametrize("payment_id", [" pay_123", "pay_123 ", "   ", "\tpay_123", "pay_123\n"])
def test_provider_history_rejects_noncanonical_payment_ids(monkeypatch, payment_id):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "count": 1,
                "items": [{
                    "id": payment_id,
                    "order_id": "order_test",
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

        def __exit__(self, *_args):
            return None

        def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(payments, "razorpay_enabled", lambda: True)
    monkeypatch.setattr(payments.httpx, "Client", Client)
    with pytest.raises(payments.PaymentProviderError, match="incomplete"):
        payments.list_razorpay_order_payments(provider_order_id="order_test")


def test_provider_history_accepts_canonical_payment_id(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "count": 1,
                "items": [{
                    "id": "pay_123",
                    "order_id": "order_test",
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

        def __exit__(self, *_args):
            return None

        def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(payments, "razorpay_enabled", lambda: True)
    monkeypatch.setattr(payments.httpx, "Client", Client)
    assert payments.list_razorpay_order_payments(provider_order_id="order_test")[0]["id"] == "pay_123"
