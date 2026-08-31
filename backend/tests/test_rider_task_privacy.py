"""P1: a rider must not be able to harvest waiting customers.

/delivery/tasks/available returned the full task payload — recipient name,
phone, house details, directions and exact GPS — for every unassigned READY
delivery on the platform, to any user with the delivery role, before any
assignment existed. One onboarded rider account could poll it continuously and
read the whole customer base.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models.orders import Delivery, DeliveryStatus, OrderStatus
from app.models.user import UserRole
from tests.factories import make_order, make_user, session

client = TestClient(app)
OTP = "123456"

#: Fields that identify a household. None of these may appear before assignment.
IDENTIFYING_FIELDS = (
    "recipient_name",
    "recipient_phone",
    "house_details",
    "customer_landmark",
    "customer_directions",
    "customer_latitude",
    "customer_longitude",
    "store_phone",
)


def token_for(phone: str) -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ready_unassigned_order(db):
    order = make_order(db, status=OrderStatus.READY, with_delivery=True)
    delivery = db.query(Delivery).filter(Delivery.order_id == order.id).one()
    delivery.status = DeliveryStatus.UNASSIGNED
    db.flush()
    return order, delivery


def _assign(db, delivery, rider):
    delivery.delivery_partner_id = rider.id
    delivery.status = DeliveryStatus.ASSIGNED
    delivery.assigned_at = datetime.now(timezone.utc)
    db.flush()


def test_open_offers_never_expose_customer_identity() -> None:
    with session() as db:
        order, _delivery = _ready_unassigned_order(db)
        db.commit()
        order_number = order.order_number

    response = client.get(
        "/api/v1/delivery/tasks/available", headers=auth(token_for("+919000000002"))
    )
    assert response.status_code == 200, response.text
    offers = response.json()
    mine = [offer for offer in offers if offer["order_number"] == order_number]
    assert mine, "the open task should be offered to riders"

    for offer in offers:
        for field in IDENTIFYING_FIELDS:
            assert field not in offer, f"{field} leaked in a pre-assignment offer"


def test_open_offers_carry_enough_to_judge_the_job() -> None:
    """Least privilege must not mean riders cannot decide whether to accept."""
    with session() as db:
        order, _delivery = _ready_unassigned_order(db)
        db.commit()
        order_number = order.order_number

    offers = client.get(
        "/api/v1/delivery/tasks/available", headers=auth(token_for("+919000000002"))
    ).json()
    offer = next(o for o in offers if o["order_number"] == order_number)

    assert offer["store_name"]
    assert offer["store_latitude"] is not None
    assert offer["payment_method"] in {"cod", "upi"}
    assert offer["total"]
    assert offer["item_count"] >= 1
    # A coarse drop-off signal: an area label and a rounded distance.
    assert offer["dropoff_area"]
    assert offer["dropoff_distance_km"] is None or offer["dropoff_distance_km"] % 0.5 == 0


def test_assigned_rider_receives_full_delivery_detail() -> None:
    with session() as db:
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        order, delivery = _ready_unassigned_order(db)
        _assign(db, delivery, rider)
        db.commit()
        rider_phone, order_number = rider.phone, order.order_number

    response = client.get("/api/v1/delivery/tasks/me", headers=auth(token_for(rider_phone)))
    assert response.status_code == 200, response.text
    tasks = [t for t in response.json() if t["order_number"] == order_number]
    assert tasks, "an assigned delivery should appear in the rider's own tasks"
    task = tasks[0]
    # Now they need it, so now they get it.
    assert task["recipient_name"]
    assert task["customer_landmark"]
    assert task["customer_latitude"] is not None


def test_a_rider_cannot_see_another_riders_assigned_delivery() -> None:
    with session() as db:
        assigned_rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        order, delivery = _ready_unassigned_order(db)
        _assign(db, delivery, assigned_rider)
        db.commit()
        order_number = order.order_number

    other = client.get(
        "/api/v1/delivery/tasks/me", headers=auth(token_for("+919000000002"))
    ).json()
    assert all(task["order_number"] != order_number for task in other)


def test_assigned_delivery_is_no_longer_offered_to_everyone() -> None:
    with session() as db:
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        order, delivery = _ready_unassigned_order(db)
        _assign(db, delivery, rider)
        db.commit()
        order_number = order.order_number

    offers = client.get(
        "/api/v1/delivery/tasks/available", headers=auth(token_for("+919000000002"))
    ).json()
    assert all(offer["order_number"] != order_number for offer in offers)


def test_customers_cannot_read_the_rider_offer_board_at_all() -> None:
    with session() as db:
        _ready_unassigned_order(db)
        db.commit()

    customer = make_user_token()
    response = client.get("/api/v1/delivery/tasks/available", headers=auth(customer))
    assert response.status_code == 403


def make_user_token() -> str:
    with session() as db:
        user = make_user(db)
        db.commit()
        phone = user.phone
    return token_for(phone)


def test_offer_board_is_bounded() -> None:
    """An unbounded listing is both a scaling risk and a scraping convenience."""
    response = client.get(
        "/api/v1/delivery/tasks/available?limit=1", headers=auth(token_for("+919000000002"))
    )
    assert response.status_code == 200
    assert len(response.json()) <= 1
