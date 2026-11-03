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

23. A retry must never expose an existing Razorpay payment order or
    create a replacement order solely because GaonOne still says PENDING or
    FAILED. Under the commercial order lock, inspect **every** previous
    attempt: reject unknown providers, mismatched terms, local capture evidence
    and any provider payment that is not a well-formed terminal failure.
    Provider read failures and incomplete histories defer checkout instead
    of inviting a duplicate charge. Empty histories and verified terminal
    failures may safely reuse the same intent or create a new one.

24. A historical payment attempt missing its provider order ID is not
    safely retryable, even when its local status is `failed`. Without that
    identity GaonOne cannot ask Razorpay whether the earlier payment captured;
    quarantine the commercial order before reusing or creating an intent.
25. An automatic refund must bind to exactly one local captured-payment
    evidence row, with paid status, provider payment ID, Razorpay provider,
    matching commercial total and INR currency. A second capture-evidence
    row (including a locally failed row carrying a payment ID) or inconsistent
    single row creates an unbound refund obligation for manual reconciliation,
    not a guessed provider refund target.

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
- Pending/failed UPI triage (read-only; staging copy only):
  `python -m app.scripts.audit_upi_payments --unpaid --limit 100 --days 30`.
  Review `unexpected_capture`, `multiple_captures`,
  `local_capture_evidence`, `provider_unavailable`,
  `payment_history_mismatch`, and `provider_ambiguous` before
  reattempting payment or expiring stock. `no_capture_found` is only a
  point-in-time provider observation, **not** proof that a customer cannot
  later complete an authorized checkout window. This tool never initiates
  payments/refunds or changes orders, inventory, or financial records.
  Both audit modes reject non-integer captured paise values; duplicate local
  payment/order identities are treated as inconsistent evidence.

## Pre-release validation

- [ ] Backend CI lint, migration checks and full pytest suite green,
      including Alembic upgrade/downgrade of revision 0027.
- [ ] Web CI and Flutter analysis/tests green.
- [ ] Web and Flutter Orders/Checkout show reconciliation-specific
      guidance on HTTP 409 and provider-read failures (502/503): the order is
      saved, payment is not confirmed, and the customer should check status
      before attempting another charge. Confirm no UI marks a pending UPI
      order paid or invites a blind retry. Flutter message regression tests
      must pass without building an APK.
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
- [ ] A payment-intent retry with two active local provider orders, or an
      active attempt lacking its provider order ID, is quarantined for manual
      reconciliation before any new provider request or checkout window.
- [ ] Website intent-error recovery refreshes the order before offering a
      retry: a concurrent webhook capture must replace stale pending UI with
      a verified-paid state; a 502/503 provider outage must warn against
      blindly paying twice. Run the Playwright scenario on all browser targets.
      Simulate an older manual refresh resolving *after* a newer verified-paid
      refresh; the stale pending response must not reopen Pay now. Key the
      webhook race fixture to the intent request, not a GET request count.

- [ ] Intent retry provider-history acceptance: captured, authorized,
      created, refunded, unknown and malformed failed provider payments block
      both reusing an active intent and creating a new one after a local
      failure. A provider outage defers retry; verified empty/terminal-failed
      histories allow retry. An older unsettled attempt cannot be hidden by a
      newer active attempt. Mock all provider I/O in automated tests.
- [ ] New provider order responses must contain a nonempty string ID, exact
      integer amount in paise and INR currency. Any missing/mismatched field
      blocks checkout intent creation without recording a local payment attempt.
- [ ] Intent retries on legacy inconsistent orders: captured local attempt
      with order-level PENDING/FAILED, stale provider amount/currency, already
      paid/refunding/refunded or non-PLACED orders must fail closed. Test both
      direct routes and HTTP responses using disposable records.
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
      A signed `refund.processed` event must report a processed entity, and
      `refund.failed` must report a failed entity. Unknown or contradictory
      statuses remain unprocessed for replay/reconciliation; a correctly
      labelled late failure must never downgrade a completed refund.
- [ ] Razorpay payment-history collection: missing/non-integer/mismatched
      `count`, malformed rows, missing/non-string payment IDs, duplicate IDs
      (including contradictory captured/failed records), entries belonging to
      another provider order and a full 100-item page fail closed; an explicit
      zero count and a complete short page with distinct, matching payment
      identities are accepted. No duplicated row may mask an omitted capture
      during payment retry, order-only webhook reconciliation, expiration or
      the read-only historical audit.
- [ ] Authoritative capture amount types: reject float, string, boolean and
      missing paise values even when Python numeric equality would match.
      Neither callback verification nor expiration reconciliation may mark
      the order paid or release merchant fulfilment on malformed evidence.
- [ ] Signed capture webhooks with mismatched authoritative provider
      evidence remain unprocessed in the durable ledger and retry on the
      bounded backoff schedule; a later corrected provider read can settle
      exactly once. Never permanently acknowledge a mismatched capture.
