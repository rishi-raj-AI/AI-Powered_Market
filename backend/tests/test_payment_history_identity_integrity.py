"""Fail-closed Razorpay history validation for stock recovery.

All responses are synthetic. No credentials or network requests are used.
"""
import pytest

from app.services import payments
from app.services.payments import PaymentProviderError


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class _Client:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, *_args, **_kwargs):
        return _Response(self.payload)


@pytest.mark.parametrize(
    "items",
    [
        [
            {"id": "pay_same", "order_id": "order_test", "status": "failed"},
            {"id": "pay_same", "order_id": "order_test", "status": "captured"},
        ],
        [{"id": "pay_valid", "order_id": "order_other", "status": "failed"}],
        [{"id": "pay_invalid-id", "order_id": "order_test", "status": "failed"}],
        [{"id": None, "order_id": "order_test", "status": "failed"}],
    ],
)
def test_payment_history_rejects_unattributable_or_duplicate_records(monkeypatch, items):
    monkeypatch.setattr(payments, "razorpay_enabled", lambda: True)
    monkeypatch.setattr(
        payments.httpx, "Client", lambda **_kwargs: _Client({"items": items, "count": len(items)})
    )
    with pytest.raises(PaymentProviderError, match="incomplete"):
        payments.list_razorpay_order_payments(provider_order_id="order_test")


@pytest.mark.parametrize(
    "payload",
    [
        {"items": [], "count": True},
        {"items": [], "count": 1},
        {"items": [{"id": "pay_valid", "order_id": "order_test"}], "count": 0},
        {"items": "not-a-list", "count": 0},
    ],
)
def test_payment_history_rejects_incomplete_page_metadata(monkeypatch, payload):
    monkeypatch.setattr(payments, "razorpay_enabled", lambda: True)
    monkeypatch.setattr(payments.httpx, "Client", lambda **_kwargs: _Client(payload))
    with pytest.raises(PaymentProviderError, match="incomplete|invalid"):
        payments.list_razorpay_order_payments(provider_order_id="order_test")
