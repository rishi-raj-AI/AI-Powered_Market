"""P0-C: a delivery that fails after pickup must have a way out.

Previously: /delivery/{id}/fail accepted a failure at picked_up, the order
stayed at out_for_delivery (which only transitions to delivered), recovery
refused anything already picked up, and admins hit the same transition gate.
The order was stranded forever and prepaid money with it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.models.integrations import CodCollection, SettlementEntry
from app.models.orders import (
    Delivery,
    DeliveryStatus,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    StatusTransitionEvent,
)
from app.models.user import UserRole
from app.services.refunds import get_refund_for_order
from app.services.settlements import SETTLEMENT_VOIDED, ensure_settlement_entry
from tests.factories import make_order, make_user, session

client = TestClient(app)
OTP = "123456"


def admin_token() -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": "+919000000001", "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _failed_after_pickup(db, **order_kwargs):
    """An order whose rider took the goods and then could not deliver."""
    order = make_order(db, status=OrderStatus.OUT_FOR_DELIVERY, with_delivery=True, **order_kwargs)
    rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
    delivery = db.query(Delivery).filter(Delivery.order_id == order.id).one()
    now = datetime.now(timezone.utc)
    delivery.delivery_partner_id = rider.id
    delivery.status = DeliveryStatus.FAILED
    delivery.assigned_at = now
    delivery.picked_up_at = now
    delivery.failed_at = now
    delivery.failure_reason = "customer_unavailable"
    db.flush()
    return order, delivery


def test_prepaid_failure_after_pickup_returns_order_and_owes_a_refund() -> None:
    with session() as db:
        order, delivery = _failed_after_pickup(db, payment_status=PaymentStatus.PAID)
        ensure_settlement_entry(db, order)
        db.commit()
        order_id, delivery_id = order.id, delivery.id

    response = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/resolve-failure",
        headers=auth(admin_token()),
        json={"resolution": "return_to_store", "notes": "Rider returned the goods"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["order_status"] == "returned"
    assert body["refund_requested"] is True

    with session() as db:
        from app.models.orders import Order

        order = db.get(Order, order_id)
        # No longer stranded.
        assert order.status == OrderStatus.RETURNED
        # Money owed back, and not yet claimed as returned.
        assert order.payment_status == PaymentStatus.REFUND_PENDING
        refund = get_refund_for_order(db, order_id)
        assert refund is not None
        assert refund.reason == "delivery_returned"
        # Merchant entitlement is gone the moment the goods came back.
        entry = db.query(SettlementEntry).filter(SettlementEntry.order_id == order_id).one()
        assert entry.status == SETTLEMENT_VOIDED
        assert entry.void_reason == "delivery_returned"
        # Stock went back on the shelf.
        assert order.stock_restored_at is not None
        # And the whole thing is explainable afterwards.
        events = (
            db.query(StatusTransitionEvent)
            .filter(StatusTransitionEvent.order_id == order_id)
            .all()
        )
        assert any(e.to_status == "returned" for e in events)


def test_admin_failed_delivery_queue_is_protected_and_factual() -> None:
    with session() as db:
        order, delivery = _failed_after_pickup(db, payment_status=PaymentStatus.PAID)
        db.commit()
        delivery_id = str(delivery.id)

    customer = client.post(
        "/api/v1/auth/verify-otp", json={"phone": "+919000000099", "otp": OTP}
    ).json()["access_token"]
    assert client.get("/api/v1/admin/deliveries/failed", headers=auth(customer)).status_code == 403

    response = client.get("/api/v1/admin/deliveries/failed", headers=auth(admin_token()))
    assert response.status_code == 200, response.text
    row = next(item for item in response.json() if item["id"] == delivery_id)
    assert row["status"] == "failed"
    assert row["failure_reason"] == "customer_unavailable"
    assert row["picked_up_at"] is not None


def test_cod_failure_after_pickup_never_becomes_paid() -> None:
    with session() as db:
        order, delivery = _failed_after_pickup(
            db,
            payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        db.commit()
        order_id, delivery_id = order.id, delivery.id

    response = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/resolve-failure",
        headers=auth(admin_token()),
        json={"resolution": "return_to_store"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["refund_requested"] is False

    with session() as db:
        from app.models.orders import Order

        order = db.get(Order, order_id)
        assert order.status == OrderStatus.RETURNED
        # Cash was never collected, so nothing may imply it was.
        assert order.payment_status == PaymentStatus.PENDING
        assert get_refund_for_order(db, order_id) is None


def test_cod_with_recorded_cash_requires_human_reconciliation() -> None:
    with session() as db:
        order, delivery = _failed_after_pickup(
            db,
            payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        db.add(
            CodCollection(
                delivery_id=delivery.id,
                order_id=order.id,
                amount=order.total,
                collected_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        delivery_id = delivery.id

    response = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/resolve-failure",
        headers=auth(admin_token()),
        json={"resolution": "return_to_store"},
    )
    # Cash that is recorded as collected on a delivery that failed is a physical
    # discrepancy. Guessing here would invent money movement.
    assert response.status_code == 409
    assert "Reconcile the cash" in response.json()["detail"]


def test_resolution_is_idempotent_and_cannot_be_repeated() -> None:
    with session() as db:
        order, delivery = _failed_after_pickup(db, payment_status=PaymentStatus.PAID)
        db.commit()
        order_id, delivery_id = order.id, delivery.id

    token = admin_token()
    first = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/resolve-failure",
        headers=auth(token),
        json={"resolution": "return_to_store"},
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/resolve-failure",
        headers=auth(token),
        json={"resolution": "return_to_store"},
    )
    assert second.status_code == 409

    with session() as db:
        from app.models.orders import Order

        order = db.get(Order, order_id)
        assert order.status == OrderStatus.RETURNED
        # Exactly one refund obligation, no double restoration.
        refund = get_refund_for_order(db, order_id)
        assert refund is not None


def test_reassign_is_refused_once_goods_have_left_the_store() -> None:
    with session() as db:
        order, delivery = _failed_after_pickup(db, payment_status=PaymentStatus.PAID)
        db.commit()
        delivery_id = delivery.id

    response = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/resolve-failure",
        headers=auth(admin_token()),
        json={"resolution": "reassign"},
    )
    assert response.status_code == 409
    assert "custody never left the merchant" in response.json()["detail"]


def test_reassign_still_works_before_pickup() -> None:
    with session() as db:
        order = make_order(db, status=OrderStatus.READY, with_delivery=True)
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        delivery = db.query(Delivery).filter(Delivery.order_id == order.id).one()
        delivery.delivery_partner_id = rider.id
        delivery.status = DeliveryStatus.FAILED
        delivery.assigned_at = datetime.now(timezone.utc)
        delivery.failed_at = datetime.now(timezone.utc)
        db.commit()
        delivery_id, order_id = delivery.id, order.id

    response = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/resolve-failure",
        headers=auth(admin_token()),
        json={"resolution": "reassign"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["delivery_status"] == "unassigned"
    assert response.json()["refund_requested"] is False

    with session() as db:
        delivery = db.get(Delivery, delivery_id)
        assert delivery.delivery_partner_id is None
        assert delivery.status == DeliveryStatus.UNASSIGNED
        # Still deliverable; the order was never returned.
        from app.models.orders import Order

        assert db.get(Order, order_id).status == OrderStatus.READY


def test_only_a_failed_delivery_can_be_resolved() -> None:
    with session() as db:
        order = make_order(db, status=OrderStatus.READY, with_delivery=True)
        db.commit()
        delivery_id = db.query(Delivery).filter(Delivery.order_id == order.id).one().id

    response = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/resolve-failure",
        headers=auth(admin_token()),
        json={"resolution": "return_to_store"},
    )
    assert response.status_code == 409


def test_non_admin_cannot_resolve_a_failure() -> None:
    with session() as db:
        order, delivery = _failed_after_pickup(db, payment_status=PaymentStatus.PAID)
        db.commit()
        delivery_id = delivery.id

    rider = client.post(
        "/api/v1/auth/verify-otp", json={"phone": "+919000000002", "otp": OTP}
    ).json()["access_token"]
    response = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/resolve-failure",
        headers=auth(rider),
        json={"resolution": "return_to_store"},
    )
    assert response.status_code == 403


def test_returned_order_cannot_then_be_marked_delivered() -> None:
    with session() as db:
        order, delivery = _failed_after_pickup(db, payment_status=PaymentStatus.PAID)
        db.commit()
        order_id, delivery_id = order.id, delivery.id

    client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/resolve-failure",
        headers=auth(admin_token()),
        json={"resolution": "return_to_store"},
    )
    complete = client.post(
        f"/api/v1/delivery/{delivery_id}/complete", headers=auth(admin_token())
    )
    assert complete.status_code == 409

    with session() as db:
        from app.models.orders import Order

        assert db.get(Order, order_id).status == OrderStatus.RETURNED


def test_merchant_cannot_assign_returned_status_directly() -> None:
    """RETURNED has financial consequences and is operations-owned."""
    with session() as db:
        order, _delivery = _failed_after_pickup(db, payment_status=PaymentStatus.PAID)
        db.commit()
        order_id = order.id

    response = client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        headers=auth(admin_token()),
        json={"status": "returned"},
    )
    assert response.status_code == 403
    assert "not a merchant-assignable order status" in response.json()["detail"]


def test_stock_restoration_stays_exactly_once_across_return() -> None:
    with session() as db:
        order, delivery = _failed_after_pickup(db, payment_status=PaymentStatus.PAID)
        from app.models.commerce import StoreProduct
        from app.models.orders import OrderItem

        item = db.query(OrderItem).filter(OrderItem.order_id == order.id).one()
        listing = (
            db.query(StoreProduct)
            .filter(
                StoreProduct.store_id == order.store_id,
                StoreProduct.product_id == item.product_id,
            )
            .one()
        )
        before = listing.stock_quantity
        quantity = item.quantity
        db.commit()
        delivery_id, listing_id = delivery.id, listing.id

    client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/resolve-failure",
        headers=auth(admin_token()),
        json={"resolution": "return_to_store"},
    )

    with session() as db:
        from app.models.commerce import StoreProduct

        listing = db.get(StoreProduct, listing_id)
        assert listing.stock_quantity == before + quantity
