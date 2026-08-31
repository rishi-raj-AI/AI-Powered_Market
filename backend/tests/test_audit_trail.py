"""The status transition audit trail: one row per transition, with actor and why.

Rows are written by database triggers (migration 0007), which is the right
place: the trigger fires on any status update, including one the application
forgot to log, so the trail cannot be bypassed. What a trigger cannot know is
who acted and why, and that is what the application annotates.

The failure mode these tests exist to prevent is double-writing — an
application-level insert alongside the trigger, which would make the ledger
report two state changes where one happened.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.orders import Order, OrderStatus, PaymentStatus, StatusTransitionEvent
from app.models.user import User
from tests.factories import make_order, session

client = TestClient(app)
OTP = "123456"


def token_for(phone: str) -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _events(db, order_id, to_status: str) -> list[StatusTransitionEvent]:
    return (
        db.query(StatusTransitionEvent)
        .filter(
            StatusTransitionEvent.order_id == order_id,
            StatusTransitionEvent.to_status == to_status,
        )
        .all()
    )


def test_a_transition_produces_exactly_one_event() -> None:
    with session() as db:
        order = make_order(
            db,
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        db.commit()
        order_id = order.id
        customer_phone = db.get(User, order.user_id).phone

    response = client.post(
        f"/api/v1/orders/{order_id}/cancel", headers=auth(token_for(customer_phone))
    )
    assert response.status_code == 200, response.text

    with session() as db:
        events = _events(db, order_id, "cancelled")
        # One state change, one row. Two would mean the application inserted
        # alongside the trigger.
        assert len(events) == 1


def test_the_event_records_who_acted_and_why() -> None:
    with session() as db:
        order = make_order(
            db,
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        db.commit()
        order_id, user_id = order.id, order.user_id
        customer_phone = db.get(User, user_id).phone

    client.post(f"/api/v1/orders/{order_id}/cancel", headers=auth(token_for(customer_phone)))

    with session() as db:
        event = _events(db, order_id, "cancelled")[0]
        assert event.from_status == "placed"
        assert event.to_status == "cancelled"
        # The trigger cannot know either of these.
        assert event.actor_user_id == user_id
        assert event.reason == "customer_cancelled"


def test_the_trail_is_readable_through_the_api() -> None:
    with session() as db:
        order = make_order(
            db,
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        db.commit()
        order_id = order.id
        customer_phone = db.get(User, order.user_id).phone

    token = token_for(customer_phone)
    client.post(f"/api/v1/orders/{order_id}/cancel", headers=auth(token))

    events = client.get(f"/api/v1/orders/{order_id}/events", headers=auth(token))
    assert events.status_code == 200, events.text
    body = events.json()
    assert any(
        item["entity_type"] == "order"
        and item["to_status"] == "cancelled"
        and item["reason"] == "customer_cancelled"
        for item in body
    )


def test_an_unannotated_transition_is_still_recorded() -> None:
    """The trigger is the safety net: a direct status write is still audited."""
    with session() as db:
        order = make_order(
            db,
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        db.commit()
        order_id = order.id

        # No application-level annotation at all.
        order.status = OrderStatus.ACCEPTED
        db.commit()

        events = _events(db, order_id, "accepted")
        assert len(events) == 1
        assert events[0].from_status == "placed"
        # Nobody claimed responsibility, and the trail says so honestly.
        assert events[0].actor_user_id is None


def test_annotation_never_invents_an_event() -> None:
    """Annotating a transition that never happened must not create a row."""
    from app.services.audit import annotate_order_transition

    with session() as db:
        order = make_order(
            db,
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        db.commit()
        order_id = order.id

        result = annotate_order_transition(
            db,
            order,
            to_status="delivered",
            actor_user_id=order.user_id,
            reason="never_happened",
        )
        db.commit()

        assert result is None
        assert _events(db, order_id, "delivered") == []
