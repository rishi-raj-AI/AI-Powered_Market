"""Provider payment identities must be safe before any outbound lookup."""
import pytest

from app.services import payments


@pytest.mark.parametrize(
    "payment_id",
    [
        None,
        "",
        "pay_",
        " pay_123",
        "pay_123 ",
        "pay_123/../../orders",
        "pay_123?count=100",
        "pay_123#fragment",
        "pay_123%2Frefund",
        "pay_123\n",
        "pay_１２３",
        "order_123",
        123,
    ],
)
def test_payment_fetch_rejects_malformed_identity_without_network(monkeypatch, payment_id):
    def unexpected_network(*args, **kwargs):
        raise AssertionError("Malformed payment ID reached the HTTP client")

    monkeypatch.setattr(payments.httpx, "Client", unexpected_network)
    monkeypatch.setattr(payments, "razorpay_enabled", unexpected_network)

    with pytest.raises(payments.PaymentProviderError, match="Invalid Razorpay payment identity"):
        payments.fetch_razorpay_payment(provider_payment_id=payment_id)


def test_payment_fetch_accepts_canonical_identity_and_checks_provider_response(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"id": "pay_abc_123", "status": "captured"}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            assert url == "https://api.razorpay.com/v1/payments/pay_abc_123"
            return FakeResponse()

    monkeypatch.setattr(payments, "razorpay_enabled", lambda: True)
    monkeypatch.setattr(payments.httpx, "Client", FakeClient)
    assert payments.fetch_razorpay_payment(provider_payment_id="pay_abc_123")["status"] == "captured"
