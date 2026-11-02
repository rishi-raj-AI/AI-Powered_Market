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
  matching immutable territory version with a publication timestamp.
- Requires the assignment's delivery-enabled flag and half-open effective dates.
- Evaluates circles using PostGIS `ST_DWithin` on geography in metres.
- Evaluates polygons with boundary-inclusive `ST_Covers` in SRID 4326.
- Applies exclusion multipolygons with boundary-inclusive `ST_Covers`.
- Uses explicit assignment priority, then territory priority, then stable UUID
  tie-breakers; a nearby unassigned territory cannot grant coverage.
- Does not log coordinates or customer address data.

Run `pytest -q tests/test_territory_preview.py` against disposable
PostgreSQL/PostGIS after Alembic upgrade. Tests cover circles, polygon
boundaries, exclusions, status/effective-date filtering, overlapping
assignments, wrong-store isolation, and invalid coordinate inputs.

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
