# P0 integrated checkout — capture binding and CI repair

**Development only.** This branch stacks on the integrated geography/payment PR #271, not on payment-only PR #243. Do not merge or deploy until the exact-head CI and staging gates below are green and reviewed. Do not enable territory flags, expire real reservations, or run production payment/refund writes.

## Why this patch exists

- PR #271 Backend CI failed because an older payment-history test accepted an item with an ID but **without its required provider `order_id`**. The hardened implementation correctly rejects such a response as incomplete. Update the fixture to carry `order_id=order_test`, and explicitly reject an item attributed to a different order. Do not weaken the fail-closed implementation.
- A locally failed payment attempt without a provider order ID cannot be independently reconciled. Do not offer a second UPI checkout until reviewed.
- A refund must not arbitrarily select the newest paid attempt when multiple possible captures exist. Bind an automatic refund only when exactly one captured attempt has a matching Razorpay provider, INR currency, commercial amount and provider payment ID. Otherwise retain the refund obligation for reconciliation.

## Review scope

Compare `backend/app/api/v1/routes/payments.py`, `backend/app/services/refunds.py`, `backend/tests/test_payment_intent_integrity.py` and `backend/tests/test_refund_capture_binding_integrity.py` against the payment PR #243 head inspected during integration. Geography authorization at quote and place-order remains authoritative; never cherry-pick the payment-only temporary delivery-zone bypass.

## CI and staging acceptance (must be recorded, not assumed)

From `backend/` on a disposable CI/staging PostgreSQL/PostGIS database:

```bash
python -m pytest -q tests/test_payment_history_count_integrity.py tests/test_payment_intent_integrity.py tests/test_refund_capture_binding_integrity.py tests/test_razorpay_payment_history.py tests/test_refund_webhook_integrity.py
```

Also require the full Backend, Web, Mobile and Production **CI workflows** on the exact PR head. A passing Production CI workflow is not permission to deploy.

Stage the following synthetic scenarios with isolated test credentials and no production payments:

1. COD and UPI outside assigned active delivery coverage reject before order creation and do not mutate inventory.
2. A confirmed in-zone address is eligible at both quote and place-order; mismatched idempotency key address/method retries return 409.
3. Failed or ambiguous UPI attempts with missing provider order identity cannot open a new intent.
4. Multiple potential captures or conflicting local/provider evidence prevent automatic refunds and stock release.
5. Exactly one verified matching capture may settle, and exactly one matching refund obligation may be dispatched.
6. Verify browser and physical Android GPS/map-pin confirmation and legacy address upgrade; do not infer confirmed GPS from a village centroid.

## Scoped production diagnosis — read only, separate approval

When authorized with a specific store/address UUID pair and a SELECT-only DB account, run from `backend/`:

```bash
python -m app.scripts.diagnose_delivery_serviceability \
  --store-id '<AUTHORIZED_STORE_UUID>' \
  --address-id '<AUTHORIZED_ADDRESS_UUID>' \
  --acknowledge-authorized-access
```

The script should emit only configuration flags, reason codes and rounded distances. Review its output without logging personal coordinates or addresses. This diagnostic is **pending**, not evidence of a production root cause.

## Rollback / release gate

Before merge, revert this stacked PR or drop its branch to restore the preceding integrated PR #271; do not alter production state. For any future approved deployment, snapshot database and environment/configuration, verify migration compatibility, keep new territory flags disabled, deploy only reviewed commit SHAs, verify payment/checkout and telemetry, and roll back application images/configuration on regression. Do not blindly reverse a migration containing production data; use the approved expand/contract plan. Any ambiguous money movement requires reconciliation, not automatic retry.

**Not completed by this patch:** production root-cause confirmation, physical Android acceptance, live payment-provider acceptance, migration review and production rollout.
