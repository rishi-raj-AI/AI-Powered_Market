"""Opt-in UPI reservation expiration must never assume provider failure."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.commerce import StoreProduct
from app.models.integrations import PaymentAttempt
from app.models.orders import Order, OrderItem, OrderStatus, PaymentStatus
from app.services import payment_expiration
from app.services.payments import PaymentProviderUnavailable
from tests.factories import make_order, session


def _old_unpaid_order(db):
    order = make_order(db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False)
    order.created_at = datetime.now(timezone.utc) - timedelta(minutes=40)
    attempt = PaymentAttempt(
        order_id=order.id, provider="razorpay",
        provider_order_id=f"order_{uuid4().hex}", status="attempted",
        amount=Decimal("120.00"), currency="INR",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=40),
    )
    db.add(attempt)
    item = db.query(OrderItem).filter(OrderItem.order_id == order.id).one()
    listing = db.query(StoreProduct).filter(
        StoreProduct.store_id == order.store_id,
        StoreProduct.product_id == item.product_id,
    ).one()
    listing.stock_quantity -= item.quantity  # model the checkout reservation
    db.commit()
    return order.id, attempt.provider_order_id, listing.id


def test_expired_unpaid_upi_order_restores_stock_exactly_once(monkeypatch):
    with session() as db:
        order_id, _provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(payment_expiration, "list_razorpay_order_payments", lambda **_: [])
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["expired"] >= 1
        order = db.get(Order, order_id)
        listing = db.get(StoreProduct, listing_id)
        assert order.status == OrderStatus.CANCELLED
        assert order.stock_restored_at is not None
        assert listing.stock_quantity == 10
        again = payment_expiration.expire_unpaid_orders(db, limit=10)
        db.refresh(listing)
        assert again["expired"] == 0
        assert listing.stock_quantity == 10


def test_expiry_reconciles_captured_payment_instead_of_cancelling(monkeypatch):
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": f"pay_{uuid4().hex}", "order_id": provider_order_id,
                "amount": 12000, "currency": "INR", "status": "captured",
            }],
        )
        monkeypatch.setattr(payment_expiration, "_notify_payment_captured", lambda *_: None)
        monkeypatch.setattr(payment_expiration, "_apply_paid", lambda _db, attempt, order, payment_id: (
            setattr(attempt, "status", "paid"),
            setattr(attempt, "provider_payment_id", payment_id),
            setattr(order, "payment_status", PaymentStatus.PAID),
        ))
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["captured"] >= 1
        order = db.get(Order, order_id)
        listing = db.get(StoreProduct, listing_id)
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PAID
        assert listing.stock_quantity == 9


def test_provider_outage_defers_expiration_and_preserves_stock(monkeypatch):
    with session() as db:
        order_id, _provider_order_id, listing_id = _old_unpaid_order(db)

        def unavailable(**_kwargs):
            raise PaymentProviderUnavailable("test provider outage")

        monkeypatch.setattr(payment_expiration, "list_razorpay_order_payments", unavailable)
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        order = db.get(Order, order_id)
        listing = db.get(StoreProduct, listing_id)
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert listing.stock_quantity == 9


def test_authorized_payment_is_not_expired(monkeypatch):
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": f"pay_{uuid4().hex}", "order_id": provider_order_id,
                "amount": 12000, "currency": "INR", "status": "authorized",
            }],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        assert db.get(Order, order_id).status == OrderStatus.PLACED
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


def test_expiry_defers_capture_when_another_payment_is_authorized(monkeypatch):
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [
                {"id": f"pay_{uuid4().hex}", "order_id": provider_order_id,
                 "amount": 12000, "currency": "INR", "status": "captured"},
                {"id": f"pay_{uuid4().hex}", "order_id": provider_order_id,
                 "amount": 12000, "currency": "INR", "status": "authorized"},
            ],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        order = db.get(Order, order_id)
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


def test_expiry_never_releases_underpaid_capture_as_paid(monkeypatch):
    """Provider capture for an incorrectly priced attempt needs reconciliation."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        attempt = db.query(PaymentAttempt).filter(
            PaymentAttempt.order_id == order_id,
        ).one()
        attempt.amount = Decimal("119.00")
        db.commit()
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": f"pay_{uuid4().hex}", "order_id": provider_order_id,
                "amount": 11900, "currency": "INR", "status": "captured",
            }],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        order = db.get(Order, order_id)
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


