from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.v1.routes import support as support_routes
from app.main import app
from app.models.commerce import Merchant, Store
from app.models.governance import AdministrativeAuditEvent
from app.models.integrations import NotificationEvent
from app.models.orders import Delivery
from app.models.support import SupportMessage, SupportTicket
from app.models.user import User, UserRole
from tests.factories import make_order, make_user, session

client = TestClient(app)
OTP = "123456"


def _token(phone: str) -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str, request_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers


def _admin(*, active: bool = True, verified: bool = True) -> tuple[str, object]:
    with session() as db:
        user = make_user(db, role=UserRole.ADMIN, prefix="6")
        user.is_active = active
        user.is_verified = verified
        db.commit()
        user_id, phone = user.id, user.phone
    return _token(phone), user_id


def _ticket(token: str, **payload) -> dict:
    response = client.post(
        "/api/v1/support/tickets",
        headers=_auth(token),
        json={
            "subject": "Order support",
            "description": "Please review this delivery issue",
            **payload,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_linked_context_is_derived_and_cross_role_ownership_is_hidden() -> None:
    with session() as db:
        customer = make_user(db, prefix="7")
        stranger = make_user(db, prefix="7")
        order = make_order(db, customer=customer, with_delivery=True)
        stranger_order = make_order(db, customer=stranger, with_delivery=True)
        delivery = db.scalar(select(Delivery).where(Delivery.order_id == order.id))
        stranger_delivery = db.scalar(
            select(Delivery).where(Delivery.order_id == stranger_order.id)
        )
        assert delivery is not None
        assert stranger_delivery is not None
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        delivery.delivery_partner_id = rider.id
        db.commit()
        customer_phone, stranger_phone, rider_phone = customer.phone, stranger.phone, rider.phone
        order_id, delivery_id, store_id = order.id, delivery.id, order.store_id
        stranger_order_id = stranger_order.id
        stranger_delivery_id = stranger_delivery.id
        stranger_store_id = stranger_order.store_id
        store_row = db.get(Store, store_id)
        assert store_row is not None
        merchant_row = db.get(Merchant, store_row.merchant_id)
        assert merchant_row is not None
        merchant_user = db.get(User, merchant_row.owner_user_id)
        assert merchant_user is not None
        merchant_phone = merchant_user.phone

    customer_ticket = _ticket(_token(customer_phone), order_id=str(order_id))
    assert customer_ticket["store_id"] == str(store_id)
    assert customer_ticket["requester_type"] == "customer"
    assert client.post(
        "/api/v1/support/tickets",
        headers=_auth(_token(stranger_phone)),
        json={"subject": "Wrong order", "description": "Not my order", "order_id": str(order_id)},
    ).status_code == 404
    assert client.post(
        "/api/v1/support/tickets",
        headers=_auth(_token(customer_phone)),
        json={
            "subject": "Mixed context",
            "description": "Do not reveal cross-tenant relationships",
            "order_id": str(order_id),
            "delivery_id": str(stranger_delivery_id),
            "store_id": str(stranger_store_id),
        },
    ).status_code == 404

    merchant_ticket = _ticket(_token(merchant_phone), order_id=str(order_id))
    assert merchant_ticket["requester_type"] == "merchant"
    rider_ticket = _ticket(_token(rider_phone), delivery_id=str(delivery_id))
    assert rider_ticket["order_id"] == str(order_id)
    assert rider_ticket["store_id"] == str(store_id)
    assert rider_ticket["requester_type"] == "delivery"
    assert client.post(
        "/api/v1/support/tickets",
        headers=_auth(_token(rider_phone)),
        json={
            "subject": "Mixed rider context",
            "description": "Do not reveal unrelated order relationships",
            "order_id": str(stranger_order_id),
            "delivery_id": str(delivery_id),
        },
    ).status_code == 404
    assert client.post(
        "/api/v1/support/tickets",
        headers=_auth(_token(stranger_phone)),
        json={
            "subject": "Wrong delivery",
            "description": "Not my delivery",
            "delivery_id": str(delivery_id),
        },
    ).status_code == 404


def test_non_admin_missing_and_unauthorized_references_share_one_404_contract() -> None:
    with session() as db:
        owner = make_user(db, prefix="7")
        stranger = make_user(db, prefix="7")
        order = make_order(db, customer=owner, with_delivery=True)
        delivery = db.scalar(select(Delivery).where(Delivery.order_id == order.id))
        assert delivery is not None
        db.commit()
        stranger_phone = stranger.phone
        references = {
            "order_id": order.id,
            "delivery_id": delivery.id,
            "store_id": order.store_id,
        }
    token = _token(stranger_phone)

    for field, existing_id in references.items():
        unauthorized = client.post(
            "/api/v1/support/tickets",
            headers=_auth(token),
            json={
                "subject": "Private context",
                "description": "This reference belongs to another requester",
                field: str(existing_id),
            },
        )
        missing = client.post(
            "/api/v1/support/tickets",
            headers=_auth(token),
            json={
                "subject": "Missing context",
                "description": "This reference does not exist",
                field: str(uuid4()),
            },
        )
        assert unauthorized.status_code == missing.status_code == 404
        assert unauthorized.json() == missing.json() == {
            "detail": "Linked support context not found"
        }


def test_public_messages_are_idempotent_and_internal_notes_never_leak_or_notify() -> None:
    with session() as db:
        requester = make_user(db, prefix="7")
        db.commit()
        requester_phone, requester_id = requester.phone, requester.id
    requester_token = _token(requester_phone)
    admin_token, _ = _admin()
    ticket = _ticket(requester_token)
    ticket_id = ticket["id"]

    internal_key = str(uuid4())
    internal = client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/internal-notes",
        headers=_auth(admin_token),
        json={"body": "Provider reference is staff-only", "idempotency_key": internal_key},
    )
    assert internal.status_code == 201, internal.text
    requester_view = client.get(
        f"/api/v1/support/tickets/{ticket_id}", headers=_auth(requester_token)
    )
    assert requester_view.status_code == 200
    assert "internal_notes" not in requester_view.json()
    assert "assigned_admin_id" not in requester_view.json()
    assert "triage_summary" not in requester_view.json()
    assert "suggested_action" not in requester_view.json()
    assert "Provider reference is staff-only" not in requester_view.text
    public_transcript = client.get(
        f"/api/v1/support/tickets/{ticket_id}/messages?limit=1&offset=0",
        headers=_auth(requester_token),
    )
    assert public_transcript.status_code == 200
    assert public_transcript.json() == []
    with session() as db:
        assert db.scalar(
            select(func.count()).select_from(NotificationEvent).where(
                NotificationEvent.user_id == requester_id,
                NotificationEvent.data["ticket_id"].as_string() == ticket_id,
            )
        ) == 0

    public_key = str(uuid4())
    first = client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/messages",
        headers=_auth(admin_token),
        json={"body": "We are reviewing your case", "idempotency_key": public_key},
    )
    retry = client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/messages",
        headers=_auth(admin_token),
        json={"body": "We are reviewing your case", "idempotency_key": public_key},
    )
    assert first.status_code == retry.status_code == 201
    assert first.json()["id"] == retry.json()["id"]
    mismatch = client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/messages",
        headers=_auth(admin_token),
        json={"body": "A different payload", "idempotency_key": public_key},
    )
    assert mismatch.status_code == 409
    whitespace = client.post(
        f"/api/v1/support/tickets/{ticket_id}/messages",
        headers=_auth(requester_token),
        json={"body": "   ", "idempotency_key": str(uuid4())},
    )
    assert whitespace.status_code == 422
    requester_messages = client.get(
        f"/api/v1/support/tickets/{ticket_id}/messages?limit=1&offset=0",
        headers=_auth(requester_token),
    )
    assert requester_messages.status_code == 200
    assert requester_messages.json() == [first.json()]
    internal_transcript = client.get(
        f"/api/v1/admin/support/tickets/{ticket_id}/messages?visibility=internal",
        headers=_auth(admin_token),
    )
    assert internal_transcript.status_code == 200
    assert internal_transcript.json()[0]["body"] == "Provider reference is staff-only"
    with session() as db:
        assert db.scalar(
            select(func.count()).select_from(SupportMessage).where(
                SupportMessage.ticket_id == ticket_id,
                SupportMessage.visibility == "public",
            )
        ) == 1
        assert db.scalar(
            select(func.count()).select_from(NotificationEvent).where(
                NotificationEvent.user_id == requester_id,
                NotificationEvent.event_type == "support.public_message",
            )
        ) == 1


