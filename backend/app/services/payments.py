from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal, ROUND_HALF_UP

import httpx

from app.core.config import settings


class PaymentProviderUnavailable(RuntimeError):
    pass


class PaymentProviderError(RuntimeError):
    pass


def razorpay_enabled() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def razorpay_webhook_enabled() -> bool:
    return bool(settings.RAZORPAY_WEBHOOK_SECRET)


def amount_to_subunits(amount: Decimal) -> int:
    normalized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(normalized * 100)


def create_razorpay_order(*, amount: Decimal, receipt: str, gaonone_order_id: str) -> dict:
    if not razorpay_enabled():
        raise PaymentProviderUnavailable("Razorpay credentials are not configured")

    payload = {
        "amount": amount_to_subunits(amount),
        "currency": "INR",
        "receipt": receipt[:40],
        "notes": {"gaonone_order_id": gaonone_order_id},
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                "https://api.razorpay.com/v1/orders",
                auth=(settings.RAZORPAY_KEY_ID or "", settings.RAZORPAY_KEY_SECRET or ""),
                json=payload,
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PaymentProviderError(
            f"Razorpay rejected the order request ({exc.response.status_code})"
        ) from exc
    except httpx.HTTPError as exc:
        raise PaymentProviderError("Unable to reach Razorpay") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise PaymentProviderError("Razorpay returned an invalid order response") from exc
    if not isinstance(data, dict) or not data.get("id"):
        raise PaymentProviderError("Razorpay returned an invalid order response")
    return data


def verify_razorpay_signature(
    *, provider_order_id: str, provider_payment_id: str, received_signature: str
) -> bool:
    if not settings.RAZORPAY_KEY_SECRET:
        raise PaymentProviderUnavailable("Razorpay secret is not configured")
    signed_body = f"{provider_order_id}|{provider_payment_id}".encode("utf-8")
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"), signed_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received_signature)


def verify_razorpay_webhook_signature(*, raw_body: bytes, received_signature: str) -> bool:
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise PaymentProviderUnavailable("Razorpay webhook secret is not configured")
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received_signature)
