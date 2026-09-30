from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import func, select

from app.api.v1.routes import payment_hardening, payments as payment_routes
from app.db.session import engine
from app.main import app
from app.models.integrations import PaymentAttempt
from app.models.orders import PaymentStatus
from tests.factories import make_order, make_user, session


client = TestClient(app)
OTP = "123456"


def _token(phone: str) -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_concurrent_payment_intents_reuse_one_provider_order(monkeypatch) -> None:
    with session() as db:
        customer = make_user(db, prefix="7")
        order = make_order(
            db,
            customer=customer,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        db.commit()
        customer_phone, order_id = customer.phone, order.id
    token = _token(customer_phone)

    arrivals = Barrier(2)
    first_provider_started = Event()
    release_provider = Event()
    provider_calls: list[dict] = []
    provider_calls_lock = Lock()
    order_lock_attempts = 0
    order_lock_attempts_lock = Lock()
    second_order_lock_attempted = Event()

    def create_provider_order(**kwargs):
        with provider_calls_lock:
            provider_calls.append(kwargs)
            call_number = len(provider_calls)
        if call_number == 1:
            first_provider_started.set()
            assert release_provider.wait(timeout=5)
        return {"id": f"order_payment_intent_{call_number}"}

    def observe_order_lock(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal order_lock_attempts
        if "orders" not in statement or "FOR UPDATE" not in statement:
            return
        with order_lock_attempts_lock:
            order_lock_attempts += 1
            if order_lock_attempts == 2:
                second_order_lock_attempted.set()

    monkeypatch.setattr(payment_routes.settings, "RAZORPAY_KEY_ID", "rzp_test_payment_intent")
    monkeypatch.setattr(payment_routes, "create_razorpay_order", create_provider_order)
    sqlalchemy_event.listen(engine, "before_cursor_execute", observe_order_lock)

    def create_intent(_: int) -> tuple[int, dict]:
        with TestClient(app) as worker_client:
            arrivals.wait(timeout=5)
            response = worker_client.post(
                f"/api/v1/payments/orders/{order_id}/intent", headers=_auth(token)
            )
            return response.status_code, response.json()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create_intent, index) for index in range(2)]
            assert first_provider_started.wait(timeout=5)
            # The second request has reached the row lock while the first is
            # still inside the provider call. It cannot create a second order.
            assert second_order_lock_attempted.wait(timeout=5)
            with provider_calls_lock:
                assert len(provider_calls) == 1
            release_provider.set()
            results = [future.result(timeout=5) for future in futures]
    finally:
        release_provider.set()
        sqlalchemy_event.remove(engine, "before_cursor_execute", observe_order_lock)

    assert [status for status, _ in results] == [200, 200]
    assert len({response["payment_attempt_id"] for _, response in results}) == 1
    assert len({response["provider_order_id"] for _, response in results}) == 1
    with provider_calls_lock:
        assert len(provider_calls) == 1
    with session() as db:
        assert db.scalar(
            select(func.count())
            .select_from(PaymentAttempt)
            .where(PaymentAttempt.order_id == order_id)
        ) == 1


def test_intent_retry_and_verify_lock_order_without_deadlock(monkeypatch) -> None:
    with session() as db:
        customer = make_user(db, prefix="7")
        order = make_order(
            db,
            customer=customer,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        attempt = PaymentAttempt(
            order_id=order.id,
            provider="razorpay",
            provider_order_id=f"order_payment_intent_lock_{uuid4().hex}",
            status="created",
            amount=order.total,
            currency="INR",
        )
        db.add(attempt)
        db.commit()
        customer_phone, order_id, attempt_id = customer.phone, order.id, attempt.id
    token = _token(customer_phone)

    monkeypatch.setattr(payment_routes.settings, "RAZORPAY_KEY_ID", "rzp_test_payment_intent")
    monkeypatch.setattr(payment_hardening, "verify_razorpay_signature", lambda **_kwargs: True)
    monkeypatch.setattr(payment_hardening, "ensure_settlement_entry", lambda *_args, **_kwargs: None)
    intent_update_started = Event()
    release_intent_update = Event()
    first_verify_lock_started = Event()
    verify_lock_order: list[str] = []
    verify_lock_order_lock = Lock()

    def observe_payment_lock_order(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = statement.lower()
        if "update payment_attempts" in normalized and not intent_update_started.is_set():
            # The intent now holds its Order lock and is about to update the
            # existing attempt. A verifier must wait for that same Order lock
            # rather than first taking the PaymentAttempt lock.
            intent_update_started.set()
            assert release_intent_update.wait(timeout=5)
        if not intent_update_started.is_set() or "for update" not in normalized:
            return
        target = "orders" if "from orders" in normalized else "payment_attempts" if "from payment_attempts" in normalized else None
        if target is None:
            return
        with verify_lock_order_lock:
            if not verify_lock_order:
                verify_lock_order.append(target)
                first_verify_lock_started.set()

    def retry_intent() -> int:
        with TestClient(app) as worker_client:
            response = worker_client.post(
                f"/api/v1/payments/orders/{order_id}/intent", headers=_auth(token)
            )
            return response.status_code

    def verify_payment() -> int:
        with TestClient(app) as worker_client:
            response = worker_client.post(
                "/api/v1/payments/verify",
                headers=_auth(token),
                json={
                    "payment_attempt_id": str(attempt_id),
                    "razorpay_payment_id": f"pay_payment_intent_lock_{uuid4().hex}",
                    "razorpay_signature": "s" * 32,
                },
            )
            return response.status_code

    sqlalchemy_event.listen(engine, "before_cursor_execute", observe_payment_lock_order)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            intent_future = executor.submit(retry_intent)
            assert intent_update_started.wait(timeout=5)
            verify_future = executor.submit(verify_payment)
            try:
                assert first_verify_lock_started.wait(timeout=5)
                assert verify_lock_order == ["orders"]
            finally:
                release_intent_update.set()
            assert intent_future.result(timeout=5) == 200
            assert verify_future.result(timeout=5) == 200
    finally:
        release_intent_update.set()
        sqlalchemy_event.remove(engine, "before_cursor_execute", observe_payment_lock_order)

    with session() as db:
        stored_attempt = db.get(PaymentAttempt, attempt_id)
        assert stored_attempt is not None
        assert stored_attempt.status == "paid"


def test_payment_webhook_locks_order_before_attempt() -> None:
    with session() as db:
        customer = make_user(db, prefix="7")
        order = make_order(
            db,
            customer=customer,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        provider_order_id = f"order_payment_webhook_lock_{uuid4().hex}"
        db.add(
            PaymentAttempt(
                order_id=order.id,
                provider="razorpay",
                provider_order_id=provider_order_id,
                status="attempted",
                amount=order.total,
                currency="INR",
            )
        )
        db.commit()

    lock_order: list[str] = []

    def observe_webhook_lock_order(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = statement.lower()
        if "for update" not in normalized:
            return
        if "from orders" in normalized:
            lock_order.append("orders")
        elif "from payment_attempts" in normalized:
            lock_order.append("payment_attempts")

    sqlalchemy_event.listen(engine, "before_cursor_execute", observe_webhook_lock_order)
    try:
        with session() as db:
            payment_hardening._process_event(
                db,
                {
                    "event": "payment.failed",
                    "payload": {"payment": {"entity": {"order_id": provider_order_id}}},
                },
            )
            db.rollback()
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", observe_webhook_lock_order)

    assert lock_order[:2] == ["orders", "payment_attempts"]
