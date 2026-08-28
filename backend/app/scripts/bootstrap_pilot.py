from __future__ import annotations

import os

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.commerce import Category, Product
from app.models.geography import ServiceArea, Village
from app.models.user import User, UserRole


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _optional_float(name: str) -> float | None:
    raw = os.getenv(name, "").strip()
    return float(raw) if raw else None


def _ensure_user(db, phone: str, full_name: str, role: UserRole) -> User:
    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(
            phone=phone,
            full_name=full_name,
            role=role,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.flush()
    else:
        user.full_name = full_name
        user.role = role
        user.is_active = True
        user.is_verified = True
    return user


def _seed_catalog(db, categories: dict[str, Category]) -> tuple[int, int]:
    catalog = {
        "groceries": [
            ("Rice", "1 kg"), ("Wheat Flour (Atta)", "1 kg"), ("Toor Dal", "1 kg"),
            ("Moong Dal", "1 kg"), ("Chana Dal", "1 kg"), ("Sugar", "1 kg"),
            ("Salt", "1 kg"), ("Cooking Oil", "1 L"), ("Tea", "250 g"),
            ("Poha", "500 g"), ("Besan", "500 g"), ("Jaggery", "500 g"),
        ],
        "vegetables-fruits": [
            ("Onion", "1 kg"), ("Potato", "1 kg"), ("Tomato", "1 kg"),
            ("Green Chilli", "250 g"), ("Coriander", "1 bunch"), ("Lemon", "6 pcs"),
            ("Banana", "6 pcs"), ("Apple", "1 kg"),
        ],
        "daily-essentials": [
            ("Milk", "500 ml"), ("Curd", "500 g"), ("Bread", "1 pack"),
            ("Bath Soap", "1 pc"), ("Detergent Powder", "1 kg"), ("Dishwash Bar", "1 pc"),
            ("Toothpaste", "150 g"), ("Matchbox", "1 pack"),
        ],
        "food-restaurants": [
            ("Veg Thali", "1 plate"), ("Chapati", "1 pc"), ("Dal Rice", "1 plate"),
            ("Poha Prepared", "1 plate"), ("Tea Prepared", "1 cup"),
        ],
        "pharmacy-health": [
            ("ORS Sachet", "1 sachet"), ("Cotton Roll", "1 pc"),
            ("Antiseptic Liquid", "100 ml"), ("Bandage Roll", "1 pc"),
        ],
        "home-local-services": [
            ("Drinking Water Can", "20 L"), ("LPG Delivery Assistance", "1 service"),
        ],
    }
    created = 0
    total = sum(len(items) for items in catalog.values())
    for slug, items in catalog.items():
        category = categories[slug]
        for name, unit in items:
            product = db.scalar(
                select(Product).where(
                    Product.category_id == category.id,
                    Product.name == name,
                    Product.unit == unit,
                )
            )
            if product is None:
                db.add(Product(
                    category_id=category.id,
                    name=name,
                    unit=unit,
                    description="GaonOne starter catalogue item. Merchant controls price, stock and availability.",
                    brand=None,
                    image_url=None,
                    is_active=True,
                ))
                created += 1
            else:
                product.is_active = True
    return created, total


def main() -> None:
    if settings.APP_ENV != "production":
        raise RuntimeError("Pilot bootstrap is production-only; use seed_dev in development")

    admin_phone = _required("PILOT_ADMIN_PHONE")
    admin_name = _required("PILOT_ADMIN_NAME")
    village_name = _required("PILOT_VILLAGE_NAME")
    village_district = _required("PILOT_VILLAGE_DISTRICT")
    village_state = _required("PILOT_VILLAGE_STATE")
    village_taluka = os.getenv("PILOT_VILLAGE_TALUKA", "").strip() or None
    village_pincode = os.getenv("PILOT_VILLAGE_PINCODE", "").strip() or None
    latitude = _optional_float("PILOT_VILLAGE_LATITUDE")
    longitude = _optional_float("PILOT_VILLAGE_LONGITUDE")
    cluster_name = os.getenv("PILOT_CLUSTER_NAME", "GaonOne Pilot Cluster").strip()
    radius_km = float(os.getenv("PILOT_RADIUS_KM", "12"))

    db = SessionLocal()
    try:
        admin = _ensure_user(db, admin_phone, admin_name, UserRole.ADMIN)
        admin.is_super_admin = True

        rider_phone = os.getenv("PILOT_DELIVERY_PHONE", "").strip()
        rider_name = os.getenv("PILOT_DELIVERY_NAME", "GaonOne Pilot Rider").strip()
        rider = None
        if rider_phone:
            rider = _ensure_user(db, rider_phone, rider_name, UserRole.DELIVERY)

        village = db.scalar(
            select(Village).where(
                Village.name == village_name,
                Village.district == village_district,
                Village.state == village_state,
            )
        )
        if village is None:
            village = Village(
                name=village_name,
                taluka=village_taluka,
                district=village_district,
                state=village_state,
                pincode=village_pincode,
                latitude=latitude,
                longitude=longitude,
                is_active=True,
            )
            db.add(village)
            db.flush()
        else:
            village.taluka = village_taluka
            village.pincode = village_pincode
            village.latitude = latitude
            village.longitude = longitude
            village.is_active = True

        area = db.scalar(
            select(ServiceArea).where(
                ServiceArea.name == cluster_name,
                ServiceArea.hub_village_id == village.id,
            )
        )
        if area is None:
            area = ServiceArea(
                name=cluster_name,
                hub_village_id=village.id,
                radius_km=radius_km,
                is_active=True,
            )
            db.add(area)
        else:
            area.radius_km = radius_km
            area.is_active = True

        category_specs = (
            ("Groceries", "groceries"),
            ("Food & Restaurants", "food-restaurants"),
            ("Vegetables & Fruits", "vegetables-fruits"),
            ("Daily Essentials", "daily-essentials"),
            ("Pharmacy & Health", "pharmacy-health"),
            ("Home & Local Services", "home-local-services"),
        )
        categories: dict[str, Category] = {}
        for name, slug in category_specs:
            category = db.scalar(select(Category).where(Category.slug == slug))
            if category is None:
                category = Category(name=name, slug=slug, is_active=True)
                db.add(category)
                db.flush()
            else:
                category.name = name
                category.is_active = True
            categories[slug] = category

        catalog_created, catalog_total = _seed_catalog(db, categories)
        db.commit()

        print("GaonOne production pilot bootstrap complete")
        print(f"Super Admin user: {admin.phone} ({admin.id})")
        if rider is not None:
            print(f"Delivery user: {rider.phone} ({rider.id})")
        print(f"Pilot village: {village.name} ({village.id})")
        print(f"Service cluster: {cluster_name} / {radius_km:g} km")
        print(f"Starter catalogue: {catalog_total} generic items ({catalog_created} newly created)")
        print("No merchant/store demo data was created in production.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