def test_successful_public_message_replay_survives_later_ticket_closure() -> None:
    with session() as db:
        requester = make_user(db, prefix="7")
        db.commit()
        requester_phone = requester.phone
    requester_token = _token(requester_phone)
    admin_token, _ = _admin()

    requester_ticket = _ticket(requester_token)
    requester_key = str(uuid4())
    requester_payload = {
        "body": "Please retain this reply",
        "idempotency_key": requester_key,
    }
    requester_first = client.post(
        f"/api/v1/support/tickets/{requester_ticket['id']}/messages",
        headers=_auth(requester_token),
        json=requester_payload,
    )
    assert requester_first.status_code == 201, requester_first.text
    closed = client.patch(
        f"/api/v1/admin/support/tickets/{requester_ticket['id']}",
        headers=_auth(admin_token),
        json={"status": "closed", "expected_version": 1},
    )
    assert closed.status_code == 200, closed.text
    requester_replay = client.post(
        f"/api/v1/support/tickets/{requester_ticket['id']}/messages",
        headers=_auth(requester_token),
        json=requester_payload,
    )
    assert requester_replay.status_code == 201
    assert requester_replay.json() == requester_first.json()
    requester_new = client.post(
        f"/api/v1/support/tickets/{requester_ticket['id']}/messages",
        headers=_auth(requester_token),
        json={"body": "A genuinely new reply", "idempotency_key": str(uuid4())},
    )
    assert requester_new.status_code == 409
    requester_mismatch = client.post(
        f"/api/v1/support/tickets/{requester_ticket['id']}/messages",
        headers=_auth(requester_token),
        json={"body": "Changed payload", "idempotency_key": requester_key},
    )
    assert requester_mismatch.status_code == 409

    admin_ticket = _ticket(requester_token)
    admin_key = str(uuid4())
    admin_payload = {"body": "Public staff reply", "idempotency_key": admin_key}
    admin_first = client.post(
        f"/api/v1/admin/support/tickets/{admin_ticket['id']}/messages",
        headers=_auth(admin_token),
        json=admin_payload,
    )
    assert admin_first.status_code == 201, admin_first.text
    closed = client.patch(
        f"/api/v1/admin/support/tickets/{admin_ticket['id']}",
        headers=_auth(admin_token),
        json={"status": "closed", "expected_version": 1},
    )
    assert closed.status_code == 200, closed.text
    admin_replay = client.post(
        f"/api/v1/admin/support/tickets/{admin_ticket['id']}/messages",
        headers=_auth(admin_token),
        json=admin_payload,
    )
    assert admin_replay.status_code == 201
    assert admin_replay.json() == admin_first.json()
    admin_new = client.post(
        f"/api/v1/admin/support/tickets/{admin_ticket['id']}/messages",
        headers=_auth(admin_token),
        json={"body": "A genuinely new staff reply", "idempotency_key": str(uuid4())},
    )
    assert admin_new.status_code == 409
    admin_mismatch = client.post(
        f"/api/v1/admin/support/tickets/{admin_ticket['id']}/messages",
        headers=_auth(admin_token),
        json={"body": "Changed staff payload", "idempotency_key": admin_key},
    )
    assert admin_mismatch.status_code == 409

    with session() as db:
        for ticket_id in (requester_ticket["id"], admin_ticket["id"]):
            assert db.scalar(
                select(func.count()).select_from(SupportMessage).where(
                    SupportMessage.ticket_id == ticket_id,
                    SupportMessage.visibility == "public",
                )
            ) == 1


