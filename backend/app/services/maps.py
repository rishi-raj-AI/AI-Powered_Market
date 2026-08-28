from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import settings


ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"


@dataclass(frozen=True)
class RouteResult:
    distance_meters: int
    duration_seconds: int
    encoded_polyline: str


def maps_enabled() -> bool:
    return settings.MAPS_PROVIDER.lower().strip() == "google" and bool(settings.MAPS_API_KEY)


def _seconds(value: str | None) -> int:
    if not value or not value.endswith("s"):
        return 0
    try:
        return max(0, int(round(float(value[:-1]))))
    except ValueError:
        return 0


def compute_route(
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
) -> RouteResult | None:
    if not maps_enabled():
        return None

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
        return None

    routes = data.get("routes") or []
    if not routes:
        return None
    route = routes[0]
    polyline = (route.get("polyline") or {}).get("encodedPolyline") or ""
    return RouteResult(
        distance_meters=max(0, int(route.get("distanceMeters") or 0)),
        duration_seconds=_seconds(route.get("duration")),
        encoded_polyline=polyline,
    )
