# P0 scoped checkout serviceability diagnosis — integration branch

This tool is ported from geography PR #244 onto the combined payment,
geography and draft-territory migration branch. It is read-only and **not**
evidence of the reported production failure until an authorized store/address
pair is checked.

## Scope and safety

The diagnostic accepts **exactly one** store UUID and one address UUID, and
requires `--acknowledge-authorized-access`. It performs no enumeration or
writes. It opens a PostgreSQL read-only transaction, then rolls it back.
Prefer a database role with SELECT-only permissions in addition to the
transaction guard. Do not pass database credentials on the command line.

Output is restricted to IDs, configuration flags, the existing assigned
legacy service-area decision, rounded PostGIS distances and reason codes.
It excludes names, phones, house details, landmarks, customer IDs and raw
coordinates. Treat the resulting scoped IDs/distances as sensitive
operational information; do not paste into public issues.

## Approved isolated environment

From `backend/` with an authorized **read-only** database connection:

```bash
python -m app.scripts.diagnose_delivery_serviceability \
  --store-id 'STORE_UUID' \
  --address-id 'ADDRESS_UUID' \
  --acknowledge-authorized-access
```

Do not run an unreviewed development image against the live database or
replace a production container to obtain the tool. If the diagnostic is not
already in an approved running image, use a separate approved read-only
environment. Production execution is **pending authorization**.

## What to verify

Compare the same store/address's assigned service-area ID, store/merchant
availability, hub/area activation, pin presence, hub-to-address distance,
inside-area predicate and evaluator reason code. A global village or
location preview is not a substitute for the store-specific checkout
decision. Never widen a radius, change a hub centre, or bypass eligibility
merely to make a test pass.

Before release, confirm the combined COD and UPI checkout paths reject
missing/unconfirmed/out-of-area pins **without creating an order**, and
retain Razorpay capture checks, idempotency, inventory and merchant/rider
fulfilment gates. Use a disposable PostGIS test database and then an
authorized staging environment. Production diagnosis and physical Android
acceptance remain unverified.

Rollback is application-only where possible; keep additive schema and
payment/audit history intact. Do not execute a destructive Alembic
downgrade after data exists.
