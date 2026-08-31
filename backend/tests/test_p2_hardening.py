"""P2 register: dangerous dead code, silent overrides, and unbounded surfaces."""

from __future__ import annotations

import io
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models.commerce import Merchant, Store
from app.models.orders import Delivery, DeliveryStatus, Order, OrderStatus, PaymentStatus
from app.models.user import User, UserRole
from tests.factories import make_order, make_store, make_user, session

client = TestClient(app)
OTP = "123456"


def token_for(phone: str) -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------- P2-1: no completion bypass ever


def test_the_legacy_status_route_cannot_complete_a_delivery() -> None:
    """Completion needs verified proof; this route has no branch for it at all."""
    with session() as db:
        order = make_order(
            db, status=OrderStatus.OUT_FOR_DELIVERY, with_delivery=True, payment_status=PaymentStatus.PENDING
        )
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        delivery = db.query(Delivery).filter(Delivery.order_id == order.id).one()
        delivery.delivery_partner_id = rider.id
        delivery.status = DeliveryStatus.PICKED_UP
        delivery.picked_up_at = datetime.now(timezone.utc)
        db.commit()
        delivery_id, order_id, rider_phone = delivery.id, order.id, rider.phone

    response = client.patch(
        f"/api/v1/delivery/{delivery_id}/status",
        headers=auth(token_for(rider_phone)),
        json={"status": "delivered"},
    )
    assert response.status_code == 422

    with session() as db:
        order = db.get(Order, order_id)
        # Critically: the order is untouched and COD did not become paid.
        assert order.status == OrderStatus.OUT_FOR_DELIVERY
        assert order.payment_status == PaymentStatus.PENDING


def test_the_completion_branch_no_longer_exists_in_the_source() -> None:
    """A schema change must not be able to reactivate a payment side effect."""
    import inspect

    from app.api.v1.routes import orders as legacy_orders

    source = inspect.getsource(legacy_orders.update_delivery_status)
    assert "PaymentStatus.PAID" not in source
    assert "OrderStatus.DELIVERED" not in source


# ------------------------------------- P2-2: releasing a job is a real handoff


def test_a_rider_releasing_a_job_gives_up_ownership() -> None:
    with session() as db:
        order = make_order(db, status=OrderStatus.READY, with_delivery=True)
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        delivery = db.query(Delivery).filter(Delivery.order_id == order.id).one()
        delivery.delivery_partner_id = rider.id
        delivery.status = DeliveryStatus.ASSIGNED
        delivery.assigned_at = datetime.now(timezone.utc)
        db.commit()
        delivery_id, rider_phone = delivery.id, rider.phone

    response = client.patch(
        f"/api/v1/delivery/{delivery_id}/status",
        headers=auth(token_for(rider_phone)),
        json={"status": "unassigned"},
    )
    assert response.status_code == 200, response.text

    with session() as db:
        delivery = db.get(Delivery, delivery_id)
        assert delivery.status == DeliveryStatus.UNASSIGNED
        # The old behaviour left the rider attached to a delivery in the open
        # pool, so it looked both claimed and available.
        assert delivery.delivery_partner_id is None
        assert delivery.assigned_at is None


def test_a_rider_cannot_release_a_job_after_pickup() -> None:
    with session() as db:
        order = make_order(db, status=OrderStatus.OUT_FOR_DELIVERY, with_delivery=True)
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        delivery = db.query(Delivery).filter(Delivery.order_id == order.id).one()
        delivery.delivery_partner_id = rider.id
        delivery.status = DeliveryStatus.PICKED_UP
        delivery.picked_up_at = datetime.now(timezone.utc)
        db.commit()
        delivery_id, rider_phone = delivery.id, rider.phone

    response = client.patch(
        f"/api/v1/delivery/{delivery_id}/status",
        headers=auth(token_for(rider_phone)),
        json={"status": "unassigned"},
    )
    # Goods are already with the rider; walking away is a failure, not a release.
    assert response.status_code == 409


