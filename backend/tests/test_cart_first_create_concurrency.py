"""PostgreSQL two-session regression for first-cart creation.

Requires the disposable PostGIS integration database used by backend CI.
No production database, external payment service, or territory mutation.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import sleep

from sqlalchemy import delete, func, select

from app.api.v1.routes.orders import _get_or_create_cart
from app.db.session import SessionLocal
from app.models.orders import Cart
from tests import factories


def test_simultaneous_first_cart_requests_share_one_cart():
    with factories.session() as db:
        user = factories.make_user(db)
        user_id = user.id
        db.commit()

    barrier = Barrier(2)

    def create_cart(delay_before_commit: float):
        with SessionLocal() as db:
            assert db.get_bind().dialect.name == "postgresql"
            barrier.wait(timeout=10)
            cart = _get_or_create_cart(db, user_id)
            cart_id = cart.id
            # Keep one transaction open long enough to exercise the unique
            # index's conflict-wait path in the competing transaction.
            sleep(delay_before_commit)
            db.commit()
            return cart_id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(create_cart, 0.2)
            second = pool.submit(create_cart, 0.0)
            ids = (first.result(timeout=20), second.result(timeout=20))
        assert ids[0] == ids[1]
        with SessionLocal() as db:
            assert db.scalar(
                select(func.count(Cart.id)).where(Cart.user_id == user_id)
            ) == 1
    finally:
        # Cart is not factory-tracked. Remove it before the user fixture's
        # foreign-key-aware teardown, even when the assertion fails.
        with SessionLocal() as db:
            db.execute(delete(Cart).where(Cart.user_id == user_id))
            db.commit()
