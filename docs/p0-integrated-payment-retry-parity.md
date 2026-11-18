# P0 integrated checkout: payment retry safety and geography release gate

This change is stacked on geography/payment PR #267. It does **not** activate new territories or relax legacy serviceability checks. The payment-only PR #243 is a reference for payment logic, **not** a safe standalone checkout merge because its base contains a temporary delivery-zone bypass.

## Scope and invariants

- Preserve `evaluate_delivery()` at quote and order placement for COD and UPI, including store-specific eligibility, confirmed location and legitimate delivery limits.
- Do not create an order for an unserviceable address, and do not mark a UPI order paid or dispatchable without authoritative captured-payment evidence.
- Do not create/reuse a Razorpay payment intent when multiple active attempts, unknown attempt states, or an active attempt missing a provider order ID require reconciliation.
- Customer web/Flutter messaging for HTTP 409, 502 and 503 must not suggest immediate re-payment. Refresh order status after an intent error; do not offer web Pay Now on a non-placed order.
- Maintain idempotency payload consistency (address and payment method) and exactly-once stock restoration.

## Provenance of the synchronized changes

The backend intent route and regression suite, Flutter retry handling and tests, and web order retry handling and e2e cases are synchronized from payment PR #243 at commit `14c82fe1f02d6a7fe1b7cde45d09c3dd5c6b6f2e`. Files were compared against integrated PR #267 at `9c62acd0842e3da836bba1dd5c75bab7d2bdec5a`; changes in the synchronized UI files were confined to payment-retry behavior. Checkout geography route was deliberately not copied.

## CI / test acceptance

1. Require exact-head Backend, Web, Mobile and Production CI success; investigate failures rather than inferring success from the payment-only branch.
2. Run PostGIS-backed COD and UPI serviceability boundary, missing-coordinate, inactive-area and cross-store tests. Verify rejected requests create no order, stock reservation or payment attempt.
3. Run payment intent integrity, capture, failed webhook, expiry, refund, concurrency and idempotency tests.
4. Run Flutter payment-retry-message tests and Web order tracking/retry e2e, including a 409 followed by a refreshed paid order and a non-placed pending order with no Pay Now button.
5. Verify both Alembic upgrade paths from the payment and geography histories in disposable PostGIS databases; inspect the merged head before staging.
6. Staging only: exercise COD inside/outside coverage; UPI failed, delayed, captured, duplicate, cancelled, refund and provider-outage lifecycles with provider sandbox credentials. Confirm no double charge, no premature fulfillment and no bypass.
7. Android device acceptance: confirmed GPS/map pin, denied permissions, inaccurate location, manual landmark address, offline/retry, Hindi/Marathi display and low-end device performance.
8. Production root-cause diagnosis remains **pending** until an operator supplies an explicitly authorized store/address pair and runs the scoped SELECT-only diagnostic. Do not log raw coordinates or payment secrets.

## Deployment preparation (not authorization)

- Obtain review approval and a green exact-head CI matrix, verify staging against a production-like sanitized dataset, review migrations, capture current production commit and migration revision, and prepare verified database/environment backups.
- Deploy only after separate explicit production authorization. Keep new territory features disabled by default and legacy serviceability authoritative.
- Before rollout, inspect the intended migration graph; do not downgrade or drop populated payment/territory tables as a rollback shortcut.
- Post-deployment operator checks: API health, read-only order/payment reconciliation, safe in/out-of-coverage quote and order tests, webhook ledger, refund obligations, worker health, and Android/web parity.
- Rollback if any coverage expansion, unauthorized paid state, duplicate charge, lost stock reservation or migration anomaly is observed: stop new rollout, disable new feature flags, revert application image to the verified prior version when schema-compatible, retain append-only payment/territory history, reconcile in-flight payments, and escalate database restoration to a separately approved recovery plan.

No production deployment, migration, territory mutation, payment capture, or APK publication is authorized by this document.
