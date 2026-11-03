"""Read-only audit of GaonOne orders marked paid against Razorpay captures.

No database writes, no refunds, no payment creation. Intended for controlled
operator execution in staging before any production reconciliation.
Usage:
    python -m app.scripts.audit_upi_payments --limit 100 --days 30
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.integrations import PaymentAttempt
from app.models.orders import Order, PaymentMethod, PaymentStatus
from app.services.payments import (
    PaymentProviderError,
    PaymentProviderUnavailable,
    amount_to_subunits,
    list_razorpay_order_payments,
)


def audit_paid_upi(*, limit: int = 100, days: int = 30) -> dict:
    if not 1 <= limit <= 1000 or not 1 <= days <= 365:
        raise ValueError("limit must be 1–1000 and days must be 1–365")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    findings = []
    with SessionLocal() as db:
        orders = db.scalars(
            select(Order)
            .where(
                Order.payment_method == PaymentMethod.UPI,
                Order.payment_status == PaymentStatus.PAID,
                Order.created_at >= cutoff,
            )
            .order_by(Order.created_at.desc())
            .limit(limit)
        ).all()
        for order in orders:
            attempts = db.scalars(
                select(PaymentAttempt)
                .where(PaymentAttempt.order_id == order.id)
            ).all()
            if not attempts:
                findings.append({"order_number": order.order_number, "result": "missing_payment_attempt"})
                continue
            matched_capture_ids: set[str] = set()
            captured_ids: set[str] = set()
            unavailable = False
            mismatch = False
            ambiguous = False
            # Duplicate local provider identities are not two independent
            # receipts. They may represent a broken retry/import and can
            # conceal another charge even when one provider capture matches.
            seen_order_ids: set[str] = set()
            seen_payment_ids: set[str] = set()
            seen_provider_history_ids: set[str] = set()
            for attempt in attempts:
                # Audit all attempts, not just Razorpay rows. A different
                # provider could have collected money for the same order.
                if attempt.provider != "razorpay":
                    mismatch = True
                    continue
                if isinstance(attempt.provider_order_id, str) and attempt.provider_order_id.strip():
                    if attempt.provider_order_id in seen_order_ids:
                        mismatch = True
                    seen_order_ids.add(attempt.provider_order_id)
                if attempt.provider_payment_id is not None:
                    if not isinstance(attempt.provider_payment_id, str) or not attempt.provider_payment_id.strip():
                        mismatch = True
                        continue
                    if attempt.provider_payment_id in seen_payment_ids:
                        mismatch = True
                    seen_payment_ids.add(attempt.provider_payment_id)
                # A matching provider capture cannot validate an inconsistent
                # local ledger. An attempt for a different amount, currency or
                # non-paid status still requires explicit reconciliation.
                if (
                    attempt.amount != order.total
                    or attempt.currency != "INR"
                    or attempt.status not in {"created", "attempted", "failed", "paid"}
                    or (attempt.provider_payment_id and attempt.status != "paid")
                    or (attempt.status == "paid" and not attempt.provider_payment_id)
                ):
                    # A second locally paid attempt with no provider payment
                    # identifier cannot be cleared by another valid capture.
                    mismatch = True
                if not isinstance(attempt.provider_order_id, str) or not attempt.provider_order_id.strip():
                    mismatch = True
                    continue
                try:
                    payments = list_razorpay_order_payments(
                        provider_order_id=attempt.provider_order_id,
                    )
                except (PaymentProviderUnavailable, PaymentProviderError):
                    unavailable = True
                    continue
                # Defensive audit validation: a duplicated provider payment
                # identity is not independent capture evidence. The provider
                # helper also validates this, but audit fixtures and historical
                # adapters must not be able to bypass the invariant.
                seen_history_ids: set[str] = set()
                for payment in payments:
                    if not isinstance(payment, dict):
                        mismatch = True
                        continue
                    history_id = payment.get("id")
                    if (
                        not isinstance(history_id, str)
                        or not history_id.strip()
                        or history_id in seen_history_ids
                    ):
                        mismatch = True
                    else:
                        seen_history_ids.add(history_id)
                        # A provider payment ID must not appear under two
                        # distinct Razorpay orders, even as a failed row.
                        # Otherwise a valid capture in one history can hide
                        # contradictory evidence in another history.
                        if history_id in seen_provider_history_ids:
                            mismatch = True
                        seen_provider_history_ids.add(history_id)
                    provider_status = payment.get("status")
                    if provider_status == "failed":
                        # Only a well-formed failed payment for this exact
                        # provider order can be safely ignored. A malformed
                        # history row must not certify a separate capture.
                        if (
                            not isinstance(payment.get("id"), str)
                            or not payment["id"].strip()
                            or payment.get("order_id") != attempt.provider_order_id
                            or payment.get("currency") != attempt.currency
                            or type(payment.get("amount")) is not int
                            or payment["amount"] != amount_to_subunits(attempt.amount)
                        ):
                            mismatch = True
                        continue
                    if provider_status != "captured":
                        # An authorized/created or unrecognised provider
                        # payment could still move money after this audit.
                        ambiguous = True
                        continue
                    payment_id = payment.get("id")
                    if isinstance(payment_id, str):
                        captured_ids.add(payment_id)
                    if (
                        isinstance(payment_id, str)
                        and bool(payment_id.strip())
                        and payment.get("order_id") == attempt.provider_order_id
                        and payment.get("currency") == "INR"
                        and type(payment.get("amount")) is int
                        and payment["amount"] == amount_to_subunits(order.total)
                        and payment_id == attempt.provider_payment_id
                    ):
                        matched_capture_ids.add(payment_id)
                    else:
                        mismatch = True
            # Never hide an extra captured payment or an unavailable attempt
            # just because another attempt matches the order. This is an
            # audit, not a payment-state mutation; uncertainty must be visible.
            if len(captured_ids) > 1:
                result = "multiple_captures"
            elif unavailable:
                result = "provider_unavailable"
            elif mismatch:
                result = "capture_mismatch"
            elif ambiguous:
                result = "provider_ambiguous"
            elif matched_capture_ids:
                result = "verified_capture"
            else:
                result = "no_matching_capture"
            findings.append({"order_number": order.order_number, "result": result})
        db.rollback()  # explicitly read-only
    return {
        "scanned": len(findings),
        "verified": sum(f["result"] == "verified_capture" for f in findings),
        "requires_review": sum(f["result"] != "verified_capture" for f in findings),
        "findings": findings,
    }


def audit_unpaid_upi(*, limit: int = 100, days: int = 30) -> dict:
    """Read-only triage for UPI orders still marked pending or failed.

    Never infer that an order is safely unpaid from its local flag alone.
    This report does not change payment, stock, settlement, or refund records.
    """
    if not 1 <= limit <= 1000 or not 1 <= days <= 365:
        raise ValueError("limit must be 1–1000 and days must be 1–365")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    findings = []
    with SessionLocal() as db:
        orders = db.scalars(
            select(Order)
            .where(
                Order.payment_method == PaymentMethod.UPI,
                Order.payment_status.in_((PaymentStatus.PENDING, PaymentStatus.FAILED)),
                Order.created_at >= cutoff,
            )
            .order_by(Order.created_at.desc())
            .limit(limit)
        ).all()
        for order in orders:
            attempts = db.scalars(
                select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
            ).all()
            captures: set[tuple[str, str]] = set()
            unavailable = False
            inconsistent = False
            unsettled = False
            local_capture = False
            seen_local_order_ids: set[str] = set()
            seen_local_payment_ids: set[str] = set()
            seen_provider_payment_ids: set[str] = set()
            for attempt in attempts:
                if attempt.status == "paid" or attempt.provider_payment_id is not None:
                    local_capture = True
                    if attempt.provider_payment_id is not None and (
                        not isinstance(attempt.provider_payment_id, str)
                        or not attempt.provider_payment_id.strip()
                    ):
                        inconsistent = True
                elif attempt.status not in {"created", "attempted", "failed"}:
                    unsettled = True
                # A payment identity cannot belong to two local attempts,
                # even when both histories otherwise appear to have failed.
                local_payment_id = attempt.provider_payment_id
                if isinstance(local_payment_id, str) and local_payment_id.strip():
                    if local_payment_id in seen_local_payment_ids:
                        inconsistent = True
                    seen_local_payment_ids.add(local_payment_id)
                if (
                    attempt.provider != "razorpay"
                    or attempt.currency != "INR"
                    or attempt.amount != order.total
                    or not isinstance(attempt.provider_order_id, str)
                    or not attempt.provider_order_id.strip()
                ):
                    inconsistent = True
                    continue
                # Two local attempts must never claim the same provider order.
                # Even if that order has only failed payments, the duplicated
                # identity makes a reassuring no-capture result unsafe.
                if attempt.provider_order_id in seen_local_order_ids:
                    inconsistent = True
                    continue
                seen_local_order_ids.add(attempt.provider_order_id)
                try:
                    history = list_razorpay_order_payments(
                        provider_order_id=attempt.provider_order_id
                    )
                except (PaymentProviderUnavailable, PaymentProviderError):
                    unavailable = True
                    continue
                # The provider helper already rejects incomplete histories.
                # Keep the audit conservative when reading historical/mock
                # evidence too: malformed or duplicate failed rows must not
                # produce the reassuring "no_capture_found" classification.
                seen_payment_ids: set[str] = set()
                for payment in history:
                    if not isinstance(payment, dict):
                        inconsistent = True
                        continue
                    payment_id = payment.get("id")
                    if (
                        not isinstance(payment_id, str)
                        or not payment_id.strip()
                        or payment_id in seen_payment_ids
                    ):
                        inconsistent = True
                    else:
                        seen_payment_ids.add(payment_id)
                        # Check across provider orders as well as within each
                        # page. A reused payment ID invalidates the audit.
                        if payment_id in seen_provider_payment_ids:
                            inconsistent = True
                        seen_provider_payment_ids.add(payment_id)
                    if (
                        type(payment.get("amount")) is not int
                        or payment["amount"] != amount_to_subunits(order.total)
                        or payment.get("currency") != "INR"
                        or payment.get("order_id") != attempt.provider_order_id
                    ):
                        inconsistent = True
                    if payment.get("status") == "captured":
                        if isinstance(payment_id, str) and payment_id.strip():
                            captures.add((attempt.provider_order_id, payment_id))
                        else:
                            inconsistent = True
                    elif payment.get("status") != "failed":
                        unsettled = True

            if len(captures) > 1:
                result = "multiple_captures"
            elif captures:
                # Even a mismatched capture is a possible money movement:
                # do not certify the order unpaid or automatically expire it.
                result = "unexpected_capture"
            elif local_capture:
                result = "local_capture_evidence"
            elif unavailable:
                result = "provider_unavailable"
            elif inconsistent:
                result = "payment_history_mismatch"
            elif unsettled:
                result = "provider_ambiguous"
            elif not attempts:
                result = "missing_payment_attempt"
            else:
                result = "no_capture_found"
            findings.append({
                "order_number": order.order_number,
                "result": result,
                "provider_capture_count": len(captures),
            })
        db.rollback()  # read-only: no stock or payment changes
    return {
        "scanned": len(findings),
        "no_capture_found": sum(f["result"] == "no_capture_found" for f in findings),
        "requires_review": sum(f["result"] != "no_capture_found" for f in findings),
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--unpaid", action="store_true", help="Audit pending/failed UPI orders instead of paid orders")
    args = parser.parse_args()
    audit = audit_unpaid_upi if args.unpaid else audit_paid_upi
    print(json.dumps(audit(limit=args.limit, days=args.days), indent=2))


if __name__ == "__main__":
    main()
