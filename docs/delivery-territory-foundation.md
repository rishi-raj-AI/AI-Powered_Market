# Delivery territory foundation — additive schema only

This PR is **stacked on address provenance PR #247**. Its Alembic revision
`0028_delivery_territory_foundation` follows
`0027_address_location_provenance`. Do not merge independently or rename the
migration without reconciling Alembic heads. It is not a delivery-engine rollout.

## Existing authority and compatibility

- `service_areas`, `stores.service_area_id` and the existing hub-centred
  PostGIS radius predicate remain the sole checkout authority.
- No legacy coverage is copied, changed, activated or deleted by this migration.
- All new operational rows default to `draft`. No route reads these tables yet.
- No pricing, order, payment, dispatch or API behaviour changes.
- No new feature flag is enabled; the future `MULTI_TERRITORY_DELIVERY` flag
  must be off by default until a comparison-mode evaluator is reviewed.

## New tables

| Table | Purpose |
|---|---|
| `operating_regions` | Operational grouping independent of administrative village boundaries |
| `delivery_hubs` | Named operational centre with validated coordinates |
| `delivery_territories` | Draft circle or SRID-4326 multipolygon; optional legacy-area mapping |
| `delivery_territory_exclusions` | Valid SRID-4326 multipolygon exclusions |
| `store_delivery_territories` | Multiple store assignments, priorities and effective windows |
| `delivery_territory_versions` | Versioned JSONB snapshot, actor and change reason |
| `territory_change_audit` | Actor/action/reason and before/after version identifiers |

Circle distances must later be evaluated using `ST_DWithin` on geography in
**metres**, with `ST_MakePoint(longitude, latitude)`. Polygon containment
must use `ST_Covers` for inclusive boundaries, apply exclusions, validate
effective dates, and resolve overlapping assigned territories by explicit
priority and a stable ID tie-breaker. The geometry GiST indexes support
polygon lookups. Drafts may be incomplete, but invalid geometries cannot be
persisted. The publish endpoint must reject incomplete drafts.

The new version/audit tables are append-only **by application contract**;
database-enforced immutability and publish/rollback authorization must be
implemented before any write API is exposed. Do not claim that these tables
alone provide approved publishing or rollback.

## Proposed staged migration

1. Merge and deploy the address-provenance dependency after review.
2. Review this migration and run `alembic upgrade head` against a disposable
   PostGIS test database. Confirm existing `service_areas` and `stores` counts
   and geometry decisions are unchanged.
3. In a separate, explicitly reviewed PR, add a read-only, repeatable
   backfill that maps legacy service-area hubs/radii into draft circles,
   retaining the legacy service-area ID and original delivery fee. Never
   activate a territory as a side effect of backfill.
4. Add shadow evaluation: legacy remains authoritative; new engine decisions
   are compared in aggregate without logging customer coordinates.
5. Add admin draft, preview, publish, rollback and store assignment APIs
   with capability enforcement and immutable published version snapshots.
6. Only after observed parity and CI/acceptance, enable a centrally evaluated
   `MULTI_TERRITORY_DELIVERY` flag for both quote and order placement.
7. Defer legacy-field retirement to a later release.

## Review / test / rollback

- Run backend lint, migration upgrade, and PostGIS tests:
  `pytest -q tests/test_delivery_territory_foundation.py`.
- Check `pg_indexes` for both GiST indexes and `ST_SRID=4326`.
- No production database was accessed in this PR.
- Before adoption, downgrade `0028` to `0027` in a disposable environment.
  **After any published territory or audit exists, do not run downgrade**:
  it would discard audit history. Roll back application reads via feature
  flag, retain additive tables, and preserve migration history.
- Production deployment, production diagnostics, data backfill and territory
  activation require separate explicit authorization.

## Remaining gates

Real PostgreSQL/PostGIS CI, migration head consistency, shadow evaluator,
repeatable backfill, publication immutability, authorization, audit, map editor,
real-device tests and production checkout verification.
