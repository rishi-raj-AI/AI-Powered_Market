"""Store opening hours, in India-local time, decided by the backend.

opens_at/closes_at were stored on the store and rendered by the clients, but
nothing ever enforced them, so an order could be placed at 03:00 against a
store that closes at 20:00. Availability is a backend decision; clients render
what the backend says rather than computing it themselves.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

#: All GaonOne business hours are expressed in India-local time regardless of
#: where the server or the customer happens to be.
BUSINESS_TZ = ZoneInfo("Asia/Kolkata")


def business_now() -> datetime:
    return datetime.now(BUSINESS_TZ)


def to_business_time(moment: datetime | None = None) -> datetime:
    """Normalise any instant to India-local time, aware-safe.

    A naive datetime is treated as already India-local rather than guessed at,
    which is what causes the classic naive/aware mix-up.
    """
    if moment is None:
        return business_now()
    if moment.tzinfo is None:
        return moment.replace(tzinfo=BUSINESS_TZ)
    return moment.astimezone(BUSINESS_TZ)


def is_open_at(opens_at: time | None, closes_at: time | None, moment: datetime | None = None) -> bool:
    """Is a store with this schedule open at this instant?

    A store with no schedule is always open — hours are optional and their
    absence must not silently close a shop that never set them.

    Overnight schedules are supported: closes_at earlier than opens_at means the
    window crosses midnight (22:00-02:00 is open at 23:30 and at 01:00).
    """
    if opens_at is None or closes_at is None:
        return True
    if opens_at == closes_at:
        # A zero-length window is meaningless as "closed all day"; treat an
        # identical pair as round-the-clock trading.
        return True

    local = to_business_time(moment).timetz().replace(tzinfo=None)
    if opens_at < closes_at:
        return opens_at <= local < closes_at
    # Crosses midnight.
    return local >= opens_at or local < closes_at


def store_is_open(store, moment: datetime | None = None) -> bool:
    return is_open_at(store.opens_at, store.closes_at, moment)


def describe_hours(opens_at: time | None, closes_at: time | None) -> str | None:
    if opens_at is None or closes_at is None:
        return None
    return f"{opens_at.strftime('%H:%M')}-{closes_at.strftime('%H:%M')} IST"
