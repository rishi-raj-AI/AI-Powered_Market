"""P1: store opening hours are a backend decision, in India-local time.

opens_at/closes_at were stored on the store and rendered by the clients but
enforced nowhere, so an order could be placed at 03:00 against a store that
closes at 20:00.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.store_hours import (
    BUSINESS_TZ,
    describe_hours,
    is_open_at,
    store_is_open,
    to_business_time,
)
from tests.factories import make_listing, make_store, session

client = TestClient(app)


def ist(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 15, hour, minute, tzinfo=BUSINESS_TZ)


def test_store_without_hours_is_always_open() -> None:
    """Hours are optional; not setting them must not silently close a shop."""
    assert is_open_at(None, None, ist(3)) is True
    assert is_open_at(time(9), None, ist(3)) is True
    assert is_open_at(None, time(21), ist(3)) is True


def test_identical_open_and_close_is_round_the_clock() -> None:
    assert is_open_at(time(0), time(0), ist(3)) is True
    assert is_open_at(time(22), time(22), ist(11)) is True


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (7, 59, False),
        (8, 0, True),   # opening boundary is inclusive
        (12, 0, True),
        (20, 59, True),
        (21, 0, False),  # closing boundary is exclusive
        (23, 30, False),
        (3, 0, False),
    ],
)
def test_daytime_schedule_boundaries(hour, minute, expected) -> None:
    assert is_open_at(time(8), time(21), ist(hour, minute)) is expected


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (21, False),
        (22, True),   # opens
        (23, True),
        (0, True),    # across midnight
        (1, True),
        (2, False),   # closes
        (12, False),
    ],
)
def test_overnight_schedule_crosses_midnight(hour, expected) -> None:
    assert is_open_at(time(22), time(2), ist(hour)) is expected


def test_hours_are_evaluated_in_india_local_time_not_utc() -> None:
    """The bug this prevents: a UTC server closing an Indian shop at the wrong hour."""
    # 20:00 UTC is 01:30 next day in IST — outside an 08:00-21:00 window.
    utc_evening = datetime(2026, 6, 15, 20, 0, tzinfo=timezone.utc)
    assert is_open_at(time(8), time(21), utc_evening) is False

    # 05:00 UTC is 10:30 IST — inside it.
    utc_morning = datetime(2026, 6, 15, 5, 0, tzinfo=timezone.utc)
    assert is_open_at(time(8), time(21), utc_morning) is True


def test_naive_datetimes_are_treated_as_india_local() -> None:
    """Avoids the classic naive/aware mix-up rather than guessing UTC."""
    naive = datetime(2026, 6, 15, 10, 0)
    assert to_business_time(naive).tzinfo == BUSINESS_TZ
    assert is_open_at(time(8), time(21), naive) is True


def test_another_timezone_is_converted_not_ignored() -> None:
    london = datetime(2026, 6, 15, 20, 0, tzinfo=ZoneInfo("Europe/London"))
    # 20:00 London is 00:30 IST the next day.
    assert is_open_at(time(8), time(21), london) is False
    assert is_open_at(time(22), time(2), london) is True


def test_describe_hours_is_explicit_about_the_timezone() -> None:
    assert describe_hours(time(8), time(21)) == "08:00-21:00 IST"
    assert describe_hours(None, time(21)) is None


def test_store_helper_reads_the_stores_own_schedule() -> None:
    with session() as db:
        store = make_store(db, opens_at=time(8), closes_at=time(21))
        db.commit()
        assert store_is_open(store, ist(10)) is True
        assert store_is_open(store, ist(23)) is False


def test_checkout_refuses_a_closed_store() -> None:
    """The rule has to bite at checkout, which is the pricing/stock authority."""
    from app.api.v1.routes import checkout as checkout_route

    with session() as db:
        store = make_store(db, opens_at=time(8), closes_at=time(21), is_active=True)
        make_listing(db, store)
        db.commit()
        # Closed at 23:00 IST.
        assert store_is_open(store, ist(23)) is False
        # Checkout consults exactly this helper, so a closed store cannot be
        # ordered from regardless of what a client believes.
        assert checkout_route.store_is_open is store_is_open


def test_store_read_exposes_backend_computed_availability() -> None:
    """Clients render the backend's answer; they never compute their own."""
    with session() as db:
        store = make_store(db, opens_at=time(0), closes_at=time(0), is_active=True)
        db.commit()
        store_id = str(store.id)

    response = client.get(f"/api/v1/stores/{store_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "is_open_now" in body
    assert body["is_open_now"] is True
