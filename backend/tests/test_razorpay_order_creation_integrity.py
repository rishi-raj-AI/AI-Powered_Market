"""Never hand checkout a provider order with the wrong amount or currency.

Synthetic HTTP responses only; no credentials, provider traffic or live money.
"""
from decimal import Decimal

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

    def post(self, url, *, auth, json):
        assert url == "https://api.razorpay.com/v1/orders"
        assert json["amount"] == 12000
        assert json["currency"] == "INR"
        assert json["receipt"] == "GO_TEST_ORDER"
        assert json["notes"]["gaonone_order_id"] == "test-commercial-order"
        return httpx.Response(
            200,
            json=self.response_body,
            request=httpx.Request("POST", url),
        )


def _create(monkeypatch, response_body):
    monkeypatch.setattr(payments.settings, "RAZORPAY_KEY_ID", "rzp_test_mock")
    monkeypatch.setattr(payments.settings, "RAZORPAY_KEY_SECRET", "mock-only-secret")
    monkeypatch.setattr(
        payments.httpx, "Client",
        lambda **_kwargs: _Client(response_body),
    )
    return payments.create_razorpay_order(
        amount=Decimal("120.00"),
        receipt="GO_TEST_ORDER",
        gaonone_order_id="test-commercial-order",
    )


def test_matching_provider_order_is_returned(monkeypatch):
    response = {"id": "order_mock", "amount": 12000, "currency": "INR"}
    assert _create(monkeypatch, response) == response


@pytest.mark.parametrize("response", [
    {},
    {"id": None, "amount": 12000, "currency": "INR"},
    {"id": "", "amount": 12000, "currency": "INR"},
    {"id": 123, "amount": 12000, "currency": "INR"},
    {"id": "order_mock", "currency": "INR"},
    {"id": "order_mock", "amount": None, "currency": "INR"},
    {"id": "order_mock", "amount": 11999, "currency": "INR"},
    {"id": "order_mock", "amount": True, "currency": "INR"},
    {"id": "order_mock", "amount": "12000", "currency": "INR"},
    {"id": "order_mock", "amount": 12000},
    {"id": "order_mock", "amount": 12000, "currency": "USD"},
    [],
])
def test_invalid_or_mismatched_provider_order_fails_closed(monkeypatch, response):
    with pytest.raises(payments.PaymentProviderError, match="mismatched"):
        _create(monkeypatch, response)
