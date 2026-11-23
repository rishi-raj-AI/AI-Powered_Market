# Published draft territory impact preview (read-only)

## Scope and safety

`POST /api/v1/admin/delivery-territories/draft-impact-preview` accepts a store UUID, a territory UUID and an explicit synthetic test point (WGS84 latitude/longitude) in the POST body. It requires `geography.manage` and `TERRITORY_ADMIN_PREVIEW_ENABLED=true` (disabled by default). It never loads customer addresses, writes territory rows, publishes coverage, quotes delivery, or changes COD/UPI checkout. Do not submit real customer address coordinates to this administrative tool.

Unlike the active-only parity endpoint, this compares a **single published draft** territory to the store's legacy service area. The candidate must have a current, complete, immutable geometry/exclusion snapshot, active region, active store assignment and valid effective windows. Unpublished edits and missing or ineligible assignments produce `NOT_COMPARABLE`, not a false geographic contraction. The published version is included for review and the supplied point is never returned.

Possible parity statuses: `MATCH_BOTH`, `LEGACY_ONLY`, `DRAFT_ONLY`, `NEITHER`, `NOT_COMPARABLE`. `DRAFT_ONLY` signals a *potential* coverage expansion if a separate activation process is ever approved. It does **not** authorize checkout or activation. `LEGACY_ONLY` flags a potential contraction requiring investigation. A geographic match says nothing about confirmed address provenance, inventory, capacity, fees, merchant availability, rider dispatch, payments or final order eligibility.

## Review checklist

1. Verify the base PR #262 and this PR's exact-head Backend, Web, Mobile and Production CI; execute PostGIS tests in a disposable database.
2. Verify both payment-first and geography-first Alembic upgrade paths, then reconcile new payment branch commits before integrating.
3. Exercise synthetic circle and polygon cases including exclusions, boundaries, inactive assignments, missing publication and unpublished geometry changes.
4. For any planned territory activation, obtain explicit operator review of sampled parity, coverage impact, merchant assignment and audit history. A passing preflight or impact preview alone is insufficient.
5. Preserve the existing legacy service area as checkout authority until separate approved, tested feature-switch work. Never enable the administrative flag in production without authorization.

## Rollback

This PR introduces no migration and no checkout changes. Keep the administrative flag off to disable the endpoint. Revert the branch/PR if necessary; no data rollback is required. Production diagnosis, staging COD/UPI E2E, real-device GPS confirmation and release sign-off remain pending.
