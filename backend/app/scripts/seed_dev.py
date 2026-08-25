from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.commerce import Category, Product
from app.models.geography import ServiceArea, Village
from app.models.user import User, UserRole

ADMIN_PHONE = "+919000000001"
DELIVERY_PHONE = "+919000000002"


def _ensure_user(db, phone: str, name: str, role: UserRole) -> User:
    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(phone=phone, full_name=name, role=role, is_active=True, is_verified=True)
        db.add(user)
    else:
        user.full_name = name
        user.role = role
        user.is_active = True
        user.is_verified = True
    return user


def main() -> None:
    if settings.APP_ENV == "production":
        raise RuntimeError("Development seed is disabled in production")

    db = SessionLocal()
    try:
        _ensure_user(db, ADMIN_PHONE, "GaonOne Dev Admin", UserRole.ADMIN)
        _ensure_user(db, DELIVERY_PHONE, "GaonOne Dev Rider", UserRole.DELIVERY)

        village = db.scalar(
            select(Village).where(
                Village.name == "Pilot Village",
                Village.district == "Pilot District",
                Village.state == "Maharashtra",
            )
        )
        if village is None:
            village = Village(
                name="Pilot Village",
                taluka="Pilot Taluka",
                district="Pilot District",
                state="Maharashtra",
                pincode="400001",
                latitude=18.5204,
                longitude=73.8567,
            )
            db.add(village)
            db.flush()

        area = db.scalar(select(ServiceArea).where(ServiceArea.name == "Pilot Cluster"))
        if area is None:
            db.add(ServiceArea(name="Pilot Cluster", hub_village_id=village.id, radius_km=12.0))

        category_specs = [
            ("Groceries", "groceries"),
            ("Food & Restaurants", "food-restaurants"),
            ("Vegetables & Fruits", "vegetables-fruits"),
            ("Daily Essentials", "daily-essentials"),
        ]
        categories: dict[str, Category] = {}
        for name, slug in category_specs:
            category = db.scalar(select(Category).where(Category.slug == slug))
            if category is None:
                category = Category(name=name, slug=slug)
                db.add(category)
                db.flush()
            categories[slug] = category

        product_specs = [
            ("groceries", "Rice", None, "1 kg"),
            ("groceries", "Wheat Flour", None, "1 kg"),
            ("daily-essentials", "Milk", None, "500 ml"),
            ("vegetables-fruits", "Onion", None, "1 kg"),
            ("vegetables-fruits", "Tomato", None, "1 kg"),
        ]
        for category_slug, name, brand, unit in product_specs:
            exists = db.scalar(
                select(Product).where(
                    Product.category_id == categories[category_slug].id,
                    Product.name == name,
                )
            )
            if exists is None:
                db.add(Product(category_id=categories[category_slug].id, name=name, brand=brand, unit=unit))

        db.commit()
        print("Development seed complete")
        print(f"Admin: {ADMIN_PHONE} / OTP 123456")
        print(f"Delivery: {DELIVERY_PHONE} / OTP 123456")
        print(f"Pilot village id: {village.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
