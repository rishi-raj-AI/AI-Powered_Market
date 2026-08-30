import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.commerce import Store
from app.models.geography import Address, Village
from app.models.orders import Delivery, DeliveryLocation, DeliveryStatus, Order


FRESH_LOCATION_SECONDS = 180
ASSIGNED_SPEED_KMH = 18.0
LAST_MILE_SPEED_KMH = 22.0
PICKUP_BUFFER_MINUTES = 6
DROPOFF_BUFFER_MINUTES = 4


def _point_for_address(db: Session, address: Address) -> tuple[float, float] | None:
    if address.latitude is not None and address.longitude is not None:
        return float(address.latitude), float(address.longitude)
    village = db.get(Village, address.village_id)
    if village and village.latitude is not None and village.longitude is not None:
        return float(village.latitude), float(village.longitude)
    return None


def _distance_km(db: Session, a: tuple[float, float], b: tuple[float, float]) -> float:
    value = db.scalar(
        text(
            """
            SELECT ST_Distance(
                ST_SetSRID(ST_MakePoint(:a_lng, :a_lat), 4326)::geography,
                ST_SetSRID(ST_MakePoint(:b_lng, :b_lat), 4326)::geography
            ) / 1000.0
            """
        ),
        {"a_lat": a[0], "a_lng": a[1], "b_lat": b[0], "b_lng": b[1]},
    )
    return float(value or 0.0)


def _latest_location(db: Session, delivery_id: uuid.UUID) -> DeliveryLocation | None:
    return db.scalar(
        select(DeliveryLocation)
        .where(DeliveryLocation.delivery_id == delivery_id)
        .order_by(DeliveryLocation.recorded_at.desc(), DeliveryLocation.id.desc())
        .limit(1)
    )


def _historical_phase_minutes(db: Session) -> tuple[float | None, float | None]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    row = db.execute(
        select(
            func.percentile_cont(0.5).within_group(
                func.extract("epoch", Delivery.picked_up_at - Delivery.assigned_at) / 60.0
            ),
            func.percentile_cont(0.5).within_group(
                func.extract("epoch", Delivery.delivered_at - Delivery.picked_up_at) / 60.0
            ),
        ).where(
            Delivery.status == DeliveryStatus.DELIVERED,
            Delivery.delivered_at >= cutoff,
            Delivery.assigned_at.is_not(None),
            Delivery.picked_up_at.is_not(None),
        )
    ).one()
    return (
        float(row[0]) if row[0] is not None else None,
        float(row[1]) if row[1] is not None else None,
    )


def estimate_delivery_eta(db: Session, order: Order, delivery: Delivery) -> dict:
    now = datetime.now(timezone.utc)
    if delivery.status == DeliveryStatus.DELIVERED:
        return {
            "order_id": order.id,
            "delivery_id": delivery.id,
            "delivery_status": delivery.status.value,
            "phase": "delivered",
            "estimated_arrival_at": delivery.delivered_at,
            "eta_minutes": 0,
            "remaining_distance_km": 0.0,
            "telemetry_age_seconds": None,
            "confidence": "high",
            "basis": ["actual_delivery_timestamp"],
        }
    if delivery.status == DeliveryStatus.FAILED:
        return {
            "order_id": order.id,
            "delivery_id": delivery.id,
            "delivery_status": delivery.status.value,
            "phase": "exception",
            "estimated_arrival_at": None,
            "eta_minutes": None,
            "remaining_distance_km": None,
            "telemetry_age_seconds": None,
            "confidence": "unavailable",
            "basis": ["delivery_failed"],
        }
    if delivery.status == DeliveryStatus.UNASSIGNED:
        return {
            "order_id": order.id,
            "delivery_id": delivery.id,
            "delivery_status": delivery.status.value,
            "phase": "awaiting_assignment",
            "estimated_arrival_at": None,
            "eta_minutes": None,
            "remaining_distance_km": None,
            "telemetry_age_seconds": None,
            "confidence": "unavailable",
            "basis": ["rider_not_assigned"],
        }

    store = db.get(Store, order.store_id)
    address = db.get(Address, order.address_id)
    if store is None or address is None or store.latitude is None or store.longitude is None:
        return {
            "order_id": order.id,
            "delivery_id": delivery.id,
            "delivery_status": delivery.status.value,
            "phase": "en_route" if delivery.status == DeliveryStatus.PICKED_UP else "assigned",
            "estimated_arrival_at": None,
            "eta_minutes": None,
            "remaining_distance_km": None,
            "telemetry_age_seconds": None,
            "confidence": "unavailable",
            "basis": ["route_coordinates_missing"],
        }

    destination = _point_for_address(db, address)
    if destination is None:
        return {
            "order_id": order.id,
            "delivery_id": delivery.id,
            "delivery_status": delivery.status.value,
            "phase": "en_route" if delivery.status == DeliveryStatus.PICKED_UP else "assigned",
            "estimated_arrival_at": None,
            "eta_minutes": None,
            "remaining_distance_km": None,
            "telemetry_age_seconds": None,
            "confidence": "unavailable",
            "basis": ["destination_coordinates_missing"],
        }

    store_point = (float(store.latitude), float(store.longitude))
    latest = _latest_location(db, delivery.id)
    telemetry_age = None
    current_point = None
    fresh = False
    if latest is not None:
        recorded = latest.recorded_at
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        telemetry_age = max(0, int((now - recorded).total_seconds()))
        fresh = telemetry_age <= FRESH_LOCATION_SECONDS
        if fresh:
            current_point = (float(latest.latitude), float(latest.longitude))

    historical_pickup, historical_last_mile = _historical_phase_minutes(db)
    basis: list[str] = []
    confidence = "medium"

    if delivery.status == DeliveryStatus.ASSIGNED:
        pickup_origin = current_point or store_point
        to_store = _distance_km(db, pickup_origin, store_point)
        to_customer = _distance_km(db, store_point, destination)
        travel_minutes = (to_store + to_customer) / ASSIGNED_SPEED_KMH * 60.0 + PICKUP_BUFFER_MINUTES + DROPOFF_BUFFER_MINUTES
        if historical_pickup is not None and historical_last_mile is not None:
            historical_floor = max(1.0, historical_pickup + historical_last_mile)
            travel_minutes = max(travel_minutes, historical_floor * 0.65)
            basis.append("30d_phase_medians")
        basis.extend(["postgis_route_distance", "assigned_phase_speed_model"])
        if fresh:
            basis.append("fresh_rider_telemetry")
            confidence = "high"
        else:
            basis.append("store_origin_fallback")
            confidence = "medium"
        remaining = to_store + to_customer
        phase = "assigned_to_pickup"
    else:
        origin = current_point or store_point
        remaining = _distance_km(db, origin, destination)
        travel_minutes = remaining / LAST_MILE_SPEED_KMH * 60.0 + DROPOFF_BUFFER_MINUTES
        if historical_last_mile is not None:
            travel_minutes = max(travel_minutes, historical_last_mile * 0.55)
            basis.append("30d_last_mile_median")
        basis.extend(["postgis_route_distance", "last_mile_speed_model"])
        if fresh:
            basis.append("fresh_rider_telemetry")
            confidence = "high"
        else:
            basis.append("store_origin_fallback")
            confidence = "low"
        phase = "picked_up_to_dropoff"

    eta_minutes = max(1, int(math.ceil(travel_minutes)))
    return {
        "order_id": order.id,
        "delivery_id": delivery.id,
        "delivery_status": delivery.status.value,
        "phase": phase,
        "estimated_arrival_at": now + timedelta(minutes=eta_minutes),
        "eta_minutes": eta_minutes,
        "remaining_distance_km": round(remaining, 2),
        "telemetry_age_seconds": telemetry_age,
        "confidence": confidence,
        "basis": basis,
    }


