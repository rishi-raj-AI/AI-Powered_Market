from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.v1.routes.substitutions import _substitution_score
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.orders import OrderItem
from tests import factories

client = TestClient(app)


def auth(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


def test_substitutions_only_offer_available_same_store_choices():
    with SessionLocal() as db:
        store = factories.make_store(db, is_active=True)
        base = factories.make_listing(db, store, price=Decimal("100.00"), stock=0)
        base.product.name = "Original Rice"
        base.product.brand = "Farm Brand"
        close = factories.make_listing(db, store, price=Decimal("105.00"), stock=4)
        close.product.name = "Alternative Rice"
        close.product.brand = "Farm Brand"
        unavailable = factories.make_listing(db, store, price=Decimal("99.00"), stock=0)
        unavailable.product.name = "Unavailable Rice"
        db.commit()
        base_id = base.id
        close_id = close.id

    response = client.get(f"/api/v1/store-products/{base_id}/substitutions")
    assert response.status_code == 200, response.text
    assert [item["listing_id"] for item in response.json()] == [str(close_id)]
    assert response.json()[0]["name"] == "Alternative Rice"


def test_substitution_score_prefers_close_same_brand_choice():
    base = Decimal("100.00")
    assert _substitution_score(base, Decimal("105.00"), True) > _substitution_score(
        base, Decimal("105.00"), False
    )


def test_reorder_preview_uses_current_price_and_clamps_to_stock():
    with SessionLocal() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        order = factories.make_order(db, customer=customer, store=store)
        item = db.query(OrderItem).filter(OrderItem.order_id == order.id).one()
        listing = db.query(factories.StoreProduct).filter(
            factories.StoreProduct.store_id == store.id,
            factories.StoreProduct.product_id == item.product_id,
        ).one()
        item.quantity = 5
        listing.stock_quantity = 2
        listing.price = Decimal("123.00")
        db.commit()
        customer_id = customer.id
        order_id = order.id

    response = client.get(
        f"/api/v1/orders/{order_id}/reorder-preview", headers=auth(customer_id)
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["items"][0]["requested_quantity"] == 5
    assert result["items"][0]["available_quantity"] == 2
    assert result["items"][0]["current_unit_price"] == "123.00"
    assert result["estimated_subtotal"] == "246.00"


def test_reorder_preview_hides_another_customers_order():
    with SessionLocal() as db:
        owner = factories.make_user(db)
        stranger = factories.make_user(db)
        order = factories.make_order(db, customer=owner)
        db.commit()
        order_id = order.id
        stranger_id = stranger.id
    response = client.get(
        f"/api/v1/orders/{order_id}/reorder-preview", headers=auth(stranger_id)
    )
    assert response.status_code == 404
