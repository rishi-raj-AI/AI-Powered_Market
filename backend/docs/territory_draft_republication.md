# Revised delivery-territory draft publication (no activation)

This reviewable, feature-gated addition is stacked on the initial draft
publication PR. It is **not** an active coverage change, checkout switch,
store-assignment editor, or rollback implementation.

## API

`POST /api/v1/admin/delivery-territories/{territory_id}/publish-revised-draft`

- Requires `TERRITORY_ADMIN_PUBLISH_ENABLED=true` (default **false**).
- Requires the existing `admin.manage` capability (super-admin only).
- Request: `{"expected_published_version":1,"change_reason":"Approved revised draft geometry"}`.
- Requires a previously published, still-`draft` territory and an exact
  optimistic version match. A missing/inconsistent history is rejected.
- Locks the parent territory and existing exclusion rows, validates current
  PostGIS geometry and exclusions, and rejects unchanged snapshots.
- Creates a **new immutable** version and append-only audit record; never
  updates or deletes an earlier published version.
- Returns `coverage_activated=false` and `checkout_authoritative=false`.
- The caller commits the version, audit and pointer together. On rejection,
  the API rolls back the transaction.
- Coordinates and exclusion geometries are never returned in this response.

The snapshot comparison is fail-closed: mutable geometry that differs from the
published version cannot be used by the read-only geographic preview. This
revision endpoint provides a controlled way to stage a *new* snapshot without
turning it into live coverage.

## Operational restrictions

Do not enable this API on production without a separate approval and the
combined geography/payment migration review. Do not activate territories or
assignments via direct SQL. The existing service-area checkout authority remains
unchanged.

Future draft geometry/exclusion writers **must lock the parent territory row**
before editing, to serialize with publication. Existing exclusion rows are also
locked during publication; this does not protect against a new exclusion inserted
by a non-cooperating writer. Before activating coverage, enforce parent locking
for all writers, add approval and impact preview, reconcile competing Alembic
`0027` histories, validate backfill parity, and implement immutable rollback
as a new compensating version. The current snapshot format captures exclusion
geometry but not exclusion metadata/IDs, so it is insufficient for a
lossless automatic exclusion rollback.

## Verification and rollback

Run backend CI against disposable PostgreSQL/PostGIS, including
`tests/test_territory_draft_republication.py` and
`tests/test_admin_territory_draft_republication.py`. Validate authorization,
stale versions, invalid geometry, exclusion changes, immutable history, and
absence of checkout activation. Run the remaining repository workflows.

Rollback of the *feature* is to keep its flag disabled or revert this branch.
Do **not** delete committed version or audit rows. A later reviewed
compensating publication is required to reverse a staged version.
No production migration, database mutation or deployment is part of this PR.
