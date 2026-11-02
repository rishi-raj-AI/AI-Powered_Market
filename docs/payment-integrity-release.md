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
    payment exists and no other nonfailed payment (created, authorized,
    processing, refunded, or unknown) makes the outcome ambiguous.
11. Before any capture is applied (callback, webhook, expiry), the stored
    attempt must be a Razorpay INR attempt for **exactly** the commercial
    order total. An underpaid/overpaid attempt never creates settlement or
    releases fulfilment even if its own provider capture is genuine.
12. An unknown provider refund ID may only be associated with an obligation
    by payment ID when exactly one candidate exists and it has no different
    provider refund ID. Multiple candidate obligations require manual review.
13. Razorpay order-payment history is only considered complete when the
    collection reports an integer `count` equal to the number of returned
    `items`, and the response is below the 100-payment page limit. Missing,
    inconsistent, or paginated histories raise a provider error and defer
    expiration or order-only webhook confirmation. A truncated history must
    never be treated as evidence of no capture.
14. Payment expiration fails closed on every nonterminal or unknown provider
    payment status (including `created` and `refunded`), malformed provider
    history, a locally recorded capture, or an attempt from an unknown
    provider. Only a verified absence of money or well-formed terminal failed
    payments may release reserved stock.
15. Refund webhooks lock the commercial order before the refund obligation,
    matching cancellation lock order. Refund dispatch also reacquires the
    order lock before the refund lock after the provider call. PostgreSQL
    concurrent cancellation, refund-webhook and dispatch execution still
    require integration acceptance.

16. A successful refund API HTTP response must independently identify the
    expected provider payment ID, refund ID, exact amount in paise and INR
    currency before GaonOne records provider success. Missing or conflicting
    fields leave the refund obligation in `processing` for manual
    reconciliation, with no blind retry or false `refunded` state.
    A verified webhook that completed while the API call was in flight
    remains terminal and must not be downgraded.

17. A refund HTTP timeout, 5xx, unreadable response or response without a
    provider refund ID has an **indeterminate** outcome: the provider may have
    moved money. Keep the obligation in `processing` for manual provider
    reconciliation, and exclude it from automatic retries. Explicit provider
    rejection remains separately retryable under existing policy. A webhook
    confirming success during an outbound refund call wins over a subsequent
    API error; never downgrade `succeeded` to `failed`. A pending webhook
    that identifies the provider refund ID also blocks automatic re-dispatch
    after a conflicting API error.

18. Refund webhooks must explicitly include the expected currency, not merely
    omit a conflicting value. A signed refund event missing currency is not
    sufficient evidence to mark a refund successful; retain the obligation
    for replay/reconciliation.
19. A read-only audit of paid UPI orders must inspect **all** local payment
    attempts, including unexpected providers, and must not report a verified
    capture when Razorpay also reports created, authorized, refunded, or
    unrecognised payments. Terminal failed payments do not by themselves
    invalidate a separately verified capture.

20. A signed webhook event ID must never silently deduplicate a *different*
    signed payload. Conflicting provider event IDs return HTTP 409 without
    applying the second payload, even when the original event was already
    processed. Overlong event IDs are rejected before database insertion.
21. A paid-order audit must flag a locally `paid` payment attempt missing its
    provider payment ID even if another attempt has a matching capture.
    Malformed provider `failed` entries (missing ID, wrong order, amount or
    currency) are not reliable proof of nonpayment and must not be ignored.

22. A signed `payment.failed` event must identify a specific provider payment
    and order, report status `failed`, and match the attempt's amount in
    paise and INR currency before it can change local failure state. An
    order-only, incomplete, or mismatched failure remains in the durable
    webhook ledger for reconciliation. A late failure must not erase an
    attempt's existing `paid` status or provider payment ID even if the
    order-level status is inconsistent.

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
- The Mobile CI workflow runs Flutter analysis and tests for this payment PR
  but skips its debug APK build. APK generation (including CI smoke builds)
  remains deferred for this branch until release approval. Other PRs and main
  retain their existing mobile build validation.
- `PAYMENT_EXPIRY_MINUTES=15` and `PAYMENT_EXPIRY_BATCH=25` only apply if enabled.
- Never print Razorpay credentials, raw webhook signatures, customer addresses
  or payment method details in logs.
