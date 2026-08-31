"""One rider, one active delivery — under concurrency, not just in the UI.

Automatic dispatch locks the rider's user row and checks for an active
delivery; the admin assign path checks too. POST /delivery/{id}/claim never
checked at all, so the rule was only as strong as the client hiding the
button. Both paths now take the same lock in the same order.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models.orders import Delivery, DeliveryStatus, OrderStatus
from app.models.user import UserRole
from tests.factories import make_order, make_user, session

client = TestClient(app)
OTP = "123456"

ACTIVE = (DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP)


def token_for(phone: str) -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ready_delivery(db) -> Delivery:
    order = make_order(db, status=OrderStatus.READY, with_delivery=True)
    delivery = db.query(Delivery).filter(Delivery.order_id == order.id).one()
    delivery.status = DeliveryStatus.UNASSIGNED
    db.flush()
    return delivery


def _active_count(db, rider_id) -> int:
    return (
        db.query(Delivery)
        .filter(Delivery.delivery_partner_id == rider_id, Delivery.status.in_(ACTIVE))
        .count()
    )


def test_a_rider_cannot_claim_a_second_job_sequentially() -> None:
    with session() as db:
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        first = _ready_delivery(db)
        second = _ready_delivery(db)
        db.commit()
        rider_phone, rider_id = rider.phone, rider.id
        first_id, second_id = first.id, second.id

    headers = auth(token_for(rider_phone))
    assert client.post(f"/api/v1/delivery/{first_id}/claim", headers=headers).status_code == 200

    blocked = client.post(f"/api/v1/delivery/{second_id}/claim", headers=headers)
    assert blocked.status_code == 409
    assert "current delivery" in blocked.json()["detail"]

    with session() as db:
        assert _active_count(db, rider_id) == 1


def test_two_riders_racing_for_one_job_produce_one_winner() -> None:
    with session() as db:
        rider_a = make_user(db, role=UserRole.DELIVERY, prefix="9")
        rider_b = make_user(db, role=UserRole.DELIVERY, prefix="9")
        delivery = _ready_delivery(db)
        db.commit()
        phones = [rider_a.phone, rider_b.phone]
        delivery_id = delivery.id

    tokens = [auth(token_for(phone)) for phone in phones]

    def claim(headers):
        return client.post(f"/api/v1/delivery/{delivery_id}/claim", headers=headers).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, tokens))

    # Exactly one rider gets the job; the other is refused, not silently ignored.
    assert sorted(results) == [200, 409], results

    with session() as db:
        delivery = db.get(Delivery, delivery_id)
        assert delivery.status == DeliveryStatus.ASSIGNED
        assert delivery.delivery_partner_id is not None


def test_one_rider_racing_for_two_jobs_ends_with_one() -> None:
    """The failure the missing check allowed: parallel claims, both succeeding."""
    with session() as db:
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        deliveries = [_ready_delivery(db) for _ in range(4)]
        db.commit()
        rider_phone, rider_id = rider.phone, rider.id
        delivery_ids = [d.id for d in deliveries]

    headers = auth(token_for(rider_phone))

    def claim(delivery_id):
        return client.post(f"/api/v1/delivery/{delivery_id}/claim", headers=headers).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(claim, delivery_ids))

    assert results.count(200) == 1, f"more than one claim succeeded: {results}"

    with session() as db:
        assert _active_count(db, rider_id) == 1


def test_admin_assignment_respects_the_same_rule() -> None:
    with session() as db:
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        busy = _ready_delivery(db)
        busy.delivery_partner_id = rider.id
        busy.status = DeliveryStatus.ASSIGNED
        busy.assigned_at = datetime.now(timezone.utc)
        another = _ready_delivery(db)
        db.commit()
        rider_id, another_id = rider.id, another.id

    response = client.post(
        f"/api/v1/admin/deliveries/{another_id}/assign",
        headers=auth(token_for("+919000000001")),
        json={"rider_id": str(rider_id)},
    )
    assert response.status_code == 409
    assert "already has an active delivery" in response.json()["detail"]


def test_a_rider_can_claim_again_after_finishing() -> None:
    """The rule must not strand a rider who completed their job."""
    with session() as db:
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        done = _ready_delivery(db)
        done.delivery_partner_id = rider.id
        done.status = DeliveryStatus.DELIVERED
        done.delivered_at = datetime.now(timezone.utc)
        nxt = _ready_delivery(db)
        db.commit()
        rider_phone, next_id = rider.phone, nxt.id

    response = client.post(
        f"/api/v1/delivery/{next_id}/claim", headers=auth(token_for(rider_phone))
    )
    assert response.status_code == 200, response.text
