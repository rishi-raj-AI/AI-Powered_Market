from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from sqlalchemy import select

from app.api.deps import get_db
from app.models.commerce import Store
from app.schemas.commerce import NearbyStoreRead, StoreRead
from app.services.spatial import nearby_store_distances
from app.services.store_hours import store_is_open

router = APIRouter(tags=["Commerce"])


@router.get("/stores/nearby", response_model=list[NearbyStoreRead])
def nearby_stores_postgis(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=15, gt=0, le=100),
    delivery: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    ranked = nearby_store_distances(db, lat, lng, radius_km, delivery)[:limit]
    if not ranked:
        return []
    # One query for the page of stores instead of a fetch per ranked row.
    store_ids = [store_id for store_id, _ in ranked]
    by_id = {
        store.id: store
        for store in db.scalars(select(Store).where(Store.id.in_(store_ids))).all()
    }
    results: list[NearbyStoreRead] = []
    for store_id, distance_km in ranked:
        store = by_id.get(store_id)
        if store is None:
            continue
        payload = StoreRead.model_validate(store).model_dump()
        payload["is_open_now"] = store_is_open(store)
        results.append(NearbyStoreRead(**payload, distance_km=round(distance_km, 2)))
    return results
