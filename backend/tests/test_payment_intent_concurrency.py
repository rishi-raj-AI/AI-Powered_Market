from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock

from fastapi.testclient import TestClient
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import func, select

from app.api.v1.routes import payments as payment_routes
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
