from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError

from app.api.v1.routes import admin as admin_routes
from app.main import app
from app.models.governance import AdministrativeAuditEvent
from app.models.orders import Delivery, DeliveryStatus, Order, OrderStatus, PaymentMethod, PaymentStatus
from app.models.user import User, UserRole
from tests.factories import make_order, make_user, session

client = TestClient(app)
OTP = "123456"
SUPER_ADMIN_PHONE = "+919000000001"


def _token(phone: str) -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str, request_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers


def _normal_admin() -> tuple[str, object]:
    with session() as db:
        user = make_user(db, role=UserRole.ADMIN, prefix="6")
        user.is_super_admin = False
        db.commit()
        return _token(user.phone), user.id


def _super_admin_token() -> str:
    with session() as db:
        user = db.scalar(select(User).where(User.phone == SUPER_ADMIN_PHONE))
        assert user is not None
        user.role = UserRole.ADMIN
        user.is_super_admin = True
        user.is_active = True
        db.commit()
    return _token(SUPER_ADMIN_PHONE)


def test_capabilities_are_explicit_and_deny_financial_writes_by_default() -> None:
    normal_token, _ = _normal_admin()
    normal = client.get("/api/v1/users/me/capabilities", headers=_auth(normal_token))
    assert normal.status_code == 200, normal.text
    assert "refund.read" not in normal.json()["capabilities"]
    assert "payment.read" not in normal.json()["capabilities"]
    assert "rider.operations" in normal.json()["capabilities"]
    assert "refund.write" not in normal.json()["capabilities"]
    assert "settlement.write" not in normal.json()["capabilities"]
    assert "settlement.read" not in normal.json()["capabilities"]
    assert "delivery_financial.write" not in normal.json()["capabilities"]
    assert "admin.manage" not in normal.json()["capabilities"]
    assert "user.manage" not in normal.json()["capabilities"]

    with session() as db:
        customer = make_user(db)
        db.commit()
        customer_token = _token(customer.phone)
    denied_by_default = client.get(
        "/api/v1/users/me/capabilities", headers=_auth(customer_token)
    )
    assert denied_by_default.status_code == 200
    assert denied_by_default.json()["capabilities"] == []

    elevated = client.get(
        "/api/v1/users/me/capabilities", headers=_auth(_super_admin_token())
    )
    assert elevated.status_code == 200
    assert "refund.write" in elevated.json()["capabilities"]
    assert "admin.manage" in elevated.json()["capabilities"]


def test_deactivated_admin_token_is_rejected_on_the_next_request() -> None:
    normal_token, admin_id = _normal_admin()
    assert client.get(
        "/api/v1/users/me/capabilities", headers=_auth(normal_token)
    ).status_code == 200
    with session() as db:
        admin = db.get(User, admin_id)
        assert admin is not None
        admin.is_active = False
        db.commit()
    assert client.get(
        "/api/v1/users/me/capabilities", headers=_auth(normal_token)
    ).status_code == 401


def test_normal_admin_cannot_retry_refunds_or_promote_admins() -> None:
    normal_token, _ = _normal_admin()
    assert client.get(
        "/api/v1/admin/audit-events", headers=_auth(normal_token)
    ).status_code == 403
    assert client.post(
        f"/api/v1/admin/refunds/{uuid4()}/retry", headers=_auth(normal_token)
    ).status_code == 403
    assert client.get(
        "/api/v1/payments/settlements", headers=_auth(normal_token)
    ).status_code == 403
    assert client.get(
        "/api/v1/admin/refunds", headers=_auth(normal_token)
    ).status_code == 403

    with session() as db:
        candidate = make_user(db)
        db.commit()
        candidate_id = candidate.id
    promotion = client.patch(
        f"/api/v1/admin/users/{candidate_id}/role",
        headers=_auth(normal_token),
        json={"role": "admin", "is_active": True},
    )
    assert promotion.status_code == 403
    role_change = client.patch(
        f"/api/v1/admin/users/{candidate_id}/role",
        headers=_auth(normal_token),
        json={"role": "delivery", "is_active": True},
    )
    assert role_change.status_code == 403
    with session() as db:
        assert db.scalar(
            select(AdministrativeAuditEvent).where(
                AdministrativeAuditEvent.resource_type == "user",
                AdministrativeAuditEvent.resource_id == str(candidate_id),
            )
        ) is None


def test_normal_admin_cannot_trigger_indirect_refund_or_settlement_writes() -> None:
    normal_token, _ = _normal_admin()
    with session() as db:
        cancellable = make_order(
            db, status=OrderStatus.PLACED, payment_status=PaymentStatus.PAID
        )
        order = make_order(
            db,
            status=OrderStatus.OUT_FOR_DELIVERY,
            payment_status=PaymentStatus.PAID,
            with_delivery=True,
        )
        delivery = db.query(Delivery).filter(Delivery.order_id == order.id).one()
        now = datetime.now(timezone.utc)
        delivery.status = DeliveryStatus.FAILED
        delivery.picked_up_at = now
        delivery.failed_at = now
        db.commit()
        cancellable_id = cancellable.id
        order_id, delivery_id = order.id, delivery.id

    cancellation = client.patch(
        f"/api/v1/merchant/orders/{cancellable_id}/status",
        headers=_auth(normal_token),
        json={"status": "cancelled"},
    )
    assert cancellation.status_code == 403
    with session() as db:
        assert db.get(Order, cancellable_id).status == OrderStatus.PLACED

    response = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/resolve-failure",
        headers=_auth(normal_token),
        json={"resolution": "return_to_store", "notes": "Returned safely"},
    )
    assert response.status_code == 403
    with session() as db:
        refreshed = db.get(Delivery, delivery_id)
        refreshed_order = db.get(Order, order_id)
        assert refreshed is not None and refreshed.status == DeliveryStatus.FAILED
        assert refreshed_order is not None and refreshed_order.status == OrderStatus.OUT_FOR_DELIVERY
        assert refreshed_order.payment_status == PaymentStatus.PAID


