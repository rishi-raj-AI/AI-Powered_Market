# P0 signed failed-payment webhook integrity — combined checkout branch

## Source and integration scope
This change is stacked on geography/payment PR #265 (commit `e7bd67f`) and ports the payment-only PR #243 `backend/app/api/v1/routes/payment_hardening.py` from inspected head `1d9cf0a5d577dfb007864e0a2223db9304b851ec`. The complete file's blob SHA is `d1fdae0caed34549b1ece6efecfa82f37e49c377`, matching the inspected payment branch. Its dedicated synthetic PostgreSQL regression suite is ported without modifications.

Do **not** merge the payment-only checkout route: that branch retains the temporary geographic eligibility bypass. The combined branch continues to use centralized delivery serviceability for new COD/UPI orders, and retains the idempotency-intent guard from PR #265.

## Threat model and behavior
A signed Razorpay `payment.failed` event proves origin, **not** that the event belongs to this local payment attempt. A malformed, order-only, mismatched-amount/currency/status or wrong-provider-order failure must not mark an order failed or erase capture evidence. Such events remain unprocessed for reconciliation. Even for an otherwise well-formed failure, an attempt already marked paid or carrying a captured provider payment ID must remain untouched.

This change checks the payment entity ID, exact provider order ID, failed status, integer paise amount, and currency before applying failure. The absence of provider order ID is not treated as a successfully processed failure. No new payment capture, refund dispatch, settlement, or inventory path is added.

## CI / acceptance
Run `pytest -q tests/test_payment_failed_webhook_integrity.py tests/test_payment_geography_checkout_gate.py tests/test_checkout_idempotency_payload.py` against a disposable PostgreSQL/PostGIS database. Run full Backend, Web, Mobile, and Production CI at the exact head. Confirm a well-formed failed payment updates only an unpaid attempt, while malformed, unrelated, order-only, and late events preserve the original payment state. Check that existing captured/failed UPI fulfilment gates and COD geography restrictions remain intact.

Prior PR #265 passed all four workflows at `e7bd67f`; this new head requires independent validation. No sandbox payment or real-device acceptance is implied by synthetic tests.

## Release safety and rollback
Before any approved merge/deploy, reconcile ongoing PR #243 changes, inspect the migration graph, perform staging COD/UPI payment-failure/late-capture/retry acceptance, authorize scoped read-only production geography diagnosis, and verify Android address confirmation. Never change production territory settings, financial data, or provider configuration as part of this PR.

Rollback before deployment: close/revert this stacked draft PR. After a separately approved deployment: roll back only the application release to the prior signed image following in-flight payment reconciliation; this change has no database migration. Preserve webhook ledger records and do not blindly replay or delete financial events.
