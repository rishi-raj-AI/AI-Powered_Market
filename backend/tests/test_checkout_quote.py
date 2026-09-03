from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.v1.routes import checkout
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.orders import Cart, CartItem
from tests import factories

client = TestClient(app)


def _quote_context():
    with SessionLocal() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        store.opens_at = None
        store.closes_at = None
        area = db.get(factories.ServiceArea, store.service_area_id)
        area.delivery_fee = Decimal("37.50")
        listing = factories.make_listing(db, store, price=Decimal("72.50"), stock=8)
        address = factories.make_address(db, customer, db.get(factories.Village, store.village_id))
        cart = Cart(user_id=customer.id, store_id=store.id)
        db.add(cart)
        db.flush()
        factories._track(cart)
        cart_item = CartItem(cart_id=cart.id, store_product_id=listing.id, quantity=2)
        db.add(cart_item)
        db.flush()
        factories._track(cart_item)
        db.commit()
        return customer.id, address.id, listing.id


def test_quote_uses_backend_area_fee_and_current_inventory(monkeypatch):
    customer_id, address_id, _ = _quote_context()
    monkeypatch.setattr(checkout, "point_is_in_service_area", lambda *args: True)
    response = client.get(
        "/api/v1/cart/quote",
        params={"address_id": str(address_id)},
        headers={"Authorization": f"Bearer {create_access_token(str(customer_id))}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["subtotal"] == "145.00"
    assert response.json()["delivery_fee"] == "37.50"
    assert response.json()["total"] == "182.50"
    assert response.json()["checkout_ready"] is True


def test_quote_blocks_changed_inventory(monkeypatch):
    customer_id, address_id, listing_id = _quote_context()
    monkeypatch.setattr(checkout, "point_is_in_service_area", lambda *args: True)
    with SessionLocal() as db:
        listing = db.get(factories.StoreProduct, listing_id)
        listing.stock_quantity = 1
        db.commit()
    response = client.get(
        "/api/v1/cart/quote",
        params={"address_id": str(address_id)},
        headers={"Authorization": f"Bearer {create_access_token(str(customer_id))}"},
    )
    assert response.status_code == 200
    assert response.json()["inventory_valid"] is False
    assert response.json()["checkout_ready"] is False
    assert "Cart inventory changed" in response.json()["blockers"][0]


def test_quote_does_not_expose_another_customers_address():
    customer_id, _, _ = _quote_context()
    with SessionLocal() as db:
        stranger = factories.make_user(db)
        village = factories.make_village(db)
        address = factories.make_address(db, stranger, village)
        db.commit()
        stranger_address_id = address.id
    response = client.get(
        "/api/v1/cart/quote",
        params={"address_id": str(stranger_address_id)},
        headers={"Authorization": f"Bearer {create_access_token(str(customer_id))}"},
    )
    assert response.status_code == 404
