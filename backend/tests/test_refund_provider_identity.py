"""Refund provider identity must be validated before any outbound request."""
from decimal import Decimal

import pytest

from app.services import payments


@pytest.mark.parametrize(
    "provider_payment_id",
    [
        None,
        "",
        "pay_",
        "pay_abc ",
        " pay_abc",
        "pay_abc/def",
        "pay_abc?query=1",
        "pay_abc#fragment",
        "pay_abc%2Fdef",
        "pay_abc\\def",
        "pay_é",
        "order_abc",
        123,
    ],
)
def test_refund_rejects_malformed_payment_identity_without_http(monkeypatch, provider_payment_id):
    def unexpected_client(*args, **kwargs):
        pytest.fail("Invalid provider payment identity must not initiate HTTP")

    monkeypatch.setattr(payments.httpx, "Client", unexpected_client)
    with pytest.raises(payments.PaymentProviderError, match="Invalid Razorpay payment identity"):
        payments.create_razorpay_refund(
            provider_payment_id=provider_payment_id,
            amount=Decimal("10.00"),
            idempotency_key="refund:test",
        )


def test_refund_valid_identity_reaches_credential_gate(monkeypatch):
    monkeypatch.setattr(payments, "razorpay_enabled", lambda: False)
    with pytest.raises(payments.PaymentProviderUnavailable, match="credentials"):
        payments.create_razorpay_refund(
            provider_payment_id="pay_valid_123",
            amount=Decimal("10.00"),
            idempotency_key="refund:test",
        )