def test_normal_admin_cannot_impersonate_rider_financial_completion_steps() -> None:
    normal_token, _ = _normal_admin()
    with session() as db:
        order = make_order(
            db,
            status=OrderStatus.OUT_FOR_DELIVERY,
            payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PENDING,
            with_delivery=True,
        )
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        delivery = db.query(Delivery).filter(Delivery.order_id == order.id).one()
        delivery.delivery_partner_id = rider.id
        delivery.status = DeliveryStatus.PICKED_UP
        delivery.picked_up_at = datetime.now(timezone.utc)
        db.commit()
        delivery_id, amount = delivery.id, str(order.total)

    assert client.post(
        f"/api/v1/delivery/{delivery_id}/proof/challenge",
        headers=_auth(normal_token),
    ).status_code == 403
    assert client.post(
        f"/api/v1/delivery/{delivery_id}/cod-collection",
        headers=_auth(normal_token),
        json={"amount": amount},
    ).status_code == 403
    assert client.post(
        f"/api/v1/delivery/{delivery_id}/complete",
        headers=_auth(normal_token),
    ).status_code == 403


def test_admin_audit_is_attributable_and_committed_with_access_change() -> None:
    super_token = _super_admin_token()
    with session() as db:
        candidate = make_user(db)
        candidate.is_verified = False
        db.commit()
        candidate_id = candidate.id

    request_id = f"governance-test-{uuid4()}"
    response = client.patch(
        f"/api/v1/admin/users/{candidate_id}/role",
        headers=_auth(super_token, request_id),
        json={"role": "delivery", "is_active": True},
    )
    assert response.status_code == 200, response.text

    with session() as db:
        event = db.scalar(
            select(AdministrativeAuditEvent).where(
                AdministrativeAuditEvent.resource_type == "user",
                AdministrativeAuditEvent.resource_id == str(candidate_id),
                AdministrativeAuditEvent.request_id == request_id,
            )
        )
        assert event is not None
        assert event.actor_user_id is not None
        assert event.action == "user.access_updated"
        assert event.capability == "admin.manage"
        assert event.previous_state["role"] == "customer"
        assert event.resulting_state["role"] == "delivery"
        assert event.previous_state["is_verified"] is False
        assert event.resulting_state["is_verified"] is False

    audit_response = client.get(
        "/api/v1/admin/audit-events", headers=_auth(super_token)
    )
    assert audit_response.status_code == 200, audit_response.text
    assert any(
        item["request_id"] == request_id
        and item["resource_id"] == str(candidate_id)
        for item in audit_response.json()
    )


def test_audit_rows_reject_update_and_delete() -> None:
    super_token = _super_admin_token()
    with session() as db:
        candidate = make_user(db)
        db.commit()
        candidate_id = candidate.id
    request_id = f"governance-immutable-{uuid4()}"
    response = client.patch(
        f"/api/v1/admin/users/{candidate_id}/role",
        headers=_auth(super_token, request_id),
        json={"role": "delivery", "is_active": True},
    )
    assert response.status_code == 200, response.text

    with session() as db:
        event_id = db.scalar(
            select(AdministrativeAuditEvent.id).where(
                AdministrativeAuditEvent.request_id == request_id
            )
        )
        assert event_id is not None
        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(
                update(AdministrativeAuditEvent)
                .where(AdministrativeAuditEvent.id == event_id)
                .values(reason="tampered")
            )
            db.commit()
        db.rollback()
        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(
                delete(AdministrativeAuditEvent).where(
                    AdministrativeAuditEvent.id == event_id
                )
            )
            db.commit()
        db.rollback()


def test_audit_persistence_failure_rolls_back_access_mutation(monkeypatch) -> None:
    super_token = _super_admin_token()
    with session() as db:
        candidate = make_user(db)
        candidate.is_verified = False
        db.commit()
        candidate_id = candidate.id

    def add_invalid_audit(db, **_kwargs):
        db.add(
            AdministrativeAuditEvent(
                actor_user_id=uuid4(),
                action="forced.failure",
                capability="admin.manage",
                resource_type="user",
                resource_id=str(candidate_id),
                request_id="forced-audit-failure",
            )
        )

    monkeypatch.setattr(admin_routes, "record_admin_action", add_invalid_audit)
    failure_client = TestClient(app, raise_server_exceptions=False)
    response = failure_client.patch(
        f"/api/v1/admin/users/{candidate_id}/role",
        headers=_auth(super_token),
        json={"role": "delivery", "is_active": True},
    )
    assert response.status_code == 500

    with session() as db:
        candidate = db.get(User, candidate_id)
        assert candidate is not None
        assert candidate.role == UserRole.CUSTOMER
        assert candidate.is_verified is False
