"""Deterministic PostgreSQL unique-index conflict regression for first carts.

Uses disposable integration database only; never production.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

from sqlalchemy import delete, func, select, text

from app.api.v1.routes.orders import _get_or_create_cart
from app.db.session import SessionLocal
from app.models.orders import Cart
from tests import factories


def test_simultaneous_first_cart_requests_share_one_cart():
    with factories.session() as db:
        user = factories.make_user(db)
        user_id = user.id
        db.commit()

    winner_inserted = Event()
    release_winner = Event()
    loser_started = Event()
    loser_pid = []

    def winner():
        with SessionLocal() as db:
            assert db.get_bind().dialect.name == "postgresql"
            cart = _get_or_create_cart(db, user_id)
            cart_id = cart.id
            winner_inserted.set()
            if not release_winner.wait(timeout=15):
                raise AssertionError("Timed out waiting to release first-cart transaction")
            db.commit()
            return cart_id

    def loser():
        with SessionLocal() as db:
            assert db.get_bind().dialect.name == "postgresql"
            assert winner_inserted.wait(timeout=10)
            loser_pid.append(db.scalar(text("SELECT pg_backend_pid()")))
            loser_started.set()
            cart = _get_or_create_cart(db, user_id)
            cart_id = cart.id
            db.commit()
            return cart_id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(winner)
            second = pool.submit(loser)
            try:
                assert loser_started.wait(timeout=10)
                # Observe the losing backend actually blocked by the winner's
                # uncommitted unique-index insertion; no sleep-based race guess.
                deadline = monotonic() + 10
                blocked = False
                with SessionLocal() as observer:
                    while monotonic() < deadline:
                        blockers = observer.scalar(
                            text("SELECT cardinality(pg_blocking_pids(:pid))"),
                            {"pid": loser_pid[0]},
                        )
                        if blockers and blockers > 0:
                            blocked = True
                            break
                        if second.done():
                            break
                        sleep(0.02)
                assert blocked, "Competing first-cart INSERT never observed waiting on a PostgreSQL lock"
            finally:
                release_winner.set()
            ids = (first.result(timeout=20), second.result(timeout=20))
        assert ids[0] == ids[1]
        with SessionLocal() as db:
            assert db.scalar(
                select(func.count(Cart.id)).where(Cart.user_id == user_id)
            ) == 1
    finally:
        release_winner.set()
        with SessionLocal() as db:
            db.execute(delete(Cart).where(Cart.user_id == user_id))
            db.commit()
