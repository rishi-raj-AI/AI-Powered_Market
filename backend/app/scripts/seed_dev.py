from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.commerce import Category, Product
from app.models.geography import ServiceArea, Village
from app.models.user import User, UserRole

ADMIN_PHONE = "+919000000001"


def main() -> None:
    if settings.APP_ENV == "production":
        raise RuntimeError("Development seed is disabled in production")

    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.phone == ADMIN_PHONE))
        if admin is None:
            admin = User(
                phone=ADMIN_PHONE,
                full_name="GaonOne Dev Admin",
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.add(admin)
        else:
            admin.role = UserRole.ADMIN
            admin.is_active = True
            admin.is_verified = True

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
                db.add(
                    Product(
                        category_id=categories[category_slug].id,
                        name=name,
                        brand=brand,
                        unit=unit,
                    )
                )

        db.commit()
        print("Development seed complete")
        print(f"Admin phone: {ADMIN_PHONE}")
        print("OTP: 123456")
        print(f"Pilot village id: {village.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