- [ ] Expiration must defer any locally authorized, processing, refunded or
      unknown payment-attempt status even if provider history is empty; do
      not restore stock until all local and provider evidence is unambiguous.
- [ ] Provider-history integrity: an order-only `order.paid` event with one
      captured payment and a malformed secondary `failed` row (wrong order,
      amount, currency, or missing payment ID) remains pending; a well-formed
      failed retry is accepted. Payment expiration must likewise defer malformed
      failed provider rows and locally mispriced INR/payment attempts instead
      of restoring reserved stock.
- [ ] Failed-payment webhook integrity: reject missing payment/order IDs,
      mismatched amount/currency, non-failed status and order-only failure
      payloads without changing order state; preserve locally captured
      attempt evidence even if a legacy order remains pending. A valid failure
      on a *different* attempt must not downgrade a stale PENDING order when
      another attempt has either PAID status or a provider payment ID.
- [ ] Capture verification must quarantine a second attempt when any
      different attempt has partial local capture evidence: either PAID status
      without a provider payment ID or a provider payment ID without PAID
      status. Neither case may create another settlement or mark the order paid.
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
- [ ] Run read-only `--unpaid` triage on a staging copy: detect provider
      captures while orders remain PENDING/FAILED, multiple captures,
      local capture evidence, missing provider orders, unknown local states,
      provider outages, and nonterminal payment histories. Do not interpret
      `no_capture_found` as authorization to retry/expire a live checkout.
      A provider failed-payment history with missing, non-string, empty, or
      duplicated payment IDs must be classified `payment_history_mismatch`,
      not `no_capture_found`. Verify tests leave order and payment records
      unchanged; read-only audit tests must re-query persisted state using a
      fresh session after the audit closes its own session.
- [ ] Payment-intent retry preflight must validate **every** local attempt
      (provider, currency, amount, status, payment evidence, and nonblank,
      unique Razorpay order identity) before any Razorpay history read.
      A later malformed/unknown/failed attempt must block a new checkout
      even if an earlier attempt has a valid provider order. Test this with
      mocked provider I/O and disposable PostgreSQL records. A previous CI
      failure at `c79dfb0` exposed the order-dependent validation gap;
      recheck Backend CI after the two-phase validation fix.
- [ ] Read-only paid audit must quarantine duplicate provider-history payment IDs, including a captured/failed pair sharing the same ID; a single valid capture must not conceal duplicated rows returned by a historical adapter. Unpaid audit must reject whitespace-only provider order IDs and duplicate local provider-order identities rather than reporting `no_capture_found`. Verify using mocked provider responses and disposable database records.
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


### Nonempty staging reconciliation acceptance

For a staging dataset seeded with known eligible paid and unpaid UPI orders, run both read-only audits with `--fail-on-review --require-scanned`. `--fail-on-review` exits 2 on findings requiring review; `--require-scanned` exits 3 if the selected cohort is empty. An empty report must not be interpreted as successful payment verification. These options do not mutate payment or inventory records. If the staging cohort is intentionally empty, omit `--require-scanned` and record that coverage was not exercised; do not approve release on that basis.

```bash
python -m app.scripts.audit_upi_payments --limit 100 --days 30 --fail-on-review --require-scanned
python -m app.scripts.audit_upi_payments --unpaid --limit 100 --days 30 --fail-on-review --require-scanned
```


### Single-command strict staging audit

Use `--strict --summary-only` on both paid and unpaid cohorts to enforce all three
release gates while keeping individual order numbers out of CI logs. Strict
mode exits 2 for review findings, 3 for an empty cohort, and 4 for truncated
coverage (in that precedence order). Exit 0 requires a nonempty, fully scanned
cohort with no review findings; it does **not** replace manual Razorpay sandbox
acceptance or the independent staging reconciliation sign-off.

```bash
python -m app.scripts.audit_upi_payments --limit 1000 --days 30 --strict --summary-only
python -m app.scripts.audit_upi_payments --unpaid --limit 1000 --days 30 --strict --summary-only
```

If either cohort exceeds 1000 orders, partition the staging review into
documented nonoverlapping time windows or extend the audited tooling with
pagination before approving the release; do not treat a truncated scan as
complete. No payment, refund or stock writes are performed by these commands.


### Combined paid and unpaid staging gate

The read-only `--both` option checks both cohorts with one invocation. It
requires **each** cohort to be nonempty under `--strict`, and fails when
either cohort has review findings or exceeds its own `--limit`. The JSON
report retains separate paid/unpaid counts; `--summary-only` removes
order-level findings from both nested cohorts. `--both` and `--unpaid`
cannot be combined. The date window and limit apply independently to each
cohort, and a single invocation is not a transactionally consistent snapshot
of concurrent payment changes. Use a quiescent isolated staging dataset and
retain the independent provider reconciliation sign-off.

```bash
python -m app.scripts.audit_upi_payments --both --limit 1000 --days 30 --strict --summary-only
```