# ------------------------------ P2-4: platform decisions vs merchant decisions


def test_reapproving_a_merchant_does_not_reopen_a_paused_store() -> None:
    with session() as db:
        store = make_store(db, is_active=True)
        merchant = db.get(Merchant, store.merchant_id)
        # The merchant deliberately paused this storefront.
        store.is_active = False
        db.commit()
        merchant_id, store_id = merchant.id, store.id

    response = client.patch(
        f"/api/v1/merchants/{merchant_id}/approve", headers=auth(token_for("+919000000001"))
    )
    assert response.status_code == 200, response.text

    with session() as db:
        assert db.get(Store, store_id).is_active is False


def test_suspension_still_takes_every_store_offline() -> None:
    with session() as db:
        store = make_store(db, is_active=True)
        db.commit()
        merchant_id, store_id = store.merchant_id, store.id

    admin = auth(token_for("+919000000001"))
    assert client.patch(
        f"/api/v1/merchants/{merchant_id}/status", headers=admin, json={"status": "suspended"}
    ).status_code == 200

    with session() as db:
        assert db.get(Store, store_id).is_active is False

    # And lifting the suspension restores what suspension switched off.
    assert client.patch(f"/api/v1/merchants/{merchant_id}/approve", headers=admin).status_code == 200
    with session() as db:
        assert db.get(Store, store_id).is_active is True


# ------------------------------------------------ P2-8: uploads must be images


def _upload(token: str, filename: str, content: bytes, content_type: str):
    return client.post(
        "/api/v1/media/images",
        headers=auth(token),
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


def _merchant_token() -> str:
    with session() as db:
        user = make_user(db, role=UserRole.MERCHANT, prefix="8")
        db.commit()
        return token_for(user.phone)


def test_a_non_image_declared_as_an_image_is_rejected() -> None:
    """The declared Content-Type is attacker-controlled; the bytes are not."""
    response = _upload(_merchant_token(), "payload.png", b"<html>not an image</html>", "image/png")
    assert response.status_code == 415
    assert "do not match" in response.json()["detail"]


def test_a_real_png_is_accepted() -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    response = _upload(_merchant_token(), "real.png", png, "image/png")
    assert response.status_code == 201, response.text
    assert response.json()["filename"].endswith(".png")


def test_a_riff_container_that_is_not_webp_is_rejected() -> None:
    not_webp = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 32
    response = _upload(_merchant_token(), "audio.webp", not_webp, "image/webp")
    assert response.status_code == 415


def test_customers_cannot_upload_at_all() -> None:
    with session() as db:
        user = make_user(db)
        db.commit()
        phone = user.phone
    response = _upload(token_for(phone), "real.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, "image/png")
    assert response.status_code == 403


# ----------------------------------------- P2-13: order numbers cannot collide


def test_order_numbers_are_unique_under_burst() -> None:
    from app.api.v1.routes.checkout import _new_order_number

    generated = {_new_order_number() for _ in range(50_000)}
    assert len(generated) == 50_000
    assert all(len(number) <= 32 for number in generated)


# ------------------------------------------------- P2-7: listings are bounded


def test_public_listings_accept_and_respect_a_page_size() -> None:
    for path in ("/api/v1/stores?limit=1", "/api/v1/products?limit=1"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert len(response.json()) <= 1


def test_listing_page_size_is_capped() -> None:
    assert client.get("/api/v1/stores?limit=100000").status_code == 422


def test_customer_order_history_is_paginated() -> None:
    with session() as db:
        order = make_order(db)
        db.commit()
        phone = db.get(User, order.user_id).phone

    token = token_for(phone)
    assert client.get("/api/v1/orders/me?limit=1", headers=auth(token)).status_code == 200
    assert client.get("/api/v1/orders/me?limit=0", headers=auth(token)).status_code == 422