- Historical read-only audit (requires provider read credentials):
  `python -m app.scripts.audit_upi_payments --limit 100 --days 30`.
  It makes **no** financial or database mutations. Review every result other
  than `verified_capture`, especially `multiple_captures`, `capture_mismatch`,
  `provider_unavailable` and `provider_ambiguous`; a matching capture must
  not conceal another capture, an unsettled provider payment, an unknown
  provider attempt, or an unreadable payment attempt. The current audit
  scans **PAID** UPI orders only, not REFUND_PENDING/REFUNDED obligations.
  Do not automatically downgrade paid orders.

## Pre-release validation

- [ ] Backend CI lint, migration checks and full pytest suite green,
      including Alembic upgrade/downgrade of revision 0027.
- [ ] Web CI and Flutter analysis/tests green.
- [ ] Webhook ingestion: provider outage after signed event persistence,
      duplicate retry without worker, concurrent duplicate delivery, and
      replay of the original durable payload. Reject conflicting signed
      payloads reusing the same event ID (pending and processed cases) and
      reject oversized event IDs.
- [ ] Order-only `order.paid` webhook: single matching capture succeeds,
      multiple captures or any unresolved provider payment defers, and provider outage
      preserves the event.
- [ ] Replay worker: repeated authorized capture, provider outage,
      retry scheduling, worker restart, and a newer capture behind an older
      deferred event (no head-of-line starvation).
- [ ] Real PostgreSQL two-session replay acceptance: hold a captured-payment
      provider read while the first worker owns the webhook row lock; verify
      that a second replay worker and a duplicate signed webhook cannot process
      the same event, emit a second merchant notification or settle twice.
      The automated cases mock Razorpay; sandbox lifecycle remains separate.
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
- [ ] Refund webhook tests: reject missing currency as well as mismatched
      currency; verify that no refund state or settlement changes occur.
- [ ] Razorpay payment-history collection: missing/non-integer/mismatched
      `count`, malformed rows and a full 100-item page fail closed; an
      explicit zero count and a complete short page are accepted.
- [ ] Provider-history integrity: an order-only `order.paid` event with one
      captured payment and a malformed secondary `failed` row (wrong order,
      amount, currency, or missing payment ID) remains pending; a well-formed
      failed retry is accepted. Payment expiration must likewise defer malformed
      failed provider rows and locally mispriced INR/payment attempts instead
      of restoring reserved stock.
- [ ] Failed-payment webhook integrity: reject missing payment/order IDs,
      mismatched amount/currency, non-failed status and order-only failure
      payloads without changing order state; preserve locally captured
      attempt evidence even if a legacy order remains pending.
- [ ] Historical audit tests: unknown local payment provider and unsettled
      secondary Razorpay payments cannot be classified verified; a terminal
      well-formed failed retry can coexist with a verified capture. Flag
      secondary paid attempts missing provider IDs and malformed failed
      provider history even when another capture matches.
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

## PostgreSQL refund concurrency acceptance (development-only)

The test module `backend/tests/test_refund_concurrency.py` uses disposable
PostgreSQL-backed orders and mocked Razorpay calls to verify two critical
interleavings: (1) duplicate refund webhooks serialize on the commercial order
row and reverse settlement only once; (2) a processed refund webhook arriving
while the outbound refund request is in flight survives a later provider
timeout without a second refund request or downgrade of the confirmed outcome;
and (3) competing refund dispatchers claim the obligation once, issuing only
one mocked provider request.
Run this with the backend integration suite against an isolated test database;
never point it at production. CI success proves these simulated interleavings,
not actual Razorpay sandbox lifecycle acceptance or production readiness.

## Cancellation, capture and refund lock-race acceptance (development-only)

The disposable PostgreSQL tests in
`backend/tests/test_cancellation_refund_concurrency.py` hold the commercial
order lock in both directions: cancellation before a processed refund webhook,
and a processed refund webhook before cancellation. They assert neither worker
bypasses the lock, no deadlock occurs, stock is restored exactly once, and
only one settlement reversal is recorded. The same module checks cancellation
versus independently verified capture in both orders: a capture after
cancellation must create a durable refund obligation with the provider payment
ID, not reopen fulfilment or emit a merchant new-order notification; a capture
before cancellation must also leave the obligation. These tests mock provider
reads and settlement side effects; they do not prove real Razorpay sandbox
behaviour. Run them only against the isolated PostgreSQL test database.
