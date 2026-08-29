from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic

import httpx

from app.core.config import settings


ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"
ROUTE_CACHE_TTL_SECONDS = 25
ROUTE_CACHE_MAX_ENTRIES = 512


@dataclass(frozen=True)
class RouteResult:
    distance_meters: int
    duration_seconds: int
    encoded_polyline: str


_route_cache: dict[tuple[float, float, float, float], tuple[float, RouteResult | None]] = {}
_route_cache_lock = Lock()


def maps_enabled() -> bool:
    return settings.MAPS_PROVIDER.lower().strip() == "google" and bool(settings.MAPS_API_KEY)


def _seconds(value: str | None) -> int:
    if not value or not value.endswith("s"):
        return 0
    try:
        return max(0, int(round(float(value[:-1]))))
    except ValueError:
        return 0


def _cache_key(origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> tuple[float, float, float, float]:
    # Roughly 10 m precision. This avoids paying for effectively identical rider positions.
    return (round(origin_lat, 4), round(origin_lng, 4), round(destination_lat, 4), round(destination_lng, 4))


def _cached(key: tuple[float, float, float, float]) -> tuple[bool, RouteResult | None]:
    now = monotonic()
    with _route_cache_lock:
        item = _route_cache.get(key)
        if item is None:
            return False, None
        expires_at, result = item
        if expires_at <= now:
            _route_cache.pop(key, None)
            return False, None
        return True, result


def _store_cache(key: tuple[float, float, float, float], result: RouteResult | None) -> None:
    now = monotonic()
    with _route_cache_lock:
        if len(_route_cache) >= ROUTE_CACHE_MAX_ENTRIES:
            expired = [cache_key for cache_key, (expires_at, _) in _route_cache.items() if expires_at <= now]
            for cache_key in expired:
                _route_cache.pop(cache_key, None)
            while len(_route_cache) >= ROUTE_CACHE_MAX_ENTRIES:
                _route_cache.pop(next(iter(_route_cache)))
        _route_cache[key] = (now + ROUTE_CACHE_TTL_SECONDS, result)


def compute_route(
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
) -> RouteResult | None:
    if not maps_enabled():
        return None

    key = _cache_key(origin_lat, origin_lng, destination_lat, destination_lng)
    hit, cached_result = _cached(key)
    if hit:
        return cached_result

    payload = {
        "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}},
        "destination": {
            "location": {"latLng": {"latitude": destination_lat, "longitude": destination_lng}}
        },
        "travelMode": "TWO_WHEELER",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False,
        "languageCode": "en-IN",
        "units": "METRIC",
    }
    headers = {
        "X-Goog-Api-Key": settings.MAPS_API_KEY or "",
        "X-Goog-FieldMask": FIELD_MASK,
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.post(ROUTES_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        _store_cache(key, None)
        return None

    routes = data.get("routes") or []
    if not routes:
        _store_cache(key, None)
        return None
    route = routes[0]
    polyline = (route.get("polyline") or {}).get("encodedPolyline") or ""
    result = RouteResult(
        distance_meters=max(0, int(route.get("distanceMeters") or 0)),
        duration_seconds=_seconds(route.get("duration")),
        encoded_polyline=polyline,
    )
    _store_cache(key, result)
    return result
