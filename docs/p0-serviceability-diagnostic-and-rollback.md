# P0 delivery-serviceability repair — investigation and operator gate

Date: 2026-11-02. Base: `main` at `b96399b53ecbc4bbf0a3a6469a93bfdf436de79c`.
This document describes a **proposed** fix, not production acceptance.

## Repository evidence

- `checkout.py` previously used `_address_point()`: when an address lacked
  coordinates, it silently substituted the village reference point. That
  point is not a customer-confirmed doorstep and can yield false approvals or
  false rejections. This is a **confirmed source defect**, not yet a verified
  cause of any specific customer's production failure.
- `/location/serviceability` checks whether **any** active hub-centred area
  covers a point. Checkout must instead check the **store's assigned** area.
  A global positive preview therefore does not guarantee a store can deliver.
- Existing service areas are hub-centred circles, and store registration and
  relocation require the store pin to remain within its assigned area.
  Moving the circle to the store pin without a reviewed territory change
  expands the approved boundary. PR #238 proposes this different business
  rule and must not be merged as an unreviewed bug fix.
- PR #242 temporarily bypasses geographic checkout checks entirely. PR #243
  is stacked on that branch for Razorpay capture verification. **Do not
  merge or deploy the bypass**; coordinate any payment branch rebase with its
  owner so checkout validation is not accidentally removed.
- The main-branch checkout code currently retains inventory, merchant approval,
  store-hours, payment and idempotency checks. This change does not alter them.

## P0 change scope

- New `app.services.delivery_serviceability.evaluate_delivery()` produces a
  structured decision using the **existing assigned service area and PostGIS**
  `ST_DWithin` predicate. No radius changes, new pricing rules or migrations.
- Cart quote and order placement call the same evaluator. Order placement
  still rechecks inside the transaction before inventory decrement/order write.
- Addresses without coordinates remain in the address book, but cannot be
  treated as a confirmed pin for delivery commitment. Existing addresses with
  NULL provenance and coordinates remain eligible under legacy compatibility;
  they are reported as `legacy_coordinates`, **not confirmed GPS**. Once the
  additive provenance fields are present, explicit `searched_place` centroids
  and `gps`/`map_pin` records without a server confirmation timestamp are
  rejected as `ADDRESS_LOCATION_UNCONFIRMED` in both quote and checkout.
- Quote adds the backward-compatible optional
  `serviceability_reason_code` field. Existing response fields remain.
- Regressions use real CI PostGIS for boundary and rejection tests.

## Safe scoped diagnosis

**Not executed on production.** An authorized operator must supply the exact
store UUID and address UUID, confirm access rights, and run the diagnostic with
a SELECT-only database role where feasible. It does not enumerate addresses
or print customer names, phones, landmarks, house details or exact coordinates.
It reports rounded distances, configuration flags, old village-fallback
behavior and the new evaluator's rejection code.

From an approved environment with this branch's code and a configured
`DATABASE_URL`:

```bash
cd backend
python -m app.scripts.diagnose_delivery_serviceability \
  --store-id 'STORE_UUID' \
  --address-id 'ADDRESS_UUID' \
  --acknowledge-authorized-access
```

The command starts `SET TRANSACTION READ ONLY` before all SELECTs and always
rolls back. Never paste the resulting output into public issues if the scoped
IDs or distances could expose sensitive business/customer information.
Do not put DB credentials or address coordinates on the command line.

Only **after an authorized release contains the diagnostic**, an operator may
invoke it inside the existing API container:

```bash
cd /home/ubuntu/gaonone
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T api \
  python -m app.scripts.diagnose_delivery_serviceability \
  --store-id 'STORE_UUID' --address-id 'ADDRESS_UUID' \
  --acknowledge-authorized-access
```

Do not redeploy or replace the running container merely to execute this
command. Until this code exists in the running container, use an approved
separate read-only diagnostic environment.

## Release and rollback gates

1. Run `ruff check app tests`, `python -m compileall -q app tests` and
   `pytest -q` against the existing CI PostgreSQL/PostGIS service.
2. Review the precise rejection and hub/store/address distances for an
   authorized failing production pair. Verify whether missing pins, inactive
   zones, wrong assignment or actual out-of-radius coverage explains it.
3. Confirm the approved **hub-centred** radius business rule. If it is wrong,
   propose an audited coverage change rather than silently moving the centre.
4. Test COD checkout, out-of-zone rejection, missing coordinates, quote
   parity, idempotency, stock concurrency and legacy address access.
5. Before any authorized deployment: verify exact-head CI, backup/restore
   readiness, deployment approval and a controlled smoke test with test users.
6. Rollback application code to the prior approved commit if necessary. No
   database migration is introduced in this P0 branch. The legacy village
   fallback must not be re-enabled as a permanent workaround.

## Pending

- Actual production data and PostGIS inspection: **pending authorized access**.
- Production failure root cause for a specific store/address: **not proven**.
- Backend CI, PR review and real-device acceptance: record separately.
- Confirmed GPS/map pin provenance requires an additive schema and Flutter/web
  work in a follow-on PR; do not mislabel existing coordinates as confirmed.
- Future multi-territory model and map editor must use versioned, audited,
  feature-flagged publication. No live boundaries are changed here.
