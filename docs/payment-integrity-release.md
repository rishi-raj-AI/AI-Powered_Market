# GaonOne UPI payment integrity — release gate

**Status:** Development only. Do not deploy, enable expiry, run real payments,
issue refunds, or build APKs until the release owner approves.

## Core invariants

1. A valid Razorpay signature authenticates a callback; only an independent
   provider read with status `captured`, matching payment ID, provider order ID,
   amount in paise and currency INR, may mark a UPI order `paid`.
2. COD orders remain payable on delivery. UPI orders with payment status other
   than `paid` cannot be accepted, prepared, marked ready, dispatched, picked
   up or completed.
3. Merchant order-received notifications for UPI are emitted on first verified
   capture, not when a payment reservation is created.
4. Late failure events cannot overwrite `paid`, `refund_pending` or `refunded`.
   Late captures after cancellation create a durable refund obligation and do
   not reopen the commercial order.
5. Expiration never infers nonpayment from a provider outage. Stock restoration
   is guarded by `orders.stock_restored_at`. An order with both a captured and
   an authorized payment is deferred for reconciliation, not auto-expired.
6. A second captured payment cannot replace the first payment ID or silently
   generate a second merchant settlement. It requires manual reconciliation
   and, when money is owed, a separately reviewed refund obligation.
7. Refund obligations created for captures after cancellation or return must
   include the captured provider payment ID. Without it the refund dispatcher
   cannot execute the obligation; the captured attempt must be flushed first.
8. A refund webhook must match the recorded Razorpay payment ID, refund ID,
   amount in paise and currency before it can mark an order refunded. A late
   pending/failed refund result cannot reverse an already processed refund.
9. Every valid signed webhook is committed to the event ledger **before** any
   Razorpay read or financial transition. A provider outage rolls back only
   processing, not the durable event. Duplicate delivery may safely retry an
   unprocessed event, even before the replay worker is enabled.
10. An `order.paid` event without a payment entity may be reconciled using
    provider order-payment history, but only if exactly one matching captured
    payment exists and no authorized payments make the outcome ambiguous.
11. Before any capture is applied (callback, webhook, expiry), the stored
    attempt must be a Razorpay INR attempt for **exactly** the commercial
    order total. An underpaid/overpaid attempt never creates settlement or
    releases fulfilment even if its own provider capture is genuine.
12. An unknown provider refund ID may only be associated with an obligation
    by payment ID when exactly one candidate exists and it has no different
    provider refund ID. Multiple candidate obligations require manual review.
13. Payment expiration fails closed on every nonterminal or unknown provider
    payment status (including `created` and `refunded`), malformed provider
    history, a locally recorded capture, or an attempt from an unknown
    provider. Only a verified absence of money or well-formed terminal failed
    payments may release reserved stock.
14. Refund webhooks lock the commercial order before the refund obligation,
    matching cancellation lock order. Refund dispatch also reacquires the
    order lock before the refund lock after the provider call. PostgreSQL
    concurrent cancellation, refund-webhook and dispatch execution still
    require integration acceptance.

15. A successful refund API HTTP response must independently identify the
    expected provider payment ID, refund ID, exact amount in paise and INR
    currency before GaonOne records provider success. Missing or conflicting
    fields leave the refund obligation in `processing` for manual
    reconciliation, with no blind retry or false `refunded` state.
    A verified webhook that completed while the API call was in flight
    remains terminal and must not be downgraded.

16. A refund HTTP timeout, 5xx, unreadable response or response without a
    provider refund ID has an **indeterminate** outcome: the provider may have
    moved money. Keep the obligation in `processing` for manual provider
    reconciliation, and exclude it from automatic retries. Explicit provider
    rejection remains separately retryable under existing policy. A webhook
    confirming success during an outbound refund call wins over a subsequent
    API error; never downgrade `succeeded` to `failed`.

## Feature flags and operator safety

