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
                .where(PaymentAttempt.order_id == order.id, PaymentAttempt.provider == "razorpay")
            ).all()
            if not attempts:
                findings.append({"order_number": order.order_number, "result": "missing_payment_attempt"})
                continue
            captured = False
            unavailable = False
            mismatch = False
            for attempt in attempts:
                if not attempt.provider_order_id:
                    mismatch = True
                    continue
                try:
                    payments = list_razorpay_order_payments(
                        provider_order_id=attempt.provider_order_id,
                    )
                except (PaymentProviderUnavailable, PaymentProviderError):
                    unavailable = True
                    continue
                for payment in payments:
                    if payment.get("status") != "captured":
                        continue
                    if (
                        payment.get("order_id") == attempt.provider_order_id
                        and payment.get("currency") == "INR"
                        and payment.get("amount") == amount_to_subunits(order.total)
                        and payment.get("id") == attempt.provider_payment_id
                    ):
                        captured = True
                    else:
                        mismatch = True
            if captured:
                result = "verified_capture"
            elif unavailable:
                result = "provider_unavailable"
            elif mismatch:
                result = "capture_mismatch"
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(audit_paid_upi(limit=args.limit, days=args.days), indent=2))


if __name__ == "__main__":
    main()
