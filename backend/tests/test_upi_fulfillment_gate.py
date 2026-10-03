"""P0: online orders cannot release goods before payment is confirmed."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.orders import (
    Delivery,
    DeliveryProof,
    DeliveryStatus,
    Order,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)
from app.models.user import UserRole
from tests.factories import make_order, make_store, make_user, session

client = TestClient(app)
OTP = "123456"


def token_for(phone: str) -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upi_order(
    db,
    *,
    payment_status: PaymentStatus,
    order_status: OrderStatus,
    rider_assigned: bool = False,
):
    merchant = make_user(db, role=UserRole.MERCHANT, prefix="8")
    rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
    store = make_store(db, owner=merchant)
    order = make_order(
        db,
        store=store,
        payment_method=PaymentMethod.UPI,
        payment_status=payment_status,
        status=order_status,
        with_paid_attempt=payment_status == PaymentStatus.PAID,
        with_delivery=True,
    )
    delivery = db.query(Delivery).filter(Delivery.order_id == order.id).one()
    if rider_assigned:
        delivery.delivery_partner_id = rider.id
        delivery.status = DeliveryStatus.ASSIGNED
        delivery.assigned_at = datetime.now(timezone.utc)
    db.flush()
    return merchant, rider, order, delivery


@pytest.mark.parametrize("payment_status", [PaymentStatus.PENDING, PaymentStatus.FAILED])
def test_unpaid_upi_cannot_be_marked_ready(payment_status: PaymentStatus) -> None:
    with session() as db:
        merchant, _rider, order, delivery = _upi_order(
            db,
            payment_status=payment_status,
            order_status=OrderStatus.PREPARING,
        )
        db.commit()
        merchant_phone, order_id, delivery_id = merchant.phone, order.id, delivery.id

    blocked = client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        headers=auth(token_for(merchant_phone)),
        json={"status": "ready"},
    )
    assert blocked.status_code == 409, blocked.text
    assert "payment" in blocked.json()["detail"].lower()

    with session() as db:
        order = db.get(Order, order_id)
        delivery = db.get(Delivery, delivery_id)
        assert order is not None and order.status == OrderStatus.PREPARING
        assert delivery is not None and delivery.status == DeliveryStatus.UNASSIGNED
        order.payment_status = PaymentStatus.PAID
        db.commit()

    allowed = client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        headers=auth(token_for(merchant_phone)),
        json={"status": "ready"},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["status"] == OrderStatus.READY.value


@pytest.mark.parametrize("payment_status", [PaymentStatus.PENDING, PaymentStatus.FAILED])
def test_existing_unpaid_upi_order_is_not_offerable_or_claimable(
    payment_status: PaymentStatus,
) -> None:
    with session() as db:
        _merchant, rider, order, delivery = _upi_order(
            db,
            payment_status=payment_status,
            order_status=OrderStatus.READY,
        )
        db.commit()
        rider_phone, order_id, order_uuid, delivery_id = (
            rider.phone,
            str(order.id),
            order.id,
            delivery.id,
        )

    rider_token = token_for(rider_phone)
    task_offers = client.get("/api/v1/delivery/tasks/available", headers=auth(rider_token))
    assert task_offers.status_code == 200, task_offers.text
    assert order_id not in {item["order_id"] for item in task_offers.json()}

    legacy_offers = client.get("/api/v1/delivery/available", headers=auth(rider_token))
    assert legacy_offers.status_code == 200, legacy_offers.text
    assert order_id not in {item["order_id"] for item in legacy_offers.json()}

    claim = client.post(f"/api/v1/delivery/{delivery_id}/claim", headers=auth(rider_token))
    assert claim.status_code == 409, claim.text

    with session() as db:
        order = db.get(Order, order_uuid)
        delivery = db.get(Delivery, delivery_id)
        assert order is not None and order.status == OrderStatus.READY
        assert delivery is not None and delivery.status == DeliveryStatus.UNASSIGNED


@pytest.mark.parametrize("payment_status", [PaymentStatus.PENDING, PaymentStatus.FAILED])
def test_existing_unpaid_upi_is_rejected_by_manual_and_automatic_dispatch(
    payment_status: PaymentStatus,
) -> None:
    with session() as db:
        _merchant, rider, _order, delivery = _upi_order(
            db,
            payment_status=payment_status,
            order_status=OrderStatus.READY,
        )
        admin = make_user(db, role=UserRole.ADMIN, prefix="6")
        admin.is_super_admin = True
        db.commit()
        admin_phone, rider_id, delivery_id = admin.phone, rider.id, delivery.id

    admin_token = token_for(admin_phone)
    manual = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/assign",
        headers=auth(admin_token),
        json={"rider_id": str(rider_id)},
    )
    assert manual.status_code == 409, manual.text

    automatic = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/auto-assign",
        headers=auth(admin_token),
        json={},
    )
    assert automatic.status_code == 409, automatic.text

    with session() as db:
        delivery = db.get(Delivery, delivery_id)
        assert delivery is not None and delivery.status == DeliveryStatus.UNASSIGNED
        assert delivery.delivery_partner_id is None


@pytest.mark.parametrize("payment_status", [PaymentStatus.PENDING, PaymentStatus.FAILED])
def test_existing_unpaid_upi_cannot_be_picked_up_or_completed(
    payment_status: PaymentStatus,
) -> None:
    with session() as db:
        _merchant, rider, order, delivery = _upi_order(
            db,
            payment_status=payment_status,
            order_status=OrderStatus.READY,
            rider_assigned=True,
        )
        db.commit()
        rider_phone, order_id, delivery_id = rider.phone, order.id, delivery.id

    rider_token = token_for(rider_phone)
    pickup = client.patch(
        f"/api/v1/delivery/{delivery_id}/status",
        headers=auth(rider_token),
        json={"status": "picked_up"},
    )
    assert pickup.status_code == 409, pickup.text

    with session() as db:
        order = db.get(Order, order_id)
        delivery = db.get(Delivery, delivery_id)
        assert order is not None and order.status == OrderStatus.READY
        assert delivery is not None and delivery.status == DeliveryStatus.ASSIGNED
        order.status = OrderStatus.OUT_FOR_DELIVERY
        delivery.status = DeliveryStatus.PICKED_UP
        delivery.picked_up_at = datetime.now(timezone.utc)
        db.add(
            DeliveryProof(
                delivery_id=delivery.id,
                otp_hash="0" * 64,
                otp_expires_at=datetime.now(timezone.utc),
                verified_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    complete = client.post(f"/api/v1/delivery/{delivery_id}/complete", headers=auth(rider_token))
    assert complete.status_code == 409, complete.text
    assert "payment" in complete.json()["detail"].lower()

    with session() as db:
        order = db.get(Order, order_id)
        delivery = db.get(Delivery, delivery_id)
        assert order is not None and order.status == OrderStatus.OUT_FOR_DELIVERY
        assert order.payment_status == payment_status
        assert delivery is not None and delivery.status == DeliveryStatus.PICKED_UP


def test_paid_upi_can_progress_through_ready_pickup_and_completion() -> None:
    with session() as db:
        merchant, rider, order, delivery = _upi_order(
            db,
            payment_status=PaymentStatus.PAID,
            order_status=OrderStatus.PREPARING,
        )
        db.commit()
        merchant_phone, rider_phone = merchant.phone, rider.phone
        order_id, delivery_id = order.id, delivery.id

    ready = client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        headers=auth(token_for(merchant_phone)),
        json={"status": "ready"},
    )
    assert ready.status_code == 200, ready.text

    rider_token = token_for(rider_phone)
    claimed = client.post(f"/api/v1/delivery/{delivery_id}/claim", headers=auth(rider_token))
    assert claimed.status_code == 200, claimed.text
    picked_up = client.patch(
        f"/api/v1/delivery/{delivery_id}/status",
        headers=auth(rider_token),
        json={"status": "picked_up"},
    )
    assert picked_up.status_code == 200, picked_up.text

    with session() as db:
        delivery = db.get(Delivery, delivery_id)
        assert delivery is not None
        db.add(
            DeliveryProof(
                delivery_id=delivery.id,
                otp_hash="0" * 64,
                otp_expires_at=datetime.now(timezone.utc),
                verified_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    completed = client.post(f"/api/v1/delivery/{delivery_id}/complete", headers=auth(rider_token))
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == DeliveryStatus.DELIVERED.value

    with session() as db:
        order = db.get(Order, order_id)
        assert order is not None
        assert order.status == OrderStatus.DELIVERED
        assert order.payment_status == PaymentStatus.PAID