@pytest.mark.parametrize("provider_status", ["created", "authorized", "refunded", "processing", None])
def test_expiry_defers_nonterminal_or_unknown_provider_payment(monkeypatch, provider_status):
    """Only a well-formed terminal failure is evidence of nonpayment."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": f"pay_{uuid4().hex}", "order_id": provider_order_id,
                "amount": 12000, "currency": "INR", "status": provider_status,
            }],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        order = db.get(Order, order_id)
        assert order.status == OrderStatus.PLACED
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


@pytest.mark.parametrize("provider_status", ["failed", None])
def test_expiry_requires_well_formed_failed_provider_payment(monkeypatch, provider_status):
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": f"pay_{uuid4().hex}",
                "order_id": provider_order_id if provider_status == "failed" else "wrong_order",
                "amount": 12000, "currency": "INR", "status": "failed",
            }],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        order = db.get(Order, order_id)
        if provider_status == "failed":
            assert result["expired"] >= 1
            assert order.status == OrderStatus.CANCELLED
            assert db.get(StoreProduct, listing_id).stock_quantity == 10
        else:
            assert result["deferred"] >= 1
            assert order.status == OrderStatus.PLACED
            assert db.get(StoreProduct, listing_id).stock_quantity == 9


@pytest.mark.parametrize("local_status,local_payment_id", [
    ("paid", None),
    ("attempted", "pay_locally_recorded"),
])
def test_expiry_defers_local_capture_evidence_even_with_empty_provider_history(
    monkeypatch, local_status, local_payment_id,
):
    with session() as db:
        order_id, _provider_order_id, listing_id = _old_unpaid_order(db)
        attempt = db.query(PaymentAttempt).filter(PaymentAttempt.order_id == order_id).one()
        attempt.status = local_status
        attempt.provider_payment_id = local_payment_id
        db.commit()
        monkeypatch.setattr(payment_expiration, "list_razorpay_order_payments", lambda **_: [])
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        assert db.get(Order, order_id).status == OrderStatus.PLACED
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


def test_expiry_defers_unknown_payment_provider_attempt(monkeypatch):
    with session() as db:
        order_id, _provider_order_id, listing_id = _old_unpaid_order(db)
        db.add(PaymentAttempt(
            order_id=order_id, provider="unknown_provider",
            status="attempted", amount=Decimal("120.00"), currency="INR",
        ))
        db.commit()
        monkeypatch.setattr(payment_expiration, "list_razorpay_order_payments", lambda **_: [])
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        assert db.get(Order, order_id).status == OrderStatus.PLACED
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


@pytest.mark.parametrize("invalid_failed_fields", [
    {"amount": 11999},
    {"amount": None},
    {"currency": "USD"},
    {"currency": None},
    {"id": ""},
])
def test_expiry_defers_malformed_failed_money_fields(monkeypatch, invalid_failed_fields):
    """A malformed terminal failure cannot authorize stock restoration."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        failed = {
            "id": f"pay_failed_{uuid4().hex}", "order_id": provider_order_id,
            "amount": 12000, "currency": "INR", "status": "failed",
        }
        failed.update(invalid_failed_fields)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [failed],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        order = db.get(Order, order_id)
        assert order.status == OrderStatus.PLACED
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


@pytest.mark.parametrize("invalid_attempt_fields", [
    {"amount": Decimal("119.00")},
    {"currency": "USD"},
])
def test_expiry_defers_mispriced_local_attempt_even_with_empty_history(
    monkeypatch, invalid_attempt_fields,
):
    with session() as db:
        order_id, _provider_order_id, listing_id = _old_unpaid_order(db)
        attempt = db.query(PaymentAttempt).filter(
            PaymentAttempt.order_id == order_id,
        ).one()
        for key, value in invalid_attempt_fields.items():
            setattr(attempt, key, value)
        db.commit()
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments", lambda **_: [],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        order = db.get(Order, order_id)
        assert order.status == OrderStatus.PLACED
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


@pytest.mark.parametrize("local_status", ["authorized", "processing", "refunded", "unknown"])
def test_expiry_defers_unknown_local_attempt_even_with_empty_provider_history(
    monkeypatch, local_status,
):
    """An empty provider page does not invalidate conflicting local evidence."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        attempt = db.query(PaymentAttempt).filter(
            PaymentAttempt.provider_order_id == provider_order_id,
        ).one()
        attempt.status = local_status
        db.commit()
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments", lambda **_: [],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        order = db.get(Order, order_id)
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


@pytest.mark.parametrize("malformed_amount", [12000.0, "12000", None, True])
def test_expiry_does_not_confirm_malformed_captured_amount(
    monkeypatch, malformed_amount,
):
    """Provider captures require integer paise before stock/fulfilment changes."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": f"pay_{uuid4().hex}",
                "order_id": provider_order_id,
                "amount": malformed_amount,
                "currency": "INR",
                "status": "captured",
            }],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        order = db.get(Order, order_id)
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


