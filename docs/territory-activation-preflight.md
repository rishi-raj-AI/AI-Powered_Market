# Draft territory activation preflight (read-only)

This endpoint is a **technical inventory**, not permission to activate coverage. It does not change a territory, create an audit record, write to a database, or change checkout/payment behaviour. The legacy service-area evaluator remains authoritative.

`GET /api/v1/admin/delivery-territories/{territory_id}/activation-preflight`

Access: authenticated `geography.manage` administrators only. Requires `TERRITORY_ADMIN_PREVIEW_ENABLED=true`; default is false. The URL contains only a territory UUID. The response contains no customer coordinates, addresses, or store identities.

The response reports a draft's published version, assignment counts, stable issue codes, `technical_checks_passed`, `activation_authorized=false` and `checkout_authoritative=false`. Technical checks include a current immutable geometry/exclusion snapshot, consistent latest publication history, active region, valid shape, territory effective window, and at least one currently active enabled assignment to an active delivery-enabled store with an approved merchant. Unpublished geometry changes, disabled assignments, stale versions and missing records fail closed.

## Required human review before any activation work

1. Verify the original production checkout rejection with the read-only scoped diagnostic and a legitimately authorized store/address pair. Do not copy personal coordinates into issue comments or CI logs.
2. Reconcile payment PR #243 with geography PR #244 and address PR #247. Payment PR #243 is based on a temporary geographic bypass; **do not merge that bypass**. Both payment and address migrations currently descend independently from `0026_delivery_proof_limits` as separate `0027` revisions. Plan and test a single linear or explicitly merged Alembic history on an isolated database before integration.
3. Validate legacy-vs-territory parity across authorized test cases, including overlapping polygons, circle boundaries, exclusions, delivery-disabled stores, inactive regions, effective windows and confirmed address provenance. Do not broaden serviceability to make a test pass.
4. Require explicit approvals, operator impact review, an independently tested rollback, staged rollout, and post-deploy observation. A passing preflight does not cover any of these gates.
5. No activation endpoint, checkout switch, production migration or APK publication is part of this PR.

## Local review

With a disposable PostGIS database migrated to the branch head, run:

```bash
cd backend
pytest -q tests/test_territory_activation_preflight.py
ruff check app/services/territory_activation_preflight.py app/api/v1/routes/admin_territory_preview.py tests/test_territory_activation_preflight.py
```

Only use synthetic data for tests. Production diagnosis must remain read-only and scoped.
