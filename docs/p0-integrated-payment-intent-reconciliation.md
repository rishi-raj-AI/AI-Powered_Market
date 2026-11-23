# P0: UPI payment-intent reconciliation on the geography integration stack

## Scope and provenance
This draft stacks on PR #266, which retains the centralized COD/UPI `evaluate_delivery()` checks and checkout idempotency consistency. It ports **only** the payment-intent reconciliation and Razorpay order-response validation from payment PR #243 (inspected at `ba315c78`), plus its synthetic tests. It does not port the payment-only branch's temporary delivery-zone bypass. No migration, live provider request, production query, production mutation, PR merge or APK publication is part of this change.

## Safety invariants
- Only an owned UPI order in `PLACED` with payment `PENDING` or `FAILED` can request an intent. Refunded, refund-pending, accepted, cancelled and otherwise nonpayable orders are rejected.
- The order row lock covers payment-attempt inspection, provider history reads, and provider-order creation; concurrent retries must not create two live intents.
- An existing attempt with status `paid` **or** a recorded provider payment ID blocks new provider orders, even if the order's payment status is stale.
- Reusing a provider order requires the original amount/currency to match the commercial order and complete provider history containing no nonfailed or malformed payment. Provider outage or truncated history fails closed.
- Before creating a new provider order, all earlier attempts must have consistent provider/amount/currency and no capture evidence; provider history must confirm no unresolved payment.
- A successful Razorpay HTTP response is insufficient: the returned order ID must be a nonempty string and the amount (integer subunits) and currency must match the request exactly.
- Existing authoritative legacy serviceability checks, immutable territory previews, signed webhooks, refund and stock safeguards, and idempotency rules remain untouched.

## Synthetic acceptance and CI
Run Backend CI on the **exact PR head**, including PostgreSQL/PostGIS migrations and tests, plus Web, Mobile and Production CI. Focus on:
1. Concurrent intent retries returning one provider order and maintaining lock order.
2. Captured attempt with stale order-level `PENDING`/ `FAILED` refusing a new intent.
3. Existing provider order with captured/authorized/refunded/unknown or malformed history refusing reuse.
4. Provider history read outage returning 503/502 without creating a new provider order.
5. Provider order responses with wrong amount/currency, missing or malformed IDs refusing checkout exposure.
6. COD and UPI geography tests continuing to reject outside-territory, approximate and unconfirmed locations.

## Release gate (not executed)
Before any authorized deployment, independently review the latest payment PR #243 for new commits and reconcile only payment-safe changes, never the temporary geographic bypass. Validate staging COD/UPI: valid capture, failed payment, late capture, replay, retry, cancellation, refund and idempotent replays. Verify the Alembic single-head merge ancestry on a disposable database; check production migration state **read-only** using operator-approved commands. Run the scoped checkout diagnostic only with an explicitly authorized store/address pair and SELECT-only DB role; do not log coordinates or customer PII. Require physical Android GPS/map-pin acceptance, staging Web acceptance, CI green on the final exact SHA and operator signoff.

## Rollback preparation
Retain the previous immutable image digest, database backup/restore plan and prior application config. This change adds no schema or flag, so application rollback is a redeploy of the last approved image after verifying payment/stock consistency. **Never** automatically downgrade migrations, retry ambiguous payments/refunds, expand service areas or clear pending financial obligations. Rollback should preserve existing orders, payment attempts and webhook history; reconcile any in-flight capture with Razorpay before further fulfillment.
