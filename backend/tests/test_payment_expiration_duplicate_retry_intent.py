"""Razorpay retry intents must have distinct provider-order identities.

The database uniqueness constraint is the primary safeguard; the expiration
worker also defers ambiguous legacy records that predate the constraint.
Disposable database fixtures only.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.integrations import PaymentAttempt
from tests.factories import session
from tests.test_payment_expiration import _old_unpaid_order


def test_duplicate_provider_order_id_is_rejected_by_database():
    with session() as db:
        order_id, provider_order_id, _listing_id = _old_unpaid_order(db)
        db.add(PaymentAttempt(
            order_id=order_id,
            provider="razorpay",
            provider_order_id=provider_order_id,
            status="failed",
            amount=Decimal("120.00"),
            currency="INR",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
