"""Provider payment-list completeness is a money and stock safety gate."""
import pytest

from app.services import payments


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
        pass

    def get(self, *_args, **_kwargs):
        return _Response(self.payload)


@pytest.mark.parametrize(("payload", "accepted"), [
    ({"items": [], "count": 0}, True),
    ({"items": [{"id": "pay_1"}], "count": 1}, True),
    ({"items": [], "count": 1}, False),
    ({"items": [{"id": "pay_1"}], "count": 2}, False),
    ({"items": [{"id": "pay_1"}]}, False),
    ({"items": [], "count": True}, False),
    ({"items": [], "count": "0"}, False),
    ({"items": [], "count": -1}, False),
    ({"items": [None], "count": 1}, False),
    ({"items": [{"id": str(i)} for i in range(100)], "count": 100}, False),
])
def test_payment_history_requires_complete_consistent_provider_page(
    monkeypatch, payload, accepted,
):
    monkeypatch.setattr(payments, "razorpay_enabled", lambda: True)
    monkeypatch.setattr(
        payments.httpx, "Client", lambda **_: _Client(payload),
    )
    if accepted:
        assert payments.list_razorpay_order_payments(
            provider_order_id="order_test",
        ) == payload["items"]
    else:
        with pytest.raises(payments.PaymentProviderError, match="incomplete"):
            payments.list_razorpay_order_payments(provider_order_id="order_test")
