# P0 payment/geography migration integration bridge

**Development only. No production migration or deployment authorization.**

This draft branch is stacked on PR #257 (authoritative checkout geography on
payment PR #243). It incorporates the address provenance backend from PR #247
without changing checkout payment capture or the existing service-area rules.

## Migration graph

```
0026_delivery_proof_limits
  |-- 0027_webhook_retry_schedule
  |-- 0027_address_location_provenance
  \-- 0028_payment_geography_merge  (parents: both 0027 revisions)
```

The merge revision is deliberately empty. It preserves both existing revision
IDs and their parentage; it does not backfill coordinates, modify territory
assignments, or rewrite payment events. The Alembic graph is a diamond (the
merge is a child of *both* 0027 revisions), not a linear renumbering.

CI now exercises both upgrade paths using **two disposable PostGIS databases**:
payment-only head → merged head and geography-only head → merged head.
It checks that both the payment retry scheduling fields and address provenance
fields exist after each upgrade. Backend CI also performs a fresh application
migration, verifies one Alembic head, and runs the full regression suite.

## Stacked PR integration and future territory migration

PR #250 currently has `0028_delivery_territories` descending from
`0027_address_location_provenance`. Do not combine it unchanged with this
branch: that would create a second Alembic head. Before merging territory work,
rebase its **unreleased draft** migration to descend from
`0028_payment_geography_merge` and test payment-only, geography-only and
territory-head upgrades in isolated databases. Do not rewrite revision IDs
already applied to any real environment; use a new merge revision instead if
a migration has been applied outside disposable CI.

## Acceptance and rollback

- Confirm exact-head Backend, Web, Mobile and Production CI. A green parent PR
  does not establish this combined head's safety.
- Verify legacy addresses remain NULL-provenance and usable only under the
  documented compatibility policy. Explicit `searched_place` centroids are
  rejected for checkout, and confirmed GPS/map pins require a server timestamp.
- Verify no rejected COD/UPI order creates an order, charges, reserves stock
  or triggers fulfilment.
- Do not merge payment PR #243 independently: its temporary geography bypass
  remains unsafe without PR #257.
- Application rollback should preserve additive columns and payment history.
  A database downgrade would destroy captured provenance and retry scheduling
  metadata; it is **not** an automatic rollback.
- Authorized production diagnosis, staging checkout and physical Android
  acceptance are pending. No production DDL, coverage edit or APK publication
  is permitted by this PR.
