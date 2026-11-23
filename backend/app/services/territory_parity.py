"""Read-only comparison of legacy and published territory *geography*.

This is an administrative migration aid, not a checkout decision. It takes an
explicit test point, never loads a customer address, and never logs or returns
coordinates. Address provenance, inventory, capacity and payment are out of
scope. Legacy serviceability remains authoritative for all orders.
"""
from dataclasses import dataclass
from math import isfinite
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.commerce import Merchant, MerchantStatus, Store
from app.models.geography import ServiceArea, Village
from app.services.spatial import point_is_in_service_area
from app.services.territory_preview import match_active_store_territory


@dataclass(frozen=True)
class GeographyParity:
    store_id: UUID
    legacy_geographic_match: bool | None
    territory_geographic_match: bool
    parity_status: str
    legacy_configuration_issue: str | None = None
    territory_id: UUID | None = None
    checkout_authoritative: bool = False
    activation_authorized: bool = False


def _valid_coordinates(latitude: float, longitude: float) -> bool:
    return (
        isfinite(latitude) and isfinite(longitude)
        and -90 <= latitude <= 90 and -180 <= longitude <= 180
    )


def compare_store_geography(
    db: Session, store_id: UUID, latitude: float, longitude: float,
) -> GeographyParity | None:
    """Compare two independent geographies without granting delivery access.

    A missing/invalid legacy configuration is *not* treated as a negative
    geographic match: that would produce a misleading TERRITORY_ONLY result.
    A published draft does not match the active-only preview; draft impact
    analysis will require a separate, explicitly reviewed implementation.
    """
    if not _valid_coordinates(latitude, longitude):
        raise ValueError("Location coordinates are invalid")

    store = db.get(Store, store_id)
    if store is None:
        return None

    territory = match_active_store_territory(db, store_id, latitude, longitude)
    territory_match = territory is not None

    def incomparable(reason: str) -> GeographyParity:
        return GeographyParity(
            store_id=store_id, legacy_geographic_match=None,
            territory_geographic_match=territory_match,
            parity_status="NOT_COMPARABLE",
            legacy_configuration_issue=reason,
            territory_id=territory.territory_id if territory else None,
        )

    merchant = db.get(Merchant, store.merchant_id)
    if not store.is_active or merchant is None or merchant.status != MerchantStatus.APPROVED:
        return incomparable("STORE_UNAVAILABLE")
    if not store.delivery_enabled:
        return incomparable("STORE_DELIVERY_DISABLED")
    if store.service_area_id is None:
        return incomparable("LEGACY_AREA_MISSING")

    area = db.get(ServiceArea, store.service_area_id)
    if area is None or not area.is_active:
        return incomparable("LEGACY_AREA_INACTIVE_OR_MISSING")
    hub = db.get(Village, area.hub_village_id)
    if (
        hub is None or not hub.is_active
        or hub.latitude is None or hub.longitude is None
        or not _valid_coordinates(float(hub.latitude), float(hub.longitude))
        or not isfinite(float(area.radius_km)) or area.radius_km <= 0
    ):
        return incomparable("LEGACY_AREA_INVALID")

    legacy_match = point_is_in_service_area(db, area.id, latitude, longitude)
    status = (
        "MATCH_BOTH" if legacy_match and territory_match else
        "LEGACY_ONLY" if legacy_match else
        "TERRITORY_ONLY" if territory_match else "NEITHER"
    )
    return GeographyParity(
        store_id=store_id,
        legacy_geographic_match=legacy_match,
        territory_geographic_match=territory_match,
        parity_status=status,
        territory_id=territory.territory_id if territory else None,
    )
