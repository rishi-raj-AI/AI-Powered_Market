from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.commerce import Store
from app.schemas.commerce import NearbyStoreRead, StoreRead
from app.services.spatial import nearby_store_distances

router = APIRouter(tags=["Commerce"])


@router.get("/stores/nearby", response_model=list[NearbyStoreRead])
def nearby_stores_postgis(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=15, gt=0, le=100),
    delivery: bool | None = None,
    db: Session = Depends(get_db),
):
    ranked = nearby_store_distances(db, lat, lng, radius_km, delivery)
    results: list[NearbyStoreRead] = []
    for store_id, distance_km in ranked:
        store = db.get(Store, store_id)
        if store is None:
            continue
        payload = StoreRead.model_validate(store).model_dump()
        results.append(NearbyStoreRead(**payload, distance_km=round(distance_km, 2)))
    return results
