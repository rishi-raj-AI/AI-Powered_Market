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


class PaymentProviderIndeterminate(PaymentProviderError):
    """The provider may have accepted a money-moving request despite an error.

    Never automatically re-issue a refund after a timeout, 5xx, or malformed
    response without first reconciling the original request with Razorpay.
    """


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
    # A successful HTTP response is not proof that Razorpay created the
    # intended amount/currency. Never expose a mismatched provider order to
    # Checkout: the customer could pay a different amount than the reserved
    # commercial order, leaving an ambiguous capture and stock obligation.
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("id"), str)
        or not data["id"]
        or type(data.get("amount")) is not int
        or data["amount"] != payload["amount"]
        or data.get("currency") != payload["currency"]
    ):
        raise PaymentProviderError("Razorpay returned a mismatched order response")
    return data


def create_razorpay_refund(
    *,
    provider_payment_id: str,
    amount: Decimal,
    idempotency_key: str,
    notes: dict[str, str] | None = None,
) -> dict:
    """Ask Razorpay to refund a captured payment.

    Supply a stable provider idempotency header as defence in depth. A timeout,
    5xx or malformed response is nevertheless an uncertain money movement:
    the dispatcher must reconcile it rather than automatically resubmit.
    """
    if not razorpay_enabled():
        raise PaymentProviderUnavailable("Razorpay credentials are not configured")

    payload: dict = {"amount": amount_to_subunits(amount), "speed": "normal"}
    if notes:
        payload["notes"] = notes
    # Razorpay's refund API has a refund-specific idempotency header and only
    # accepts alphanumerics, hyphens and underscores in its value. Our durable
    # application key predates that provider restriction and contains a colon,
    # so normalise only the provider-facing representation. Existing stored
    # obligations retain their stable application-level key.
    provider_idempotency_key = idempotency_key.replace(":", "-")
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"https://api.razorpay.com/v1/payments/{provider_payment_id}/refund",
                auth=(settings.RAZORPAY_KEY_ID or "", settings.RAZORPAY_KEY_SECRET or ""),
                headers={"X-Refund-Idempotency": provider_idempotency_key},
                json=payload,
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise PaymentProviderIndeterminate("Razorpay refund outcome is unknown (server error)") from exc
        raise PaymentProviderError(
            f"Razorpay rejected the refund request ({exc.response.status_code})"
        ) from exc
    except httpx.HTTPError as exc:
        raise PaymentProviderIndeterminate("Razorpay refund outcome is unknown (transport error)") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise PaymentProviderIndeterminate("Razorpay returned an unreadable refund response") from exc
    if not isinstance(data, dict) or not data.get("id"):
        raise PaymentProviderIndeterminate("Razorpay returned an incomplete refund response")
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


def fetch_razorpay_payment(*, provider_payment_id: str) -> dict:
    """Fetch authoritative provider payment state; a valid callback signature alone is insufficient."""
    if not razorpay_enabled():
        raise PaymentProviderUnavailable("Razorpay credentials are not configured")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"https://api.razorpay.com/v1/payments/{provider_payment_id}",
                auth=(settings.RAZORPAY_KEY_ID or "", settings.RAZORPAY_KEY_SECRET or ""),
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PaymentProviderError(f"Razorpay payment verification failed ({exc.response.status_code})") from exc
    except httpx.HTTPError as exc:
        raise PaymentProviderError("Unable to verify payment with Razorpay") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise PaymentProviderError("Razorpay returned an invalid payment response") from exc
    if not isinstance(data, dict) or data.get("id") != provider_payment_id:
        raise PaymentProviderError("Razorpay returned a mismatched payment response")
    return data



def list_razorpay_order_payments(*, provider_order_id: str) -> list[dict]:
    """Authoritative provider read before expiring an unpaid reservation.

    Refuse to treat a truncated provider response as proof that no capture
    exists. A provider outage must delay expiration, not silently lose money.
    """
    # Never interpolate untrusted or legacy provider identifiers into a URL.
    # A malformed identity cannot provide authoritative evidence for stock release.
    if (
        not isinstance(provider_order_id, str)
        or not provider_order_id.startswith("order_")
        or not provider_order_id[6:]
        or not all(ch.isascii() and ch.isalnum() or ch == "_" for ch in provider_order_id)
    ):
        raise PaymentProviderError("Invalid Razorpay order identity")
    if not razorpay_enabled():
        raise PaymentProviderUnavailable("Razorpay credentials are not configured")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"https://api.razorpay.com/v1/orders/{provider_order_id}/payments",
                auth=(settings.RAZORPAY_KEY_ID or "", settings.RAZORPAY_KEY_SECRET or ""),
                params={"count": 100, "skip": 0},
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PaymentProviderError(
            f"Razorpay payment lookup failed ({exc.response.status_code})"
        ) from exc
    except httpx.HTTPError as exc:
        raise PaymentProviderError("Unable to retrieve Razorpay order payments") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise PaymentProviderError("Razorpay returned invalid payment history") from exc
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise PaymentProviderError("Razorpay returned invalid payment history")
    items = data["items"]
    # The collection's count must describe the *entire* returned page. A
    # short or inconsistent response is not evidence that the remaining
    # payments failed or never existed: an omitted capture could otherwise
    # make the expiration worker cancel an order and release reserved stock.
    # Refuse a full page too, since additional payments may be paginated.
    count = data.get("count")
    if (
        type(count) is not int
        or count != len(items)
        or len(items) >= 100
        or not all(isinstance(item, dict) for item in items)
    ):
        raise PaymentProviderError("Razorpay payment history is incomplete")

    # A duplicated payment ID can conceal a missing row while preserving the
    # reported page count. Contradictory statuses for the same payment must
    # never be interpreted as one valid capture plus a harmless failed retry.
    # Require unique, attributable identities before any caller uses this
    # history to release stock, settle an order, or offer another payment.
    seen_payment_ids: set[str] = set()
    for item in items:
        payment_id = item.get("id")
        if (
            not isinstance(payment_id, str)
            or not payment_id
            or item.get("order_id") != provider_order_id
            or payment_id != payment_id.strip()
            or payment_id in seen_payment_ids
        ):
            raise PaymentProviderError("Razorpay payment history is incomplete")
        seen_payment_ids.add(payment_id)
    return items
