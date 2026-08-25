# GaonOne Backend Phase 1

Phase 1 delivers the first end-to-end marketplace backend slice.

## Included

- Phone-first OTP authentication and JWT access tokens
- Customer, merchant, delivery and admin roles
- Villages, service areas and landmark-first rural addresses
- Merchant applications and admin approval
- Stores and service-area mapping
- Categories, products, store pricing and inventory
- Customer cart restricted to one store per checkout
- Inventory validation during checkout
- COD/UPI-ready order records
- Merchant order lifecycle: placed -> accepted -> preparing -> ready
- Delivery lifecycle: unassigned -> assigned -> picked up -> delivered
- Development seed users and pilot catalogue

## Local validation

```bash
git pull origin main
docker compose down
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api alembic current
docker compose exec api python -m app.scripts.seed_dev
```

Expected Alembic head:

```text
0003_orders_delivery (head)
```

Expected seed output includes:

```text
Development seed complete
Admin: +919000000001 / OTP 123456
Delivery: +919000000002 / OTP 123456
```

Open Swagger:

```text
http://localhost:8000/docs
```

## Development accounts

All development accounts use OTP `123456` while `APP_ENV` is not `production`.

- Admin: `+919000000001`
- Delivery partner: `+919000000002`
- Customer: create any valid phone through `/auth/verify-otp`
- Merchant: create a customer, then call `/merchants/apply`; approve it using an admin token

## Recommended smoke flow

1. Login as admin.
2. Confirm `/villages`, `/service-areas`, `/categories`, and `/products` return seed data.
3. Create a new customer and add an address for the pilot village.
4. Create another user and submit `/merchants/apply`.
5. Approve the merchant from the admin account.
6. Login as the merchant and create a store.
7. Add one or more global products to the store with prices and stock.
8. Login as the customer, add a store product to `/cart/items`, and checkout.
9. Login as the merchant and move the order through accepted -> preparing -> ready.
10. Login as the delivery account, claim the available delivery, mark it picked up, then delivered.
11. Confirm the customer order is now `delivered`.

## Production integrations intentionally deferred

The core contracts exist, but these external services should be connected after the local transaction flow is validated:

- Real SMS/OTP provider
- Razorpay/UPI payment capture and webhooks
- Maps/geocoding provider
- Push notifications
- Object storage for store/product images
- Production observability and secrets management
