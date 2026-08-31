"""Cross-account access attempts, one per boundary the platform relies on.

Every one of these is an object another account owns, requested with a valid
session belonging to somebody else. The expected answer is always a refusal —
never the object, and never a 500 that reveals it exists by failing differently.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models.commerce import Merchant, Store
from app.models.orders import Delivery, DeliveryStatus, OrderStatus, PaymentStatus
from app.models.user import User, UserRole
from tests.factories import make_order, make_store, make_user, session

client = TestClient(app)
OTP = "123456"

REFUSALS = {401, 403, 404}


def token_for(phone: str) -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _other_customer_token() -> str:
    with session() as db:
        user = make_user(db)
        db.commit()
        return token_for(user.phone)


# ------------------------------------------------------------ customer data


def test_a_customer_cannot_read_another_customers_order() -> None:
    with session() as db:
        order = make_order(db)
        db.commit()
        order_id = order.id

    response = client.get(f"/api/v1/orders/{order_id}", headers=auth(_other_customer_token()))
    assert response.status_code in REFUSALS


def test_a_customer_cannot_cancel_another_customers_order() -> None:
    with session() as db:
        order = make_order(db, status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING)
        db.commit()
        order_id = order.id

    response = client.post(
        f"/api/v1/orders/{order_id}/cancel", headers=auth(_other_customer_token())
    )
    assert response.status_code in REFUSALS

    with session() as db:
        from app.models.orders import Order

        assert db.get(Order, order_id).status == OrderStatus.PLACED


def test_a_customer_cannot_read_another_customers_refund() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        order_id = order.id

    response = client.get(
        f"/api/v1/orders/{order_id}/refund", headers=auth(_other_customer_token())
    )
    assert response.status_code in REFUSALS


def test_a_customer_cannot_read_another_customers_tracking() -> None:
    with session() as db:
        order = make_order(db, status=OrderStatus.OUT_FOR_DELIVERY, with_delivery=True)
        db.commit()
        order_id = order.id

    response = client.get(
        f"/api/v1/orders/{order_id}/tracking", headers=auth(_other_customer_token())
    )
    assert response.status_code in REFUSALS


def test_a_customer_cannot_read_another_customers_order_history() -> None:
    with session() as db:
        order = make_order(db)
        db.commit()
        order_id = order.id

    response = client.get(
        f"/api/v1/orders/{order_id}/events", headers=auth(_other_customer_token())
    )
    assert response.status_code in REFUSALS


# ------------------------------------------------------------ merchant scope


def test_a_merchant_cannot_read_another_merchants_inventory() -> None:
    with session() as db:
        store = make_store(db)
        intruder = make_user(db, role=UserRole.MERCHANT, prefix="8")
        db.commit()
        store_id, intruder_phone = store.id, intruder.phone

    response = client.get(
        f"/api/v1/stores/{store_id}/inventory", headers=auth(token_for(intruder_phone))
    )
    assert response.status_code in REFUSALS


def test_a_merchant_cannot_edit_another_merchants_store() -> None:
    with session() as db:
        store = make_store(db)
        intruder = make_user(db, role=UserRole.MERCHANT, prefix="8")
        db.commit()
        store_id, intruder_phone, original = store.id, intruder.phone, store.name

    response = client.patch(
        f"/api/v1/stores/{store_id}",
        headers=auth(token_for(intruder_phone)),
        json={"name": "Hijacked Store"},
    )
    assert response.status_code in REFUSALS

    with session() as db:
        assert db.get(Store, store_id).name == original


def test_a_merchant_cannot_price_another_merchants_listing() -> None:
    with session() as db:
        store = make_store(db)
        intruder = make_user(db, role=UserRole.MERCHANT, prefix="8")
        db.commit()
        store_id, intruder_phone = store.id, intruder.phone

    response = client.post(
        f"/api/v1/stores/{store_id}/products",
        headers=auth(token_for(intruder_phone)),
        json={"product_id": str(store_id), "price": "1.00", "stock_quantity": 1, "is_available": True},
    )
    assert response.status_code in REFUSALS


def test_a_merchant_cannot_move_another_merchants_order() -> None:
    with session() as db:
        order = make_order(db, status=OrderStatus.PLACED)
        intruder = make_user(db, role=UserRole.MERCHANT, prefix="8")
        merchant = Merchant(
            owner_user_id=intruder.id, business_name="Intruder Traders", status="approved"
        )
        db.add(merchant)
        db.commit()
        order_id, intruder_phone = order.id, intruder.phone

    response = client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        headers=auth(token_for(intruder_phone)),
        json={"status": "accepted"},
    )
    assert response.status_code in REFUSALS


# -------------------------------------------------------------- rider scope


def _assigned_to_someone(db):
    order = make_order(db, status=OrderStatus.OUT_FOR_DELIVERY, with_delivery=True)
    owner = make_user(db, role=UserRole.DELIVERY, prefix="9")
    delivery = db.query(Delivery).filter(Delivery.order_id == order.id).one()
    delivery.delivery_partner_id = owner.id
    delivery.status = DeliveryStatus.PICKED_UP
    delivery.picked_up_at = datetime.now(timezone.utc)
    db.flush()
    return delivery


def test_a_rider_cannot_complete_another_riders_delivery() -> None:
    with session() as db:
        delivery = _assigned_to_someone(db)
        intruder = make_user(db, role=UserRole.DELIVERY, prefix="9")
        db.commit()
        delivery_id, intruder_phone = delivery.id, intruder.phone

    response = client.post(
        f"/api/v1/delivery/{delivery_id}/complete", headers=auth(token_for(intruder_phone))
    )
    assert response.status_code in REFUSALS


def test_a_rider_cannot_issue_a_proof_challenge_on_another_riders_delivery() -> None:
    with session() as db:
        delivery = _assigned_to_someone(db)
        intruder = make_user(db, role=UserRole.DELIVERY, prefix="9")
        db.commit()
        delivery_id, intruder_phone = delivery.id, intruder.phone

    response = client.post(
        f"/api/v1/delivery/{delivery_id}/proof/challenge",
        headers=auth(token_for(intruder_phone)),
    )
    assert response.status_code in REFUSALS


def test_a_rider_cannot_record_cash_against_another_riders_delivery() -> None:
    with session() as db:
        delivery = _assigned_to_someone(db)
        intruder = make_user(db, role=UserRole.DELIVERY, prefix="9")
        db.commit()
        delivery_id, intruder_phone = delivery.id, intruder.phone

    response = client.post(
        f"/api/v1/delivery/{delivery_id}/cod-collection",
        headers=auth(token_for(intruder_phone)),
        json={"amount": "120.00"},
    )
    assert response.status_code in REFUSALS


def test_a_rider_cannot_post_location_to_another_riders_delivery() -> None:
    with session() as db:
        delivery = _assigned_to_someone(db)
        intruder = make_user(db, role=UserRole.DELIVERY, prefix="9")
        db.commit()
        delivery_id, intruder_phone = delivery.id, intruder.phone

    response = client.post(
        f"/api/v1/delivery/{delivery_id}/location",
        headers=auth(token_for(intruder_phone)),
        json={
            "latitude": 18.52,
            "longitude": 73.85,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code in REFUSALS


# -------------------------------------------------------------- admin scope


def test_a_customer_cannot_reach_admin_surfaces() -> None:
    token = auth(_other_customer_token())
    for path in (
        "/api/v1/admin/users",
        "/api/v1/admin/overview",
        "/api/v1/admin/deliveries/active",
        "/api/v1/admin/refunds",
        "/api/v1/merchants",
    ):
        assert client.get(path, headers=token).status_code in REFUSALS, path


def test_a_rider_cannot_reach_admin_surfaces() -> None:
    with session() as db:
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        db.commit()
        phone = rider.phone
    token = auth(token_for(phone))
    for path in ("/api/v1/admin/users", "/api/v1/admin/overview", "/api/v1/admin/refunds"):
        assert client.get(path, headers=token).status_code in REFUSALS, path


def test_a_merchant_cannot_retry_a_refund() -> None:
    """Refund execution moves real money and is admin-only."""
    with session() as db:
        merchant = make_user(db, role=UserRole.MERCHANT, prefix="8")
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        phone, order_id = merchant.phone, order.id

    from app.services.refunds import REFUND_REASON_CANCELLED, ensure_refund_request

    with session() as db:
        from app.models.orders import Order

        refund = ensure_refund_request(db, db.get(Order, order_id), reason=REFUND_REASON_CANCELLED)
        db.commit()
        refund_id = refund.id

    response = client.post(
        f"/api/v1/admin/refunds/{refund_id}/retry", headers=auth(token_for(phone))
    )
    assert response.status_code in REFUSALS


# ------------------------------------------------------- unauthenticated use


def test_protected_surfaces_refuse_anonymous_callers() -> None:
    for path in (
        "/api/v1/users/me",
        "/api/v1/orders/me",
        "/api/v1/addresses/me",
        "/api/v1/admin/users",
        "/api/v1/delivery/tasks/available",
        "/api/v1/notifications/me",
    ):
        assert client.get(path).status_code in REFUSALS, path


def test_a_forged_token_is_refused() -> None:
    forged = {"Authorization": "Bearer not.a.real.token"}
    assert client.get("/api/v1/users/me", headers=forged).status_code == 401


def test_a_token_for_a_deactivated_account_stops_working() -> None:
    with session() as db:
        user = make_user(db)
        db.commit()
        phone, user_id = user.phone, user.id

    token = auth(token_for(phone))
    assert client.get("/api/v1/users/me", headers=token).status_code == 200

    with session() as db:
        db.get(User, user_id).is_active = False
        db.commit()

    # Deactivation takes effect immediately; the live token stops working.
    assert client.get("/api/v1/users/me", headers=token).status_code == 401
