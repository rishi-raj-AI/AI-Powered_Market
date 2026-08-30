from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median


@dataclass(frozen=True)
class DeliveryPerformance:
    sample_count: int
    median_assignment_to_pickup_seconds: int | None
    median_pickup_to_delivery_seconds: int | None


def _seconds(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None or end < start:
        return None
    return int((end - start).total_seconds())


def summarize_delivery_performance(deliveries) -> DeliveryPerformance:
    assignment_to_pickup: list[int] = []
    pickup_to_delivery: list[int] = []
    terminal = 0
    for delivery in deliveries:
        if getattr(delivery, "delivered_at", None) is None:
            continue
        terminal += 1
        first = _seconds(getattr(delivery, "assigned_at", None), getattr(delivery, "picked_up_at", None))
        second = _seconds(getattr(delivery, "picked_up_at", None), getattr(delivery, "delivered_at", None))
        if first is not None:
            assignment_to_pickup.append(first)
        if second is not None:
            pickup_to_delivery.append(second)
    return DeliveryPerformance(
        sample_count=terminal,
        median_assignment_to_pickup_seconds=int(median(assignment_to_pickup)) if assignment_to_pickup else None,
        median_pickup_to_delivery_seconds=int(median(pickup_to_delivery)) if pickup_to_delivery else None,
    )


def eta_basis(*, route_duration_seconds: int | None, historical_delivery_seconds: int | None) -> dict:
    """Return explainable ETA basis; never invent a duration when neither source exists."""
    if route_duration_seconds is not None and route_duration_seconds >= 0:
        return {"available": True, "duration_seconds": int(route_duration_seconds), "basis": "live_route"}
    if historical_delivery_seconds is not None and historical_delivery_seconds >= 0:
        return {"available": True, "duration_seconds": int(historical_delivery_seconds), "basis": "historical_median"}
    return {"available": False, "duration_seconds": None, "basis": "unavailable"}