@pytest.mark.parametrize("statuses", [
    ("captured", "captured"),
    ("captured", "failed"),
    ("failed", "failed"),
])
def test_expiry_defers_duplicate_provider_payment_identity(monkeypatch, statuses):
    """Duplicated provider IDs cannot prove capture or terminal nonpayment."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        duplicate_id = f"pay_{uuid4().hex}"
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [
                {
                    "id": duplicate_id, "order_id": provider_order_id,
                    "amount": 12000, "currency": "INR", "status": status,
                }
                for status in statuses
            ],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        order = db.get(Order, order_id)
        assert result["deferred"] >= 1
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


def test_expiry_compares_provider_history_to_canonical_order_total(monkeypatch):
    """A corrupted local attempt must not define provider money validation."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        attempt = db.query(PaymentAttempt).filter(PaymentAttempt.order_id == order_id).one()
        attempt.amount = Decimal("119.00")
        db.commit()
        observed = []
        real_convert = payment_expiration.amount_to_subunits

        def record_amount(amount):
            observed.append(amount)
            return real_convert(amount)

        monkeypatch.setattr(payment_expiration, "amount_to_subunits", record_amount)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": f"pay_{uuid4().hex}", "order_id": provider_order_id,
                "amount": 12000, "currency": "INR", "status": "failed",
            }],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert observed == [Decimal("120.00")]
        assert result["deferred"] >= 1
        assert db.get(Order, order_id).status == OrderStatus.PLACED
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


def test_expiry_defers_when_capture_application_does_not_mark_order_paid(monkeypatch):
    """Do not report successful reconciliation if capture left payment pending."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": f"pay_{uuid4().hex}", "order_id": provider_order_id,
                "amount": 12000, "currency": "INR", "status": "captured",
            }],
        )
        monkeypatch.setattr(payment_expiration, "_apply_paid", lambda *_: None)
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["captured"] == 0
        assert result["deferred"] >= 1
        assert db.get(Order, order_id).payment_status == PaymentStatus.PENDING
        assert db.get(Order, order_id).status == OrderStatus.PLACED
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


@pytest.mark.parametrize("attempt_status,payment_id_mode", [
    ("attempted", "correct"),
    ("paid", "missing"),
    ("paid", "wrong"),
])
def test_expiry_defers_incomplete_capture_attempt_evidence(
    monkeypatch, attempt_status, payment_id_mode,
):
    """Order-level PAID alone cannot certify a captured provider attempt."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        captured_id = f"pay_{uuid4().hex}"
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": captured_id, "order_id": provider_order_id,
                "amount": 12000, "currency": "INR", "status": "captured",
            }],
        )

        def incomplete_capture(_db, attempt, order, _payment_id):
            order.payment_status = PaymentStatus.PAID
            attempt.status = attempt_status
            attempt.provider_payment_id = (
                captured_id if payment_id_mode == "correct"
                else None if payment_id_mode == "missing"
                else f"pay_wrong_{uuid4().hex}"
            )

        monkeypatch.setattr(payment_expiration, "_apply_paid", incomplete_capture)
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["captured"] == 0
        assert result["deferred"] >= 1
        order = db.get(Order, order_id)
        assert order.payment_status == PaymentStatus.PENDING
        assert order.status == OrderStatus.PLACED
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


@pytest.mark.parametrize("provider_order_id,local_status", [
    (None, "created"),
    (None, "failed"),
    ("", "failed"),
    ("   ", "created"),
    (" order_legacy ", "failed"),
])
def test_expiry_quarantines_unverifiable_legacy_provider_order(
    monkeypatch, provider_order_id, local_status,
):
    """A local failure cannot prove no money moved when provider lookup is impossible."""
    with session() as db:
        order_id, _original_provider_order_id, listing_id = _old_unpaid_order(db)
        attempt = db.query(PaymentAttempt).filter(PaymentAttempt.order_id == order_id).one()
        attempt.provider_order_id = provider_order_id
        attempt.status = local_status
        db.commit()

        def unexpected_provider_read(**_kwargs):
            pytest.fail("An unidentifiable provider order must not be queried")

        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments", unexpected_provider_read,
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["expired"] == 0
        assert result["captured"] == 0
        assert result["deferred"] >= 1
        order = db.get(Order, order_id)
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9
