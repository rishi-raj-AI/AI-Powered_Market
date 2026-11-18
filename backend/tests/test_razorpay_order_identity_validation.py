"""Reject unsafe Razorpay order identities before any network call."""
import pytest

from app.services import payments


@pytest.mark.parametrize("order_id", [
    "", " ", "order_", " order_123", "order_123 ", "order_123/path",
    "order_123?count=0", "order_123#fragment", "order_123\n",
    "order_१२३", None, 123,
])
def test_payment_history_rejects_malformed_order_identity_without_http(monkeypatch, order_id):
    class ForbiddenClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("provider must not be contacted")

    monkeypatch.setattr(payments, "razorpay_enabled", lambda: True)
    monkeypatch.setattr(payments.httpx, "Client", ForbiddenClient)
    with pytest.raises(payments.PaymentProviderError, match="Invalid Razorpay order identity"):
        payments.list_razorpay_order_payments(provider_order_id=order_id)
