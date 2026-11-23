# Admin territory geographic preview (draft, no checkout switch)

This change is stacked on PR #251, PR #250, and PR #247. It adds a
**read-only** API for internal administrators to preview whether a coordinate
falls inside an active, published, store-assigned territory. It does not
modify checkout, delivery pricing, dispatch, legacy service areas, or payment.

## Access and request

Feature flag: `TERRITORY_ADMIN_PREVIEW_ENABLED=false` (default).

`POST /api/v1/admin/delivery-territories/preview`

Requires an authenticated administrator with the existing
`geography.manage` capability. Non-admin users receive HTTP 403; anonymous
users receive HTTP 401. The flag-off response is HTTP 404. The request body
contains `store_id`, `latitude`, and `longitude`. Coordinates are sent in
the body rather than URL query parameters to avoid routine access-log exposure.
Reverse proxies, error instrumentation, and APM must also be configured not to
log request bodies or sensitive location data.

The response contains `geographic_match`, optional territory and assignment
identifiers, optional geometry type, and
`checkout_authoritative: false`. It never echoes coordinates, customer
addresses, phone numbers, pricing, or a promise of fulfilment.

## Validation

- Run Backend CI against PostgreSQL/PostGIS, including
  `tests/test_territory_preview.py` and
  `tests/test_admin_territory_preview.py`.
- Confirm flag disabled by default, admin access, customer/anonymous denial,
  invalid-coordinate rejection, no-match behavior, and no coordinate echo.
- Verify the endpoint does not issue INSERT/UPDATE/DELETE or commit.
- Keep legacy checkout authoritative until an approved migration/backfill,
  parity comparison, and separately reviewed rollout.

## Release and rollback

Do not enable in production without explicit authorization. The change is
additive and requires no new migration beyond PR #250. Rollback is to leave
`TERRITORY_ADMIN_PREVIEW_ENABLED=false` or revert this API commit; no data
rollback is required.

## Important blocker before territory publication

The current preview checks `delivery_territories` mutable geometry while
requiring only that a `published_version` row exists. The schema's append-only
version/audit triggers do not themselves guarantee that mutable territory
geometry and exclusions match the published snapshot. A future publishing
implementation **must** atomically pin published geometry and exclusions to an
immutable version (or enforce write guards on live coverage), validate
geometry and assignment state, and audit every change before enabling any
authoritative new-territory checkout path. This read-only endpoint does not
resolve that blocker and must not be treated as evidence of publication safety.

The payment PR #243 and geography PR #247 currently introduce divergent
Alembic `0027` revisions; reconcile and test the combined migration graph
before merging either stack.
