import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.geography import Address, ServiceArea, Village
from app.models.user import User, UserRole
from app.schemas.geography import AddressCreate, AddressRead, PlaceDetailsRead, PlaceSuggestion, ReverseGeocodeRead, ServiceAreaCreate, ServiceAreaRead, ServiceabilityRead, VillageCreate, VillageRead
from app.services.places import PlacesUnavailable, autocomplete, place_details, reverse_geocode
from app.services.rate_limit import RateLimitExceeded, RateLimitUnavailable, rate_limiter
from app.services.spatial import serviceability_for_point

router = APIRouter(tags=["Geography"])


def _serviceability(db: Session, latitude: float, longitude: float) -> ServiceabilityRead:
    best = serviceability_for_point(db, latitude, longitude)
    if best is None:
        return ServiceabilityRead(serviceable=False)
    distance_km = float(best["distance_km"])
    radius_km = float(best["radius_km"])
    return ServiceabilityRead(
        serviceable=distance_km <= radius_km,
        service_area_id=best["id"],
        service_area_name=best["name"],
        distance_km=round(distance_km, 2),
        radius_km=radius_km,
    )


def _limit_provider(user: User, scope: str, limit: int) -> None:
    try:
        rate_limiter.enforce(scope, str(user.id), limit=limit, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except RateLimitUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/villages", response_model=list[VillageRead])
def list_villages(q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Village).where(Village.is_active.is_(True)).order_by(Village.name)
    if q:
        stmt = stmt.where(Village.name.ilike(f"%{q}%"))
    return db.scalars(stmt).all()


@router.post("/villages", response_model=VillageRead, status_code=status.HTTP_201_CREATED)
def create_village(payload: VillageCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN))):
    village = Village(**payload.model_dump())
    db.add(village)
    db.commit()
    db.refresh(village)
    return village


@router.get("/service-areas", response_model=list[ServiceAreaRead])
def list_service_areas(db: Session = Depends(get_db)):
    return db.scalars(select(ServiceArea).where(ServiceArea.is_active.is_(True)).order_by(ServiceArea.name)).all()


@router.post("/service-areas", response_model=ServiceAreaRead, status_code=status.HTTP_201_CREATED)
def create_service_area(payload: ServiceAreaCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN))):
    if db.get(Village, payload.hub_village_id) is None:
        raise HTTPException(status_code=404, detail="Hub village not found")
    area = ServiceArea(**payload.model_dump())
    db.add(area)
    db.commit()
    db.refresh(area)
    return area


@router.get("/location/autocomplete", response_model=list[PlaceSuggestion])
def location_autocomplete(q: str = Query(min_length=2, max_length=160), latitude: float | None = None, longitude: float | None = None, session_token: str | None = None, user: User = Depends(get_current_user)):
    _limit_provider(user, "maps-autocomplete", 60)
    try:
        return autocomplete(q, latitude, longitude, session_token)
    except PlacesUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Address search provider unavailable") from exc


@router.get("/location/place/{place_id}", response_model=PlaceDetailsRead)
def location_place(place_id: str, session_token: str | None = None, user: User = Depends(get_current_user)):
    _limit_provider(user, "maps-place-details", 30)
    try:
        return place_details(place_id, session_token)
    except PlacesUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Place details provider unavailable") from exc


@router.get("/location/reverse", response_model=ReverseGeocodeRead | None)
def location_reverse(latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180), user: User = Depends(get_current_user)):
    _limit_provider(user, "maps-reverse", 30)
    try:
        return reverse_geocode(latitude, longitude)
    except PlacesUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Reverse geocoding provider unavailable") from exc


@router.get("/location/serviceability", response_model=ServiceabilityRead)
def location_serviceability(latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180), db: Session = Depends(get_db)):
    return _serviceability(db, latitude, longitude)


@router.get("/addresses/me", response_model=list[AddressRead])
def list_my_addresses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Address).where(Address.user_id == user.id).order_by(Address.is_default.desc(), Address.created_at.desc())).all()


@router.post("/addresses/me", response_model=AddressRead, status_code=status.HTTP_201_CREATED)
def create_my_address(payload: AddressCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    village = db.get(Village, payload.village_id)
    if village is None:
        raise HTTPException(status_code=404, detail="Village not found")
    if (payload.latitude is None) != (payload.longitude is None):
        raise HTTPException(status_code=422, detail="Latitude and longitude must be supplied together")
    if payload.latitude is not None and payload.longitude is not None:
        coverage = _serviceability(db, payload.latitude, payload.longitude)
        if not coverage.serviceable:
            raise HTTPException(status_code=422, detail="Delivery address is outside the active GaonOne service area")
    if payload.is_default:
        db.execute(update(Address).where(Address.user_id == user.id).values(is_default=False))
    address = Address(user_id=user.id, **payload.model_dump())
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.delete("/addresses/me/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_address(address_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    address = db.get(Address, address_id)
    if address is None or address.user_id != user.id:
        raise HTTPException(status_code=404, detail="Address not found")
    db.delete(address)
    db.commit()
