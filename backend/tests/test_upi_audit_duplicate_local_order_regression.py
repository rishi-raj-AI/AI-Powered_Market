"""Payment attempt provider identities are unique at the database boundary.

Disposable database fixtures only; no provider calls or live financial records.
"""
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.integrations import PaymentAttempt
from tests.factories import make_order, session


@pytest.mark.parametrize("collision", ["provider_order_id", "provider_payment_id"])
def test_payment_attempt_rejects_duplicate_provider_identity(collision):
    with session() as db:
        order = make_order(db)
        original = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        duplicate = PaymentAttempt(
            order_id=order.id,
            provider="razorpay",
            provider_order_id=(
                original.provider_order_id if collision == "provider_order_id"
                else f"order_{uuid4().hex}"
            ),
            provider_payment_id=(
                original.provider_payment_id if collision == "provider_payment_id"
                else None
            ),
            amount=original.amount,
            currency=original.currency,
            status="created",
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
