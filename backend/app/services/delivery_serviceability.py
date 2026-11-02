"""Authoritative store-specific delivery eligibility for the legacy service-area model.

This does NOT enlarge delivery territories or infer a doorstep from a village
centroid. Both quotation and order placement call this function; the latter
rechecks eligibility in its checkout transaction.
"""

from dataclasses import dataclass
from math import isfinite
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.commerce import Merchant, MerchantStatus, Store
from app.models.geography import Address, ServiceArea, Village
from app.services.spatial import point_is_in_service_area

EVALUATION_VERSION = "legacy-hub-radius-v1"


@dataclass(frozen=True)
class DeliveryDecision:
    serviceable: bool
    reason_code: str
    human_readable_message: str
    store_id: UUID
    address_id: UUID
    matched_territory_id: UUID | None = None
    distance_km: float | None = None
    delivery_fee: None = None
    estimated_delivery_time: None = None
    location_confidence: str = "unverified"
    evaluation_version: str = EVALUATION_VERSION


def _reject(store: Store, address: Address, code: str, message: str, confidence: str) -> DeliveryDecision:
    return DeliveryDecision(
        serviceable=False,
        reason_code=code,
        human_readable_message=message,
        store_id=store.id,
        address_id=address.id,
        location_confidence=confidence,
    )


def evaluate_delivery(
    db: Session,
    store: Store,
    address: Address,
    *,
    merchant: Merchant | None = None,
) -> DeliveryDecision:
    """Check the store's *assigned* active hub-centered service area.

    A store pin is NOT substituted for the approved hub: doing so could expand
    coverage without a reviewed territory change. Coordinates already stored
    on legacy addresses remain usable, but are not represented as confirmed
    GPS/map pins until provenance is migrated in a later release.
    """
    # Additive address provenance (PR #247) is optional during rollout.
    # A legacy coordinate pair is usable under compatibility rules, but must
    # never be misrepresented as customer-confirmed GPS/map selection.
    source = getattr(address, "location_source", None)
    confirmed_at = getattr(address, "location_confirmed_at", None)
    has_coordinates = address.latitude is not None and address.longitude is not None
    if has_coordinates and source == "searched_place":
        # A provider result may be a road, locality, or village centroid.
        # Even a saved selection must not be called a confirmed doorstep pin.
        confidence = "approximate_searched_place"
    elif has_coordinates and source in {"gps", "map_pin"} and confirmed_at is not None:
        confidence = f"confirmed_{source}"
    elif has_coordinates:
        confidence = "legacy_coordinates"
    else:
        confidence = "unverified_manual"
    if merchant is None:
        merchant = db.get(Merchant, store.merchant_id)
    if not store.is_active or merchant is None or merchant.status != MerchantStatus.APPROVED:
        return _reject(store, address, "STORE_UNAVAILABLE", "Store is currently unavailable", confidence)
    if not store.delivery_enabled:
        return _reject(
            store, address, "STORE_DELIVERY_DISABLED",
            "This store does not currently support delivery", confidence,
        )
    if store.service_area_id is None:
        return _reject(
            store, address, "STORE_TERRITORY_MISSING",
            "Delivery coverage is not configured for this store", confidence,
        )
    area = db.get(ServiceArea, store.service_area_id)
    if area is None:
        return _reject(
            store, address, "SERVICEABILITY_CONFIGURATION_ERROR",
            "Delivery serviceability cannot be verified for this order", confidence,
        )
    if not area.is_active:
        return _reject(
            store, address, "TERRITORY_INACTIVE",
            "This store does not deliver to the selected address", confidence,
        )
    hub = db.get(Village, area.hub_village_id)
    if (
        hub is None or not hub.is_active
        or hub.latitude is None or hub.longitude is None
        or not isfinite(float(hub.latitude)) or not isfinite(float(hub.longitude))
        or not -90 <= float(hub.latitude) <= 90
        or not -180 <= float(hub.longitude) <= 180
        or not isfinite(float(area.radius_km)) or area.radius_km <= 0
    ):
        return _reject(
            store, address, "SERVICEABILITY_CONFIGURATION_ERROR",
            "Delivery serviceability cannot be verified for this order", confidence,
        )
    if address.latitude is None or address.longitude is None:
        # Never turn an unpinned landmark into a precise village-centre pin.
        return _reject(
            store, address, "ADDRESS_COORDINATES_MISSING",
            "Confirm your delivery location on the map before placing an order", confidence,
        )
    latitude, longitude = float(address.latitude), float(address.longitude)
    if (
        not isfinite(latitude) or not isfinite(longitude)
        or not -90 <= latitude <= 90 or not -180 <= longitude <= 180
    ):
        return _reject(
            store, address, "ADDRESS_LOCATION_UNCONFIRMED",
            "Confirm your delivery location on the map before placing an order", confidence,
        )
    # Explicitly sourced provider centroids are not confirmed doorstep pins.
    # Keep NULL-provenance historical coordinates usable for compatibility,
    # but never promote a new unconfirmed source to checkout eligibility.
    if source in {"gps", "map_pin", "searched_place"} and confidence not in {
        "confirmed_gps", "confirmed_map_pin",
    }:
        return _reject(
            store, address, "ADDRESS_LOCATION_UNCONFIRMED",
            "Confirm your delivery location on the map before placing an order",
            confidence,
        )
    if not point_is_in_service_area(db, area.id, latitude, longitude):
        return _reject(
            store, address, "ADDRESS_OUTSIDE_TERRITORY",
            "This store does not deliver to the selected address", confidence,
        )
    return DeliveryDecision(
        serviceable=True,
        reason_code="SERVICEABLE",
        human_readable_message="Delivery is available",
        store_id=store.id,
        address_id=address.id,
        matched_territory_id=area.id,
        location_confidence=confidence,
    )
