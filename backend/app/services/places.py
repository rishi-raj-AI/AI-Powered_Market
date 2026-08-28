from __future__ import annotations

import math

import httpx

from app.core.config import settings

PLACES_BASE = "https://places.googleapis.com/v1"
GEOCODE_BASE = "https://geocode.googleapis.com/v4beta/geocode/location"


class PlacesUnavailable(RuntimeError):
    pass


def _enabled() -> bool:
    return settings.MAPS_PROVIDER == "google" and bool(settings.MAPS_API_KEY)


def _headers(field_mask: str | None = None) -> dict[str, str]:
    if not _enabled():
        raise PlacesUnavailable("Google Maps services are not configured")
    headers = {"X-Goog-Api-Key": settings.MAPS_API_KEY or "", "Content-Type": "application/json"}
    if field_mask:
        headers["X-Goog-FieldMask"] = field_mask
    return headers


def autocomplete(input_text: str, latitude: float | None = None, longitude: float | None = None, session_token: str | None = None) -> list[dict]:
    body: dict = {"input": input_text, "includedRegionCodes": ["in"], "regionCode": "IN", "languageCode": "en"}
    if latitude is not None and longitude is not None:
        body["locationBias"] = {"circle": {"center": {"latitude": latitude, "longitude": longitude}, "radius": 30000.0}}
    if session_token:
        body["sessionToken"] = session_token
    with httpx.Client(timeout=6.0) as client:
        response = client.post(
            f"{PLACES_BASE}/places:autocomplete",
            headers=_headers("suggestions.placePrediction.placeId,suggestions.placePrediction.text.text,suggestions.placePrediction.structuredFormat"),
            json=body,
        )
        response.raise_for_status()
    results = []
    for item in response.json().get("suggestions", []):
        prediction = item.get("placePrediction")
        if prediction:
            results.append({"place_id": prediction.get("placeId"), "text": prediction.get("text", {}).get("text", ""), "structured_format": prediction.get("structuredFormat")})
    return results


def place_details(place_id: str, session_token: str | None = None) -> dict:
    params = {"sessionToken": session_token} if session_token else None
    with httpx.Client(timeout=6.0) as client:
        response = client.get(
            f"{PLACES_BASE}/places/{place_id}",
            headers=_headers("id,formattedAddress,addressComponents,location,plusCode"),
            params=params,
        )
        response.raise_for_status()
    data = response.json()
    location = data.get("location") or {}
    return {
        "place_id": data.get("id", place_id),
        "formatted_address": data.get("formattedAddress"),
        "address_components": data.get("addressComponents", []),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "plus_code": (data.get("plusCode") or {}).get("globalCode"),
    }


def reverse_geocode(latitude: float, longitude: float) -> dict | None:
    with httpx.Client(timeout=6.0) as client:
        response = client.get(
            GEOCODE_BASE,
            headers=_headers(),
            params={"location.latitude": latitude, "location.longitude": longitude, "languageCode": "en", "regionCode": "IN"},
        )
        response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        return None
    first = results[0]
    return {"formatted_address": first.get("formattedAddress"), "place_id": first.get("placeId"), "address_components": first.get("addressComponents", [])}


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
