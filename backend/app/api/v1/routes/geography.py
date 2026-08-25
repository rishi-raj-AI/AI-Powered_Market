import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.geography import Address, ServiceArea, Village
from app.models.user import User, UserRole
from app.schemas.geography import AddressCreate, AddressRead, ServiceAreaCreate, ServiceAreaRead, VillageCreate, VillageRead

router = APIRouter(tags=["Geography"])


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


@router.get("/addresses/me", response_model=list[AddressRead])
def list_my_addresses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Address).where(Address.user_id == user.id).order_by(Address.is_default.desc(), Address.created_at.desc())).all()


@router.post("/addresses/me", response_model=AddressRead, status_code=status.HTTP_201_CREATED)
def create_my_address(payload: AddressCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.get(Village, payload.village_id) is None:
        raise HTTPException(status_code=404, detail="Village not found")
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
