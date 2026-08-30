from decimal import Decimal

from app.api.v1.routes.cart_health import assess_cart_item
from app.api.v1.routes.fulfillment_recommendation import recommend_mode
from app.api.v1.routes.merchant_reliability import reliability_score
from app.api.v1.routes.repeat_cadence import _median


def test_cart_health_detects_blockers_and_low_stock():
    assert assess_cart_item(requested=2, stock=1, available=True, price=Decimal("10"))[0] == "blocked"
    state, reasons = assess_cart_item(requested=2, stock=3, available=True, price=Decimal("10"))
    assert state == "warning"
    assert "low_stock" in reasons
    assert assess_cart_item(requested=1, stock=20, available=True, price=Decimal("10"))[0] == "healthy"


def test_fulfillment_recommendation_prefers_live_delivery_then_pickup():
    assert recommend_mode(delivery=True, pickup=True, serviceable=True, is_open=True)[0] == "delivery_now"
    assert recommend_mode(delivery=True, pickup=True, serviceable=False, is_open=True)[0] == "pickup_now"
    assert recommend_mode(delivery=True, pickup=False, serviceable=True, is_open=False)[0] == "scheduled_delivery"
    assert recommend_mode(delivery=False, pickup=False, serviceable=False, is_open=False)[0] == "unavailable"


def test_reliability_score_is_bounded_and_penalizes_failures():
    strong = reliability_score(delivered=90, cancelled=5, failed_deliveries=2, total=100)
    weak = reliability_score(delivered=50, cancelled=25, failed_deliveries=20, total=100)
    assert 0 <= weak < strong <= 1
    assert reliability_score(delivered=0, cancelled=0, failed_deliveries=0, total=0) == 0.5


def test_repeat_cadence_median_handles_even_and_odd_samples():
    assert _median([7, 14, 21]) == 14
    assert _median([7, 14]) == 10.5
    assert _median([]) is None