def test_assignment_requires_eligible_admin_and_is_audited() -> None:
    with session() as db:
        requester = make_user(db, prefix="7")
        ineligible = make_user(db, role=UserRole.DELIVERY, prefix="9")
        db.commit()
        requester_phone, ineligible_id = requester.phone, ineligible.id
    actor_token, actor_id = _admin()
    _, assignee_id = _admin()
    ticket = _ticket(_token(requester_phone))

    missing_version = client.patch(
        f"/api/v1/admin/support/tickets/{ticket['id']}/assignment",
        headers=_auth(actor_token),
        json={"assigned_admin_id": str(assignee_id)},
    )
    assert missing_version.status_code == 422

    denied = client.patch(
        f"/api/v1/admin/support/tickets/{ticket['id']}/assignment",
        headers=_auth(actor_token),
        json={"assigned_admin_id": str(ineligible_id), "expected_version": 0},
    )
    assert denied.status_code == 422
    assigned = client.patch(
        f"/api/v1/admin/support/tickets/{ticket['id']}/assignment",
        headers=_auth(actor_token, "support-assignment-test"),
        json={"assigned_admin_id": str(assignee_id), "expected_version": 0},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assigned_admin_id"] == str(assignee_id)
    assert assigned.json()["version"] == 1
    stale = client.patch(
        f"/api/v1/admin/support/tickets/{ticket['id']}/assignment",
        headers=_auth(actor_token),
        json={"assigned_admin_id": None, "expected_version": 0},
    )
    assert stale.status_code == 409
    with session() as db:
        event = db.scalar(
            select(AdministrativeAuditEvent).where(
                AdministrativeAuditEvent.actor_user_id == actor_id,
                AdministrativeAuditEvent.request_id == "support-assignment-test",
            )
        )
        assert event is not None
        assert event.action == "support.ticket_assigned"


def test_state_version_conflicts_and_waiting_customer_reply_mapping() -> None:
    with session() as db:
        requester = make_user(db, prefix="7")
        db.commit()
        requester_phone = requester.phone
    requester_token = _token(requester_phone)
    admin_token, admin_id = _admin()
    ticket = _ticket(requester_token)
    ticket_id = ticket["id"]

    assigned = client.patch(
        f"/api/v1/admin/support/tickets/{ticket_id}/assignment",
        headers=_auth(admin_token),
        json={"assigned_admin_id": str(admin_id), "expected_version": 0},
    )
    assert assigned.status_code == 200, assigned.text

    waiting = client.patch(
        f"/api/v1/admin/support/tickets/{ticket_id}",
        headers=_auth(admin_token),
        json={"status": "waiting_customer", "expected_version": 1},
    )
    assert waiting.status_code == 200, waiting.text
    assert waiting.json()["version"] == 2
    stale = client.patch(
        f"/api/v1/admin/support/tickets/{ticket_id}",
        headers=_auth(admin_token),
        json={"status": "resolved", "expected_version": 1},
    )
    assert stale.status_code == 409
    reply = client.post(
        f"/api/v1/support/tickets/{ticket_id}/messages",
        headers=_auth(requester_token),
        json={"body": "Here is the requested detail", "idempotency_key": str(uuid4())},
    )
    assert reply.status_code == 201, reply.text
    refreshed = client.get(
        f"/api/v1/support/tickets/{ticket_id}", headers=_auth(requester_token)
    ).json()
    assert refreshed["status"] == "in_progress"
    assert refreshed["version"] == 3
    with session() as db:
        event = db.scalar(
            select(NotificationEvent).where(
                NotificationEvent.user_id == admin_id,
                NotificationEvent.event_type == "support.requester_replied",
            )
        )
        assert event is not None
        assert event.title == "Requester replied"
    invalid = client.patch(
        f"/api/v1/admin/support/tickets/{ticket_id}",
        headers=_auth(admin_token),
        json={"status": "open", "expected_version": 3},
    )
    assert invalid.status_code == 409


def test_concurrent_assignment_allows_only_one_versioned_writer() -> None:
    with session() as db:
        requester = make_user(db, prefix="7")
        db.commit()
        requester_phone = requester.phone
    actor_token, _ = _admin()
    _, first_admin_id = _admin()
    _, second_admin_id = _admin()
    ticket = _ticket(_token(requester_phone))
    barrier = Barrier(2)

    def assign(assignee_id) -> int:
        worker_client = TestClient(app)
        barrier.wait()
        response = worker_client.patch(
            f"/api/v1/admin/support/tickets/{ticket['id']}/assignment",
            headers=_auth(actor_token),
            json={"assigned_admin_id": str(assignee_id), "expected_version": 0},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(assign, (first_admin_id, second_admin_id)))
    assert sorted(statuses) == [200, 409]
    with session() as db:
        stored = db.get(SupportTicket, ticket["id"])
        assert stored is not None
        assert stored.version == 1
        assert stored.assigned_admin_id in {first_admin_id, second_admin_id}


def test_audit_failure_rolls_back_support_mutation(monkeypatch) -> None:
    with session() as db:
        requester = make_user(db, prefix="7")
        db.commit()
        requester_phone = requester.phone
    admin_token, _ = _admin()
    ticket = _ticket(_token(requester_phone))

    def invalid_audit(db, **_kwargs):
        db.add(
            AdministrativeAuditEvent(
                actor_user_id=uuid4(),
                action="forced.failure",
                capability="support.manage",
                resource_type="support_ticket",
                resource_id=ticket["id"],
                request_id="forced-support-audit-failure",
            )
        )

    monkeypatch.setattr(support_routes, "record_admin_action", invalid_audit)
    failure_client = TestClient(app, raise_server_exceptions=False)
    response = failure_client.patch(
        f"/api/v1/admin/support/tickets/{ticket['id']}",
        headers=_auth(admin_token),
        json={
            "status": "resolved",
            "resolution_notes": "This must roll back",
            "expected_version": 0,
        },
    )
    assert response.status_code == 500
    with session() as db:
        stored = db.get(SupportTicket, ticket["id"])
        assert stored is not None
        assert stored.status == "open"
        assert stored.resolution_notes is None
        assert stored.version == 0


def test_ticket_payload_cannot_grant_privileges() -> None:
    with session() as db:
        requester = make_user(db, prefix="7")
        db.commit()
        requester_phone, requester_id = requester.phone, requester.id
    response = client.post(
        "/api/v1/support/tickets",
        headers=_auth(_token(requester_phone)),
        json={
            "subject": "Access request",
            "description": "Please make this account an administrator",
            "role": "admin",
        },
    )
    assert response.status_code == 422
    with session() as db:
        assert db.get(User, requester_id).role == UserRole.CUSTOMER
