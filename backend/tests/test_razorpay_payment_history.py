"""Razorpay order-payment history must be complete before stock is released.

All responses are mocked. No provider credentials, network calls, or financial
records are involved.
"""
import httpx
import pytest

from app.services import payments


class _Client:
    def __init__(self, response_body):
        self.response_body = response_body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url, *, auth, params):
        assert url.endswith("/v1/orders/order_test_history/payments")
        assert params == {"count": 100, "skip": 0}
        return httpx.Response(
            200,
            json=self.response_body,
            request=httpx.Request("GET", url),
        )


def _lookup(monkeypatch, response_body):
    monkeypatch.setattr(payments, "razorpay_enabled", lambda: True)
    monkeypatch.setattr(
        payments.httpx, "Client",
        lambda **_kwargs: _Client(response_body),
    )
    return payments.list_razorpay_order_payments(
        provider_order_id="order_test_history",
    )


def test_empty_history_with_explicit_zero_count_is_complete(monkeypatch):
    assert _lookup(monkeypatch, {"count": 0, "items": []}) == []


def test_complete_payment_history_is_returned(monkeypatch):
    items = [{"id": "pay_failed", "status": "failed"}]
    assert _lookup(monkeypatch, {"count": 1, "items": items}) == items


@pytest.mark.parametrize("response", [
    {"items": []},  # No count is not proof of zero payments.
    {"count": 1, "items": []},  # A payment was omitted.
    {"count": 0, "items": [{"id": "pay_hidden"}]},
    {"count": "0", "items": []},
    {"count": False, "items": []},
    {"count": -1, "items": []},
    {"count": 0.0, "items": []},
    {"count": 1, "items": [None]},
    {"count": 100, "items": [{} for _ in range(100)]},  # Pagination boundary.
])
def test_incomplete_or_malformed_history_never_certifies_nonpayment(
    monkeypatch, response,
):
    with pytest.raises(payments.PaymentProviderError, match="incomplete"):
        _lookup(monkeypatch, response)
