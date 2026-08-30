"""P1-5 and P1-7: address lifecycle, and a store must sit in the area it serves.

Deleting an address that any order referenced raised a foreign-key violation
and reached the customer as an unhandled 500. Separately, store creation only
checked that the supplied service_area_id existed — never that the store was
inside it — while checkout validates the *customer* address against that area.
A merchant could therefore attach a store anywhere and serve every address in
that area.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.geography import Address
from app.models.orders import Order
from tests.factories import (
    make_address,
    make_order,
    make_service_area,
    make_user,
    make_village,
    session,
)

client = TestClient(app)
OTP = "123456"


def token_for(phone: str) -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------- addresses


def test_deleting_an_address_used_by_an_order_succeeds_instead_of_500() -> None:
    from app.models.user import User

    with session() as db:
        order = make_order(db)
        db.commit()
        address_id, order_id = order.address_id, order.id
        user_phone = db.get(User, order.user_id).phone

    response = client.delete(
        f"/api/v1/addresses/me/{address_id}", headers=auth(token_for(user_phone))
    )
    assert response.status_code == 204, response.text

    with session() as db:
        address = db.get(Address, address_id)
        # Archived, not destroyed: the order still knows where it went.
        assert address is not None
        assert address.archived_at is not None
        assert db.get(Order, order_id) is not None


def test_archived_addresses_disappear_from_the_customers_list() -> None:
    with session() as db:
        user = make_user(db)
        village = make_village(db)
        keep = make_address(db, user, village)
        drop = make_address(db, user, village)
        db.commit()
        phone, keep_id, drop_id = user.phone, str(keep.id), str(drop.id)

    token = token_for(phone)
    assert client.delete(f"/api/v1/addresses/me/{drop_id}", headers=auth(token)).status_code == 204

    listed = {a["id"] for a in client.get("/api/v1/addresses/me", headers=auth(token)).json()}
    assert keep_id in listed
    assert drop_id not in listed


def test_an_archived_address_cannot_be_archived_twice() -> None:
    with session() as db:
        user = make_user(db)
        address = make_address(db, user, make_village(db))
        db.commit()
        phone, address_id = user.phone, str(address.id)

    token = token_for(phone)
    assert client.delete(f"/api/v1/addresses/me/{address_id}", headers=auth(token)).status_code == 204
    assert client.delete(f"/api/v1/addresses/me/{address_id}", headers=auth(token)).status_code == 404


def test_a_customer_cannot_archive_someone_elses_address() -> None:
    with session() as db:
        owner = make_user(db)
        intruder = make_user(db)
        address = make_address(db, owner, make_village(db))
        db.commit()
        intruder_phone, address_id = intruder.phone, str(address.id)

    response = client.delete(
        f"/api/v1/addresses/me/{address_id}", headers=auth(token_for(intruder_phone))
    )
    assert response.status_code == 404


def test_order_keeps_its_own_delivery_address_snapshot() -> None:
    """Order history must not describe wherever the address points today."""
    with session() as db:
        order = make_order(db)
        db.commit()
        order_id = order.id

    with session() as db:
        order = db.get(Order, order_id)
        # Orders created before snapshots existed are backfilled by the
        # migration; new ones snapshot at checkout.
        assert isinstance(order.delivery_address, dict)


# ------------------------------------------------------------ service areas


def test_store_cannot_be_attached_to_an_area_it_is_not_inside() -> None:
    with session() as db:
        village = make_village(db)
        area = make_service_area(db, village)  # hub at 18.5204, 73.8567, radius 15km
        db.commit()
        village_id, area_id = str(village.id), str(area.id)

    merchant_phone = f"+9188{abs(hash(area_id)) % 100000000:08d}"
    token = token_for(merchant_phone)
    applied = client.post(
        "/api/v1/merchants/apply",
        headers=auth(token),
        json={"business_name": "Far Away Traders", "gstin": None},
    )
    assert applied.status_code == 201, applied.text
    merchant_id = applied.json()["id"]
    approve = client.patch(
        f"/api/v1/merchants/{merchant_id}/approve", headers=auth(token_for("+919000000001"))
    )
    assert approve.status_code == 200, approve.text

    response = client.post(
        "/api/v1/stores",
        headers=auth(token),
        json={
            "village_id": village_id,
            "service_area_id": area_id,
            "name": "Far Away Store",
            "slug": f"far-away-{merchant_id[:8]}",
            "landmark": "Somewhere else entirely",
            # Delhi: ~1150 km from the Pune-area hub.
            "latitude": 28.6139,
            "longitude": 77.2090,
            "delivery_enabled": True,
            "pickup_enabled": True,
        },
    )
    assert response.status_code == 422, response.text
    assert "outside the selected service area" in response.json()["detail"]


def test_store_inside_its_area_is_accepted() -> None:
    with session() as db:
        village = make_village(db)
        area = make_service_area(db, village)
        db.commit()
        village_id, area_id = str(village.id), str(area.id)

    merchant_phone = f"+9187{abs(hash(village_id)) % 100000000:08d}"
    token = token_for(merchant_phone)
    applied = client.post(
        "/api/v1/merchants/apply",
        headers=auth(token),
        json={"business_name": "Local Traders", "gstin": None},
    )
    assert applied.status_code == 201, applied.text
    client.patch(
        f"/api/v1/merchants/{applied.json()['id']}/approve",
        headers=auth(token_for("+919000000001")),
    )

    response = client.post(
        "/api/v1/stores",
        headers=auth(token),
        json={
            "village_id": village_id,
            "service_area_id": area_id,
            "name": "Local Store",
            "slug": f"local-{applied.json()['id'][:8]}",
            "landmark": "Near the hub",
            "latitude": 18.5210,
            "longitude": 73.8570,
            "delivery_enabled": True,
            "pickup_enabled": True,
        },
    )
    assert response.status_code == 201, response.text


def test_service_area_requires_a_pinned_storefront() -> None:
    with session() as db:
        village = make_village(db)
        area = make_service_area(db, village)
        db.commit()
        village_id, area_id = str(village.id), str(area.id)

    merchant_phone = f"+9186{abs(hash(area_id + 'x')) % 100000000:08d}"
    token = token_for(merchant_phone)
    applied = client.post(
        "/api/v1/merchants/apply",
        headers=auth(token),
        json={"business_name": "Unpinned Traders", "gstin": None},
    )
    client.patch(
        f"/api/v1/merchants/{applied.json()['id']}/approve",
        headers=auth(token_for("+919000000001")),
    )

    response = client.post(
        "/api/v1/stores",
        headers=auth(token),
        json={
            "village_id": village_id,
            "service_area_id": area_id,
            "name": "Unpinned Store",
            "slug": f"unpinned-{applied.json()['id'][:8]}",
            "landmark": "No pin",
            "delivery_enabled": True,
            "pickup_enabled": True,
        },
    )
    assert response.status_code == 422
    assert "Pin the storefront" in response.json()["detail"]