def delivery_performance(db: Session, *, window_days: int, target_minutes: int) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    total = db.scalar(select(func.count()).select_from(Delivery).where(Delivery.updated_at >= cutoff)) or 0
    delivered = db.scalar(
        select(func.count()).select_from(Delivery).where(
            Delivery.status == DeliveryStatus.DELIVERED,
            Delivery.delivered_at >= cutoff,
        )
    ) or 0
    failed = db.scalar(
        select(func.count()).select_from(Delivery).where(
            Delivery.status == DeliveryStatus.FAILED,
            Delivery.failed_at >= cutoff,
        )
    ) or 0
    active = db.scalar(
        select(func.count()).select_from(Delivery).where(
            Delivery.status.in_([DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP]),
            Delivery.updated_at >= cutoff,
        )
    ) or 0

    stats = db.execute(
        select(
            func.avg(func.extract("epoch", Delivery.picked_up_at - Delivery.assigned_at) / 60.0),
            func.percentile_cont(0.5).within_group(func.extract("epoch", Delivery.picked_up_at - Delivery.assigned_at) / 60.0),
            func.avg(func.extract("epoch", Delivery.delivered_at - Delivery.picked_up_at) / 60.0),
            func.percentile_cont(0.5).within_group(func.extract("epoch", Delivery.delivered_at - Delivery.picked_up_at) / 60.0),
            func.avg(func.extract("epoch", Delivery.delivered_at - Order.created_at) / 60.0),
            func.percentile_cont(0.5).within_group(func.extract("epoch", Delivery.delivered_at - Order.created_at) / 60.0),
            func.percentile_cont(0.9).within_group(func.extract("epoch", Delivery.delivered_at - Order.created_at) / 60.0),
        )
        .join(Order, Order.id == Delivery.order_id)
        .where(
            Delivery.status == DeliveryStatus.DELIVERED,
            Delivery.delivered_at >= cutoff,
            Delivery.assigned_at.is_not(None),
            Delivery.picked_up_at.is_not(None),
        )
    ).one()

    on_time = db.scalar(
        select(func.count()).select_from(Delivery).join(Order, Order.id == Delivery.order_id).where(
            Delivery.status == DeliveryStatus.DELIVERED,
            Delivery.delivered_at >= cutoff,
            func.extract("epoch", Delivery.delivered_at - Order.created_at) <= target_minutes * 60,
        )
    ) or 0

    def rounded(value):
        return round(float(value), 2) if value is not None else None

    return {
        "window_days": window_days,
        "target_minutes": target_minutes,
        "total_deliveries": int(total),
        "delivered": int(delivered),
        "failed": int(failed),
        "active": int(active),
        "failure_rate": round(float(failed) / max(1, int(delivered) + int(failed)), 4),
        "on_time_rate": round(float(on_time) / int(delivered), 4) if delivered else None,
        "avg_assign_to_pickup_minutes": rounded(stats[0]),
        "median_assign_to_pickup_minutes": rounded(stats[1]),
        "avg_pickup_to_delivery_minutes": rounded(stats[2]),
        "median_pickup_to_delivery_minutes": rounded(stats[3]),
        "avg_created_to_delivery_minutes": rounded(stats[4]),
        "median_created_to_delivery_minutes": rounded(stats[5]),
        "p90_created_to_delivery_minutes": rounded(stats[6]),
    }
