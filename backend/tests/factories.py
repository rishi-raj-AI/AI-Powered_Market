"""Database factories for integration tests.

These build real rows through the application's own session so tests exercise
the same constraints, defaults and transaction semantics production does.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.commerce import (
    Category,
    Merchant,
    MerchantStatus,
    Product,
    Store,
    StoreProduct,
)
from app.models.geography import Address, ServiceArea, Village
from app.models.integrations import PaymentAttempt
from app.models.orders import (
    Delivery,
    DeliveryStatus,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)
from app.models.user import User, UserRole


#: Rows created by these factories, newest first, so they can be removed again.
_TRACKED: list[tuple[type, uuid.UUID]] = []


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _track(instance):
    _TRACKED.append((type(instance), instance.id))
    return instance


def reset_tracking() -> None:
    _TRACKED.clear()


def cleanup_tracked() -> None:
    """Delete tracked rows in reverse creation order so foreign keys hold."""
    if not _TRACKED:
        return
    tracked = list(reversed(_TRACKED))
    _TRACKED.clear()
    from app.models.integrations import CodCollection, PaymentRefund, SettlementEntry
    from app.models.orders import DeliveryLocation, DeliveryProof, StatusTransitionEvent

    with SessionLocal() as db:
        order_ids = [row_id for model, row_id in tracked if model is Order]
        delivery_ids = [
            row_id
            for row_id in db.scalars(
                select(Delivery.id).where(Delivery.order_id.in_(order_ids))
            ).all()
        ] if order_ids else []
        if delivery_ids:
            for model in (DeliveryLocation, DeliveryProof, CodCollection):
                db.query(model).filter(model.delivery_id.in_(delivery_ids)).delete(
                    synchronize_session=False
                )
        if order_ids:
            for model in (StatusTransitionEvent, PaymentRefund, PaymentAttempt, SettlementEntry, OrderItem):
                db.query(model).filter(model.order_id.in_(order_ids)).delete(
                    synchronize_session=False
                )
            db.query(Delivery).filter(Delivery.order_id.in_(order_ids)).delete(
                synchronize_session=False
            )
        db.commit()
        for model, row_id in tracked:
            try:
                instance = db.get(model, row_id)
                if instance is not None:
                    db.delete(instance)
                    db.commit()
            except Exception:  # noqa: BLE001 - best-effort teardown
                db.rollback()


def make_user(db, *, role: UserRole = UserRole.CUSTOMER, prefix: str = "7") -> User:
    numeric = int(_suffix()[:8], 16) % 1_000_000_000
    user = User(
        phone=f"+91{prefix}{numeric:09d}"[:15],
        full_name=f"Test {role.value} {_suffix()[:4]}",
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    _track(user)
    return user


def make_village(db) -> Village:
    village = Village(
        name=f"Test Area {_suffix()[:6]}",
        district=f"District {_suffix()[:6]}",
        state="Maharashtra",
        pincode="413001",
        latitude=18.5204,
        longitude=73.8567,
        is_active=True,
    )
    db.add(village)
    db.flush()
    _track(village)
    return village


def make_service_area(db, village: Village) -> ServiceArea:
    area = ServiceArea(
        name=f"Cluster {_suffix()[:6]}",
        hub_village_id=village.id,
        radius_km=15.0,
        is_active=True,
    )
    db.add(area)
    db.flush()
    _track(area)
    return area


def make_store(
    db,
    *,
    owner: User | None = None,
    village: Village | None = None,
    service_area: ServiceArea | None = None,
    opens_at: time | None = None,
    closes_at: time | None = None,
    latitude: float = 18.5204,
    longitude: float = 73.8567,
    is_active: bool = False,
) -> Store:
    # Factory stores stay out of public discovery unless a test explicitly wants
    # them there, so fixtures for one test can never alter another test's
    # store listing on the shared database.
    owner = owner or make_user(db, role=UserRole.MERCHANT, prefix="8")
    village = village or make_village(db)
    service_area = service_area or make_service_area(db, village)
    merchant = Merchant(
        owner_user_id=owner.id,
        business_name=f"Test Traders {_suffix()[:6]}",
        status=MerchantStatus.APPROVED,
    )
    db.add(merchant)
    db.flush()
    _track(merchant)
    store = Store(
        merchant_id=merchant.id,
        village_id=village.id,
        service_area_id=service_area.id,
        name=f"Test Store {_suffix()[:6]}",
        slug=f"test-store-{_suffix()}",
        landmark="Beside the bus stand",
        latitude=latitude,
        longitude=longitude,
        opens_at=opens_at,
        closes_at=closes_at,
        delivery_enabled=True,
        pickup_enabled=True,
        is_active=is_active,
    )
    db.add(store)
    db.flush()
    _track(store)
    return store


def make_listing(db, store: Store, *, price: Decimal = Decimal("100.00"), stock: int = 10) -> StoreProduct:
    category = db.scalar(select(Category).where(Category.slug == "test-category"))
    if category is None:
        category = Category(name="Test Category", slug="test-category", is_active=True)
        db.add(category)
        db.flush()
    product = Product(
        category_id=category.id,
        name=f"Test Product {_suffix()[:6]}",
        unit="1 kg",
        is_active=True,
    )
    db.add(product)
    db.flush()
    _track(product)
    listing = StoreProduct(
        store_id=store.id,
        product_id=product.id,
        price=price,
        stock_quantity=stock,
        is_available=True,
    )
    db.add(listing)
    db.flush()
    _track(listing)
    return listing


def make_address(db, user: User, village: Village) -> Address:
    address = Address(
        user_id=user.id,
        village_id=village.id,
        label="Home",
        recipient_name="Test Recipient",
        phone="+919000000009",
        house_details="House 12",
        landmark="Near the temple",
        latitude=18.5204,
        longitude=73.8567,
    )
    db.add(address)
    db.flush()
    _track(address)
    return address


def make_order(
    db,
    *,
    customer: User | None = None,
    store: Store | None = None,
    payment_method: PaymentMethod = PaymentMethod.UPI,
    payment_status: PaymentStatus = PaymentStatus.PAID,
    status: OrderStatus = OrderStatus.PLACED,
    total: Decimal = Decimal("120.00"),
    with_paid_attempt: bool = True,
    with_delivery: bool = False,
) -> Order:
    customer = customer or make_user(db)
    if store is None:
        store = make_store(db)
    village = db.get(Village, store.village_id)
    address = make_address(db, customer, village)
    listing = make_listing(db, store)
    subtotal = total - Decimal("20.00")
    order = Order(
        order_number=f"GO{_suffix().upper()[:12]}",
        user_id=customer.id,
        store_id=store.id,
        address_id=address.id,
        status=status,
        payment_method=payment_method,
        payment_status=payment_status,
        subtotal=subtotal,
        delivery_fee=Decimal("20.00"),
        total=total,
    )
    db.add(order)
    db.flush()
    _track(order)
    db.add(
        OrderItem(
            order_id=order.id,
            product_id=listing.product_id,
            product_name="Test Product",
            unit="1 kg",
            unit_price=subtotal,
            quantity=1,
            line_total=subtotal,
        )
    )
    if with_delivery:
        db.add(Delivery(order_id=order.id, status=DeliveryStatus.UNASSIGNED))
    if with_paid_attempt and payment_method == PaymentMethod.UPI:
        db.add(
            PaymentAttempt(
                order_id=order.id,
                provider="razorpay",
                provider_order_id=f"order_{_suffix()}{_suffix()}",
                provider_payment_id=f"pay_{_suffix()}{_suffix()}",
                status="paid",
                amount=total,
                currency="INR",
                updated_at=datetime.now(timezone.utc),
            )
        )
    db.flush()
    return order


def session():
    return SessionLocal()
