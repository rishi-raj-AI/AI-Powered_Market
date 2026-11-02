# Read-only multi-territory PostGIS preview

This PR is stacked on draft PR #250 (and transitively PR #247). It adds no
routes, migrations, feature-flag changes, production writes, checkout switching,
backfill, or store assignment mutations.

`match_active_store_territory` returns an optional *geographic* match for a
store ID and validated WGS84 coordinate pair. It is deliberately not a
fulfilment or checkout decision: it does not check store/merchant approval,
inventory, pricing, payment, dispatch, rider availability, or order idempotency.
The existing hub-centred legacy `service_areas` evaluator remains authoritative.

The read-only query:

- Requires active operating region, territory, and store assignment, plus a
  published immutable territory version whose **complete canonical geometry
  and exclusion snapshot** matches the mutable territory rows. A draft edit,
  added/removed exclusion, or incomplete historical snapshot fails closed;
  it cannot silently change the published preview.
- Requires the assignment's delivery-enabled flag and half-open effective dates.
- Evaluates circles using PostGIS `ST_DWithin` on geography in metres.
- Evaluates polygons with boundary-inclusive `ST_Covers` in SRID 4326.
- Applies exclusion multipolygons with boundary-inclusive `ST_Covers`.
- Uses explicit assignment priority, then territory priority, then stable UUID
  tie-breakers; a nearby unassigned territory cannot grant coverage.
- Does not log coordinates or customer address data.

The canonical `delivery-geometry-v1` snapshot contains the geometry type,
centre and radius as decimal strings, exact polygon EWKB hex, and a
stable UUID-ordered array of exclusion EWKB hex. The helper
`snapshot_current_territory_geometry(db, territory_id)` is read-only and
**does not publish**. An eventual publisher must capture this snapshot in the
same locked transaction as approval, version creation, audit insertion and
published-version update. This comparison adds work proportional to the
store's candidate territories and their exclusions; benchmark and optimize
before nationwide authoritative rollout. Mutable assignment priority,
assignment activation, territory status and effective dates are still
operational controls, not protected by this geometry snapshot.

Run `pytest -q tests/test_territory_preview.py` against disposable
PostgreSQL/PostGIS after Alembic upgrade. Tests cover circles, polygon
boundaries, exclusions, status/effective-date filtering, overlapping
assignments, wrong-store isolation, invalid coordinate inputs, and unpublished circle,
polygon, exclusion and incomplete-snapshot drift.

## Acceptance and safety

This is **not ready for a production checkout switch**. Before any
authoritative use, reconcile Alembic branches with payment PR #243, backfill
legacy areas into draft rows without changing coverage, implement approved
immutable publication/version checks, run dual-engine comparison and
mismatch review, and integrate with centralized P0 checkout serviceability
behind a single consistent feature flag. Do not infer coverage from a
geographic match alone.

Rollback: remove the new preview module/tests or disable future callers.
There are no schema changes or production data mutations in this PR.
