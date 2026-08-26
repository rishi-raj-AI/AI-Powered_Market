from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.commerce import Category, Merchant, MerchantStatus, Product, Store, StoreProduct
from app.models.geography import ServiceArea, Village
from app.models.user import User, UserRole

ADMIN_PHONE = "+919000000001"
DELIVERY_PHONE = "+919000000002"
MERCHANT_PHONE = "+919000000003"


def _ensure_user(db, phone: str, name: str, role: UserRole) -> User:
    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(phone=phone, full_name=name, role=role, is_active=True, is_verified=True)
        db.add(user)
        db.flush()
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
        merchant_user = _ensure_user(db, MERCHANT_PHONE, "Patil Kirana Owner", UserRole.MERCHANT)

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
            area = ServiceArea(name="Pilot Cluster", hub_village_id=village.id, radius_km=12.0)
            db.add(area)
            db.flush()

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
            ("groceries", "Rice", None, "1 kg", Decimal("62.00"), Decimal("70.00"), 40),
            ("groceries", "Wheat Flour", None, "1 kg", Decimal("48.00"), Decimal("55.00"), 35),
            ("daily-essentials", "Milk", "Local Dairy", "500 ml", Decimal("30.00"), Decimal("30.00"), 25),
            ("vegetables-fruits", "Onion", None, "1 kg", Decimal("38.00"), Decimal("42.00"), 28),
            ("vegetables-fruits", "Tomato", None, "1 kg", Decimal("44.00"), Decimal("50.00"), 22),
        ]
        products: dict[str, Product] = {}
        listing_specs: dict[str, tuple[Decimal, Decimal, int]] = {}
        for category_slug, name, brand, unit, price, mrp, stock in product_specs:
            product = db.scalar(
                select(Product).where(
                    Product.category_id == categories[category_slug].id,
                    Product.name == name,
                )
            )
            if product is None:
                product = Product(category_id=categories[category_slug].id, name=name, brand=brand, unit=unit)
                db.add(product)
                db.flush()
            products[name] = product
            listing_specs[name] = (price, mrp, stock)

        merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == merchant_user.id))
        if merchant is None:
            merchant = Merchant(
                owner_user_id=merchant_user.id,
                business_name="Patil Kirana & Daily Needs",
                status=MerchantStatus.APPROVED,
            )
            db.add(merchant)
            db.flush()
        else:
            merchant.business_name = "Patil Kirana & Daily Needs"
            merchant.status = MerchantStatus.APPROVED

        store = db.scalar(select(Store).where(Store.slug == "patil-kirana-pilot"))
        if store is None:
            store = Store(
                merchant_id=merchant.id,
                village_id=village.id,
                service_area_id=area.id,
                name="Patil Kirana & Daily Needs",
                slug="patil-kirana-pilot",
                description="Groceries, milk and everyday essentials from the local village market.",
                phone=MERCHANT_PHONE,
                landmark="Near Gram Panchayat, Main Chowk",
                latitude=18.5204,
                longitude=73.8567,
                delivery_enabled=True,
                pickup_enabled=True,
                is_active=True,
            )
            db.add(store)
            db.flush()

        for name, product in products.items():
            price, mrp, stock = listing_specs[name]
            listing = db.scalar(
                select(StoreProduct).where(
                    StoreProduct.store_id == store.id,
                    StoreProduct.product_id == product.id,
                )
            )
            if listing is None:
                db.add(
                    StoreProduct(
                        store_id=store.id,
                        product_id=product.id,
                        price=price,
                        mrp=mrp,
                        stock_quantity=stock,
                        is_available=True,
                    )
                )
            else:
                listing.price = price
                listing.mrp = mrp
                listing.stock_quantity = max(listing.stock_quantity, stock)
                listing.is_available = True

        db.commit()
        print("Development seed complete")
        print(f"Admin: {ADMIN_PHONE} / OTP 123456")
        print(f"Delivery: {DELIVERY_PHONE} / OTP 123456")
        print(f"Merchant: {MERCHANT_PHONE} / OTP 123456")
        print(f"Pilot village id: {village.id}")
        print(f"Demo store: {store.name} ({store.slug})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
