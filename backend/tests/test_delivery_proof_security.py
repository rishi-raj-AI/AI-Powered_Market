"""Delivery proof limits survive retries, new sessions, and concurrent requests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from queue import Queue
from threading import Barrier
from time import monotonic

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.api.v1.routes import delivery_operations as proof_routes
from app.main import app
from app.models.integrations import NotificationEvent
from app.models.orders import Delivery, DeliveryProof, DeliveryStatus, OrderStatus
from app.models.user import User, UserRole
from app.schemas.orders import DeliveryProofSubmit
from app.services.rate_limit import RateLimitExceeded, RateLimitUnavailable
from tests.factories import make_order, make_user, session

client = TestClient(app)
CODE = "654321"
WRONG_CODE = "000000"


class RecordingLimiter:
    def __init__(self):
        self.calls = []
        self.error = None

    def enforce(self, scope, identifier, *, limit, window_seconds):
        self.calls.append((scope, identifier, limit, window_seconds))
        if self.error is not None:
            raise self.error


@pytest.fixture
def limiter(monkeypatch):
    fake = RecordingLimiter()
    monkeypatch.setattr(proof_routes, "rate_limiter", fake)
    monkeypatch.setattr(proof_routes.secrets, "randbelow", lambda _: int(CODE))
    return fake


def _headers(phone):
    result = client.post(
        "/api/v1/auth/verify-otp", json={"phone": phone, "otp": "123456"}
    )
    assert result.status_code == 200, result.text
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


@pytest.fixture
def delivery_context(limiter):
    with session() as db:
        rider = make_user(db, role=UserRole.DELIVERY, prefix="9")
        order = make_order(db, status=OrderStatus.OUT_FOR_DELIVERY, with_delivery=True)
        delivery = db.scalar(select(Delivery).where(Delivery.order_id == order.id))
        delivery.delivery_partner_id = rider.id
        delivery.status = DeliveryStatus.PICKED_UP
        delivery.picked_up_at = datetime.now(timezone.utc)
        db.commit()
        context = {
            "delivery_id": delivery.id,
            "rider_id": rider.id,
            "customer_id": order.user_id,
            "headers": _headers(rider.phone),
        }
    return context


def _challenge(context, *, headers=None):
    return client.post(
        f"/api/v1/delivery/{context['delivery_id']}/proof/challenge",
        headers=headers or context["headers"],
    )


def _verify(context, *, otp=CODE, headers=None, **evidence):
    return client.post(
        f"/api/v1/delivery/{context['delivery_id']}/proof",
        headers=headers or context["headers"],
        json={"otp": otp, **evidence},
    )


def _proof(db, context):
    return db.scalar(
        select(DeliveryProof).where(DeliveryProof.delivery_id == context["delivery_id"])
    )


def _snapshot(context):
    with session() as db:
        proof = _proof(db, context)
        if proof is None:
            return None
        return {
            column.name: getattr(proof, column.name)
            for column in DeliveryProof.__table__.columns
        }


def _notifications(context):
    with session() as db:
        return list(
            db.scalars(
                select(NotificationEvent).where(
                    NotificationEvent.user_id == context["customer_id"],
                    NotificationEvent.event_type == "delivery.otp",
                )
            )
        )


def _allow_resend(context):
    # Move only the persisted clock boundary; tests never sleep to bypass it.
    with session() as db:
        _proof(db, context).last_challenge_at = datetime.now(timezone.utc) - timedelta(
            seconds=61
        )
        db.commit()


def test_challenge_cooldown_and_lifetime_cap_are_durable(delivery_context, limiter):
    context = delivery_context
    first = _challenge(context)
    assert first.status_code == 200, first.text
    assert "otp" not in first.json() and "otp_hash" not in first.json()
    first_state = _snapshot(context)
    assert first_state["challenge_count"] == 1
    assert first_state["verification_attempt_count"] == 0
    assert first_state["last_challenge_at"] is not None
    assert first_state["verification_locked_at"] is None
    assert CODE in _notifications(context)[0].body

    blocked = _challenge(context)
    assert blocked.status_code == 429, blocked.text
    assert _snapshot(context) == first_state
    assert len(_notifications(context)) == 1

    for expected_count in range(2, 6):
        _allow_resend(context)
        allowed = _challenge(context)
        assert allowed.status_code == 200, allowed.text
        assert _snapshot(context)["challenge_count"] == expected_count
    _allow_resend(context)
    before_cap = _snapshot(context)
    assert _challenge(context).status_code == 429
    assert _snapshot(context) == before_cap
    assert len(_notifications(context)) == 5
    # The fifth code remains usable; issue limits must not invalidate it.
    assert _verify(context).status_code == 200
    assert limiter.calls[0] == (
        "delivery-proof-challenge", str(context["rider_id"]), 20, 900
    )


def test_wrong_guess_budget_survives_resend_and_locks_even_correct_code(
    delivery_context, limiter
):
    context = delivery_context
    assert _challenge(context).status_code == 200
    for count in range(1, 3):
        assert _verify(context, otp=WRONG_CODE).status_code == 422
        assert _snapshot(context)["verification_attempt_count"] == count
    _allow_resend(context)
    assert _challenge(context).status_code == 200
    assert _snapshot(context)["verification_attempt_count"] == 2

    for count in range(3, 6):
        response = _verify(context, otp=WRONG_CODE)
        assert response.status_code == (429 if count == 5 else 422), response.text
        state = _snapshot(context)
        assert state["verification_attempt_count"] == count
        assert state["verified_at"] is None
    locked = _snapshot(context)
    assert locked["verification_locked_at"] is not None
    assert _verify(context).status_code == 429
    assert _challenge(context).status_code == 429
    assert _snapshot(context) == locked
    assert len(_notifications(context)) == 2
    assert (
        "delivery-proof-verify", str(context["rider_id"]), 60, 900
    ) in limiter.calls


def test_expired_code_does_not_verify_or_change_proof(delivery_context):
    context = delivery_context
    assert _challenge(context).status_code == 200
    with session() as db:
        _proof(db, context).otp_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    before = _snapshot(context)
    assert _verify(context).status_code == 409
    assert _snapshot(context) == before


def test_verification_without_issued_challenge_cannot_create_proof(
    delivery_context, limiter
):
    assert _verify(delivery_context).status_code == 409
    assert _snapshot(delivery_context) is None
    assert _notifications(delivery_context) == []
    assert limiter.calls == []


def test_verified_proof_is_immutable_and_replay_survives_expiry_and_redis_outage(
    delivery_context, limiter
):
    context = delivery_context
    assert _challenge(context).status_code == 200
    first = _verify(context, recipient_name="Asha", notes="Handed to recipient")
    assert first.status_code == 200, first.text
    with session() as db:
        _proof(db, context).otp_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    before = _snapshot(context)
    limiter.calls.clear()
    limiter.error = RateLimitUnavailable("unavailable")
    replay = _verify(
        context, otp=WRONG_CODE, recipient_name="Replacement", notes="Must not be saved"
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["verified_at"] == first.json()["verified_at"]
    assert replay.json()["recipient_name"] == "Asha"
    assert replay.json()["notes"] == "Handed to recipient"
    assert _snapshot(context) == before
    assert _challenge(context).status_code == 409
    assert _snapshot(context) == before
    assert limiter.calls == []
    assert len(_notifications(context)) == 1


@pytest.mark.parametrize("role", [UserRole.CUSTOMER, UserRole.MERCHANT, UserRole.DELIVERY, UserRole.ADMIN])
def test_role_and_assignment_checks_precede_proof_mutation(
    delivery_context, limiter, role
):
    context = delivery_context
    assert _challenge(context).status_code == 200
    assert _verify(context).status_code == 200
    with session() as db:
        intruder = make_user(db, role=role)
        db.commit()
        headers = _headers(intruder.phone)
    before = _snapshot(context)
    limiter.calls.clear()
    assert _challenge(context, headers=headers).status_code == 403
    assert _verify(context, headers=headers).status_code == 403
    assert _snapshot(context) == before
    assert limiter.calls == []


def test_super_admin_cannot_bypass_per_delivery_lock(delivery_context):
    context = delivery_context
    assert _challenge(context).status_code == 200
    with session() as db:
        admin = make_user(db, role=UserRole.ADMIN, prefix="6")
        admin.is_super_admin = True
        proof = _proof(db, context)
        proof.verification_attempt_count = 5
        proof.verification_locked_at = datetime.now(timezone.utc)
        db.commit()
        headers = _headers(admin.phone)
    before = _snapshot(context)
    assert _challenge(context, headers=headers).status_code == 429
    assert _verify(context, headers=headers).status_code == 429
    assert _snapshot(context) == before


@pytest.mark.parametrize("status", [DeliveryStatus.ASSIGNED, DeliveryStatus.FAILED, DeliveryStatus.DELIVERED])
def test_challenge_and_verification_require_active_picked_up_delivery(
    delivery_context, limiter, status
):
    context = delivery_context
    with session() as db:
        db.get(Delivery, context["delivery_id"]).status = status
        db.commit()
    assert _challenge(context).status_code == 409
    assert _verify(context).status_code == 409
    assert _snapshot(context) is None
    assert limiter.calls == []
    assert _notifications(context) == []


@pytest.mark.parametrize(
    ("error", "status"),
    [(RateLimitExceeded("too many"), 429), (RateLimitUnavailable("unavailable"), 503)],
)
def test_rate_limit_failures_cannot_issue_or_mutate_proof(
    delivery_context, limiter, error, status
):
    context = delivery_context
    limiter.error = error
    assert _challenge(context).status_code == status
    assert _snapshot(context) is None
    assert _notifications(context) == []
    limiter.error = None
    assert _challenge(context).status_code == 200
    before = _snapshot(context)
    limiter.error = error
    assert _verify(context, otp=WRONG_CODE).status_code == status
    assert _snapshot(context) == before
    assert len(_notifications(context)) == 1


def _concurrent_calls(context, operation, *, count):
    arrivals = Barrier(count)
    worker_pids = Queue()

    def invoke(index):
        # Each worker owns a separate real PostgreSQL session. The barrier is
        # before row locking; putting it after would deadlock correct locking.
        with session() as db:
            db.execute(text("SET LOCAL lock_timeout = '10s'"))
            worker_pids.put(db.scalar(text("SELECT pg_backend_pid()")))
            user = db.get(User, context["rider_id"])
            request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
            arrivals.wait(timeout=10)
            try:
                result = operation(index, db, user, request)
                return 200, result
            except HTTPException as exc:
                return exc.status_code, None

    with ThreadPoolExecutor(max_workers=count) as pool:
        with session() as holder:
            holder.scalar(select(Delivery).where(
                Delivery.id == context["delivery_id"]
            ).with_for_update())
            futures = [pool.submit(invoke, index) for index in range(count)]
            try:
                pids = [worker_pids.get(timeout=10) for _ in range(count)]
                deadline = monotonic() + 5
                while True:
                    # Require actual PostgreSQL contention before releasing
                    # the row. A lockless handler must fail this handshake,
                    # even when a scheduler would otherwise serialize calls.
                    blocked = [holder.scalar(text(
                        "SELECT cardinality(pg_blocking_pids(:pid)) > 0"
                    ), {"pid": pid}) for pid in pids]
                    if all(blocked):
                        break
                    assert not any(future.done() for future in futures), (
                        "A proof mutation bypassed the locked delivery"
                    )
                    assert monotonic() < deadline, "Workers did not contend for the delivery lock"
            finally:
                holder.rollback()
            return [future.result(timeout=10) for future in futures]


def test_concurrent_challenges_issue_exactly_one_code(delivery_context):
    context = delivery_context

    def issue(_index, db, user, request):
        return proof_routes.issue_delivery_proof_challenge(
            context["delivery_id"], request, db, user
        )

    results = _concurrent_calls(context, issue, count=2)
    assert sorted(status for status, _ in results) == [200, 429]
    assert _snapshot(context)["challenge_count"] == 1
    assert len(_notifications(context)) == 1
    with session() as db:
        assert len(list(db.scalars(select(DeliveryProof).where(
            DeliveryProof.delivery_id == context["delivery_id"]
        )))) == 1


def test_concurrent_wrong_guesses_cannot_exceed_the_durable_budget(delivery_context):
    context = delivery_context
    assert _challenge(context).status_code == 200

    def verify(_index, db, user, request):
        return proof_routes.verify_delivery_proof(
            context["delivery_id"], DeliveryProofSubmit(otp=WRONG_CODE), request, db, user
        )

    results = _concurrent_calls(context, verify, count=8)
    assert sorted(status for status, _ in results) == [422] * 4 + [429] * 4
    state = _snapshot(context)
    assert state["verification_attempt_count"] == 5
    assert state["verification_locked_at"] is not None
    assert state["verified_at"] is None


def test_concurrent_valid_verification_cannot_replace_winning_evidence(delivery_context):
    context = delivery_context
    assert _challenge(context).status_code == 200

    def verify(index, db, user, request):
        proof = proof_routes.verify_delivery_proof(
            context["delivery_id"],
            DeliveryProofSubmit(otp=CODE, recipient_name=f"Recipient {index}"),
            request, db, user,
        )
        return proof.verified_at, proof.recipient_name

    results = _concurrent_calls(context, verify, count=2)
    assert [status for status, _ in results] == [200, 200]
    assert results[0][1] == results[1][1]
    state = _snapshot(context)
    assert state["verified_at"] is not None
    assert state["verification_attempt_count"] == 0
    assert state["recipient_name"] == results[0][1][1]
