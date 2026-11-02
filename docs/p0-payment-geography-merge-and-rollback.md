# P0 payment + geography integration and release gate

**Status: development-only, no production authorization.** Originally written for
PR #257, this runbook now tracks the draft integration stack through #264.
It does not assert production recovery or authorize migration execution.

## Invariants

1. A cart quote is advisory; order creation must repeat the **same**
   store-assigned, active, hub-centred PostGIS eligibility check.
2. Neither COD nor UPI may bypass delivery coverage, and a store pin cannot
   substitute for the approved service-area hub.
3. No village-centre fallback may turn a landmark-only address into a confirmed
   doorstep pin. Explicit searched-place centroids and unconfirmed GPS/map pins
   are ineligible. Historical pinned coordinates with null provenance retain
   compatibility, but are never represented as verified.
4. Rejected orders do not create orders, reserve inventory, emit order-placed
   notifications, or initiate a payment.
5. UPI orders are reservations until provider-verified capture; merchant and
   rider fulfilment gates remain as implemented in payment PR #243.
6. Checkout idempotency, inventory locks, merchant approval, store hours,
   fees, refunds and payment-ledger integrity remain unchanged.
7. Legacy service areas remain authoritative until separately reviewed
   parity, rollout, rollback and activation gates are completed.

## Branch ownership

- Payment: PR #243, branch `fix/verify-upi-capture-before-paid`.
- Geography P0: PR #244, centralized evaluator and read-only scoped diagnostic.
- Payment/geography bridge: PR #257, stacked on #243. It ports the evaluator
  and removes the temporary checkout bypass, without importing territory
  migrations or changing the payment state machine.
- Address provenance: PR #247; territory schema: PR #250 and descendants.

Do not merge #243 directly while its checkout bypass remains in its head.
Do not merge #257 without reviewing drift against the current #243 head.

## Alembic divergence: mandatory integration blocker

At the inspected heads, both independent migrations descend from
`0026_delivery_proof_limits`:

- Payment: `0027_webhook_retry_schedule`, adds retry scheduling columns and
  index to `payment_webhook_events`.
- Geography: `0027_address_location_provenance`, adds nullable address
  provenance fields and constraints.
- Territory: `0028_delivery_territories`, descends from
  `0027_address_location_provenance`.

The numeric filename prefix is not the revision identifier. Both 0027 revisions
are distinct heads until an integration merge revision is added. Do **not**
silently rewrite a revision ID or `down_revision` on an already-applied branch.

For the eventual combined integration branch, include both independent
migration files and add an **empty Alembic merge revision** whose
`down_revision` is the tuple
`("0027_webhook_retry_schedule", "0028_delivery_territories")`.
Use a unique revision ID and verify `alembic heads` reports one head.
An empty merge only reconciles ancestry; it must not change existing columns,
data, boundaries, or payment records.

In a **disposable PostgreSQL/PostGIS database only**, exercise:
- Upgrade from deployed schema revision to the combined single head.
- Upgrade from payment-only head to the combined head.
- Upgrade from geography/territory-only head to the combined head.
- Verify both payment columns and address/territory constraints are present.
- Run payment, geography, idempotency, PostGIS and Alembic regression suites.
- Confirm no conflicting heads, unexpected DDL or data backfill.

Never run `alembic upgrade`, `downgrade`, `stamp`, `merge` or DDL on
production without separate deployment authorization.

## Read-only production diagnosis — operator template (not executed)

Use the existing scoped diagnostic from PR #244 **only after** the script
is deployed or run in a separately authorized read-only environment. Supply
one store UUID and one address UUID; avoid logging PII or exact coordinates.
The script should report reason codes, service-area IDs and rounded distances,
not names, phones, landmarks or raw lat/long.

Before any operator run, confirm the production database role is SELECT-only,
the session uses `default_transaction_read_only=on`, and that neither
migrations nor data repair scripts are invoked. Inspect production version
and Alembic current revision read-only; do not assume reported commit
`b96399b` is still deployed without checking the server.

For a SQL-only diagnostic, use a narrowly scoped read-only transaction:

```sql
BEGIN TRANSACTION READ ONLY;
SELECT s.id AS store_id, s.service_area_id, s.delivery_enabled,
       s.is_active AS store_active, sa.is_active AS area_active,
       sa.radius_km, v.is_active AS hub_active,
       a.id AS address_id,
       (a.latitude IS NOT NULL AND a.longitude IS NOT NULL) AS has_pin
FROM stores AS s
LEFT JOIN service_areas AS sa ON sa.id = s.service_area_id
LEFT JOIN villages AS v ON v.id = sa.hub_village_id
CROSS JOIN addresses AS a
WHERE s.id = :store_uuid AND a.id = :address_uuid;
ROLLBACK;
```

Use bound parameters through a SQL client; `:store_uuid` and
`:address_uuid` are placeholders, not SQL literals. Restrict output
distribution to authorized operators; do not query or print customer
coordinates, contact details, address text or payment identifiers.

## CI and release acceptance

- Backend CI: PostGIS boundary/overlap, unpinned/approximate addresses,
  inactive/missing assignments, COD and UPI rejection without order or
  inventory mutation, plus payment capture, replay, expiry and refund suites.
- Web/Mobile/Production CI: exact integration head must pass, not just parent
  PRs independently.
- Staging: confirmed GPS/manual-pin, inside/outside/edge-of-radius, stale
  address, retries, duplicate idempotency key, COD and UPI failed/pending/
  captured outcomes, merchant/rider visibility and recovery.
- Privacy: ensure checkout and diagnostic logs omit exact coordinates,
  personal address text and payment secrets.
- Approval: production operator and release owner explicitly authorize
  deployment, migrations, monitoring and any APK generation separately.

## Deployment and rollback preparation — not executed

1. Back up database and configuration; verify backup restoration in staging.
2. Record exact production commit, schema revision, image digests, feature flags,
   active service-area assignments and healthy container baseline.
3. Deploy only an approved, CI-green combined commit using the existing
   release process. Keep territory preview/publication/activation flags off.
4. Run controlled COD and UPI smoke tests and inspect reason-code counts
   without PII. Monitor checkout 409 rates, provider capture discrepancies,
   duplicate orders, refund obligations and latency.
5. If checkout regresses, stop rollout and restore the prior **application**
   image/commit and flags. Preserve additive database schema and all payment,
   order and audit rows. Do **not** blindly downgrade migrations, delete
   payment attempts or expand service-area radii.
6. Escalate any in-flight payment ambiguity for manual provider reconciliation;
   do not mark payments paid or retry refunds based on timeout alone.

**Current gate (2026-11-02):** the draft merge revision and three disposable
upgrade paths were validated in earlier integration CI, but the latest stacked
payment/geography head still requires exact-head CI and final review.
Production root cause, staging COD/UPI and physical Android acceptance remain
unverified. No production deployment, data mutation or APK is authorized.
