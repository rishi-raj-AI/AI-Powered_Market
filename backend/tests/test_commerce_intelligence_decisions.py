from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from app.api.v1.routes.cart_health import assess_cart_item
from app.api.v1.routes.delivery_windows import INDIA_TZ, _generate_windows
from app.api.v1.routes.fulfillment_recommendation import is_store_open, recommend_mode
from app.api.v1.routes.merchant_reliability import reliability_score
from app.api.v1.routes.repeat_cadence import _median, _utc
from app.services.pricing import checkout_totals, delivery_fee


def test_cart_health_detects_blockers_and_low_stock():
    assert assess_cart_item(requested=2, stock=1, available=True, price=Decimal("10"))[0] == "blocked"
    state, reasons = assess_cart_item(requested=2, stock=3, available=True, price=Decimal("10"))
    assert state == "warning"
    assert "low_stock" in reasons
    assert assess_cart_item(requested=1, stock=20, available=True, price=Decimal("10"))[0] == "healthy"


def test_authoritative_checkout_pricing_is_consistent():
    assert delivery_fee(serviceable=True) == Decimal("20.00")
    assert delivery_fee(serviceable=False) == Decimal("0.00")
    fee, total = checkout_totals(subtotal=Decimal("149.50"), serviceable=True)
    assert fee == Decimal("20.00")
    assert total == Decimal("169.50")


def test_fulfillment_recommendation_prefers_live_delivery_then_pickup():
    assert recommend_mode(delivery=True, pickup=True, serviceable=True, is_open=True)[0] == "delivery_now"
    assert recommend_mode(delivery=True, pickup=True, serviceable=False, is_open=True)[0] == "pickup_now"
    assert recommend_mode(delivery=True, pickup=False, serviceable=True, is_open=False)[0] == "scheduled_delivery"
    assert recommend_mode(delivery=False, pickup=False, serviceable=False, is_open=False)[0] == "unavailable"


def test_store_hours_use_india_local_time_and_support_overnight_windows():
    at_ten_ist = datetime(2026, 8, 30, 4, 30, tzinfo=timezone.utc)
    assert is_store_open(opens_at=time(9), closes_at=time(18), now=at_ten_ist)
    at_one_ist = datetime(2026, 8, 30, 19, 30, tzinfo=timezone.utc)
    assert is_store_open(opens_at=time(20), closes_at=time(2), now=at_one_ist)
    assert not is_store_open(opens_at=time(9), closes_at=time(18), now=at_one_ist)


def test_fulfillment_windows_use_india_local_business_hours():
    late_utc = datetime(2026, 8, 30, 20, 30, tzinfo=timezone.utc)  # 02:00 IST next day
    slots = _generate_windows(late_utc, days=1)
    assert slots
    assert all(start.tzinfo == INDIA_TZ and end.tzinfo == INDIA_TZ for start, end in slots)
    assert all(7 <= start.hour < 21 and end.hour <= 22 for start, end in slots)
    assert slots[0][0].date().isoformat() == "2026-08-31"


def test_reliability_score_is_bounded_and_penalizes_failures():
    strong = reliability_score(delivered=90, cancelled=5, failed_deliveries=2, total=100)
    weak = reliability_score(delivered=50, cancelled=25, failed_deliveries=20, total=100)
    assert 0 <= weak < strong <= 1
    assert reliability_score(delivered=0, cancelled=0, failed_deliveries=0, total=0) == 0.5


def test_repeat_cadence_median_handles_even_and_odd_samples():
    assert _median([7, 14, 21]) == 14
    assert _median([7, 14]) == 10.5
    assert _median([]) is None


def test_repeat_cadence_normalizes_naive_and_aware_datetimes_to_utc():
    naive = datetime(2026, 8, 30, 12, 0)
    aware_ist = datetime(2026, 8, 30, 17, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert _utc(naive) == datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    assert _utc(aware_ist) == datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