- `PAYMENT_WEBHOOK_REPLAY_ENABLED=false` is the safe default. The durable
  webhook table retains unconfirmed captures with `processed_at=NULL`;
  the opt-in worker rechecks provider capture and records completion only
  after verification. Configure `PAYMENT_WEBHOOK_REPLAY_BATCH=25` and review
  provider rate limits and aged pending events before enabling. Revision
  `0027_webhook_retry_schedule` adds `attempt_count` and
  `next_attempt_at` to persist replay backoff across worker restarts.
  Unresolved events retry after 60, 120, 240, 480, 960, 1920 and then
  at most 3600 seconds; they are never silently discarded. A deferred
  old event no longer monopolizes the oldest-event batch.
  Check `processed_at IS NULL` and `next_attempt_at` for backlog health.
- `PAYMENT_EXPIRY_ENABLED=false` is the safe default. Leave it disabled until
  sandbox testing, historical reconciliation and business approval.
- `PAYMENT_EXPIRY_MINUTES=15` and `PAYMENT_EXPIRY_BATCH=25` only apply if enabled.
- Never print Razorpay credentials, raw webhook signatures, customer addresses
  or payment method details in logs.
- Historical read-only audit (requires provider read credentials):
  `python -m app.scripts.audit_upi_payments --limit 100 --days 30`.
  It makes **no** financial or database mutations. Review every result other
  than `verified_capture`, especially `multiple_captures`, `capture_mismatch`,
  and `provider_unavailable`; a matching capture must not conceal another
  capture or an unreadable payment attempt. Do not automatically downgrade
  paid orders.

## Pre-release validation

- [ ] Backend CI lint, migration checks and full pytest suite green,
      including Alembic upgrade/downgrade of revision 0027.
- [ ] Web CI and Flutter analysis/tests green.
- [ ] Webhook ingestion: provider outage after signed event persistence,
      duplicate retry without worker, concurrent duplicate delivery, and
      replay of the original durable payload.
- [ ] Order-only `order.paid` webhook: single matching capture succeeds,
      multiple captures or authorized payments defer, and provider outage
      preserves the event.
- [ ] Replay worker: repeated authorized capture, provider outage,
      retry scheduling, worker restart, and a newer capture behind an older
      deferred event (no head-of-line starvation).
- [ ] Razorpay **sandbox**: captured, authorized, failed, dismissed, timeout,
      webhook-first, callback-first, replay, duplicate payment ID, mismatched
      amount/currency/order, refund after late capture.
- [ ] Two concurrent intent requests create only one provider order.
- [ ] Verify and webhook acquire order lock before payment-attempt lock.
- [ ] Merchant acceptance and preparation reject unpaid UPI but accept COD.
- [ ] Rider offers, assignment, pickup and delivery completion reject unpaid UPI.
- [ ] Expiry tests: zero attempts, provider outage, created/authorized/refunded/
      unknown status, malformed failed payment, local capture evidence, unknown
      provider, captured plus authorized, multiple captures, inventory restore
      once, cancellation race.
- [ ] Refund dispatch API tests: matching payment ID, refund ID, amount and
      currency; truncated/mismatched provider response quarantined without
      automatic re-dispatch or false refunded state.
- [ ] Refund provider ambiguity: timeout, 5xx, malformed HTTP 200, and
      webhook success racing a provider error; none can cause an automatic
      duplicate refund or downgrade a confirmed refund.
- [ ] Refund webhook tests: order-before-refund lock acquisition under
      PostgreSQL concurrency with cancellation, mismatched payment/refund ID, amount/currency,
      ambiguous multiple obligations for one provider payment,
      malformed payload, valid processed result and late failed result after
      success. Inspect any indefinitely deferred refund events manually.
- [ ] Manually investigate any second captured payment or unprocessed duplicate
      webhook. Do not clear the event or refund blindly: reconcile the provider
      transaction and customer obligation first.
- [ ] Run the historical audit against a **staging copy**; reconcile discrepancies
      manually with Razorpay records and the refund ledger.
- [ ] Confirm no production payment record is changed by staging tests.
- [ ] Confirm the temporary geographic checkout bypass is tracked and is
      replaced by the geography project before nationwide release.

## Deferred release steps

Production rollout, database backup, operator sign-off, post-deploy monitoring,
and signed Android APK generation are explicitly deferred. The CI pipeline
alone is not proof of real-payment correctness.
