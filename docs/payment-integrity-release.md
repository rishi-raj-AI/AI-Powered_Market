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
    API error; never downgrade `succeeded` to `failed`. A pending webhook
    that identifies the provider refund ID also blocks automatic re-dispatch
    after a conflicting API error.

17. Refund webhooks must explicitly include the expected currency, not merely
    omit a conflicting value. A signed refund event missing currency is not
    sufficient evidence to mark a refund successful; retain the obligation
    for replay/reconciliation.
18. A read-only audit of paid UPI orders must inspect **all** local payment
    attempts, including unexpected providers, and must not report a verified
    capture when Razorpay also reports created, authorized, refunded, or
    unrecognised payments. Terminal failed payments do not by themselves
    invalidate a separately verified capture.

19. A signed webhook event ID must never silently deduplicate a *different*
    signed payload. Conflicting provider event IDs return HTTP 409 without
    applying the second payload, even when the original event was already
    processed. Overlong event IDs are rejected before database insertion.
20. A paid-order audit must flag a locally `paid` payment attempt missing its
    provider payment ID even if another attempt has a matching capture.
    Malformed provider `failed` entries (missing ID, wrong order, amount or
    currency) are not reliable proof of nonpayment and must not be ignored.

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
PostgreSQL-backed orders and mocked Razorpay calls to verify three critical
interleavings: (1) duplicate refund webhooks serialize on the commercial order
row and reverse settlement only once; (2) a processed refund webhook arriving
while the outbound refund request is in flight survives a later provider
timeout without a second refund request or downgrade of the confirmed outcome;
and (3) competing refund dispatchers claim the obligation once, issuing only
one mocked provider request.
Run this with the backend integration suite against an isolated test database;
never point it at production. CI success proves these simulated interleavings,
not actual Razorpay sandbox lifecycle acceptance or production readiness.


## Payment-history identity and refund-event consistency (integrated geography branch)

- Treat Razorpay order-payment history as **indeterminate** when an item has a
  missing, empty or non-string payment ID, references another provider order,
  or repeats a payment ID (even if the collection count matches). Do not use
  such history to expire reservations, restore stock or authorize another UPI
  payment. Investigate the provider response and reconcile before retrying.
- A signed `refund.processed` event requires entity status `processed`; a
  signed `refund.failed` event requires entity status `failed`. Missing,
  unknown or contradictory statuses must leave the webhook unprocessed for
  replay/manual review, not transition the commercial order.
- A later genuine `refund.failed` event must not reverse a previously
  confirmed processed refund. Keep the existing order-first locking and
  payment/refund identity, amount and currency validation.
- These changes are stacked on integrated geography PR #270. The payment-only
  branch #243 includes a temporary geography bypass and must not be merged
  independently. Legacy service-area checks remain authoritative at quote
  and order placement. Territory parity and preview are read-only.

### Review and staging verification (never against production writes)

From a disposable PostgreSQL/PostGIS-backed development or staging test
environment with test-only credentials, run:

```sh
cd backend
python -m pytest -q tests/test_razorpay_payment_history.py tests/test_refund_webhook_integrity.py
python -m ruff check app/api/v1/routes/payment_hardening.py app/services/payments.py tests/test_razorpay_payment_history.py tests/test_refund_webhook_integrity.py
```

Then run the full Backend, Web, Mobile and Production CI workflows on the
**exact PR head SHA**. Test contradictory signed refund outcomes, duplicated
provider payment IDs, COD inside/outside legacy coverage, UPI capture/failure
reconciliation and idempotent checkout retries. Do not enable territory
activation, payment expiry or webhook replay without a separate approval.

### Release/rollback boundaries

No schema migration or new feature flag is introduced in this change.
Deployment requires explicit authorization after staging acceptance and
operator-reviewed rollback readiness. For rollback, revert the application
commit(s) on the integrated release branch and redeploy the previous approved
artifact; do not modify payment/refund records, manually mark orders paid,
replay financial webhooks blindly, or broaden delivery territories. Preserve
the durable webhook ledger and manually reconcile unresolved provider events.
Production diagnosis, staging acceptance and real-device GPS/map-pin testing
remain pending until independently evidenced.

## Integrated capture-binding and provider-history CI gate (PR following #271)

- Before dispatching a refund, require **exactly one** payment-attempt row
  indicating possible capture. It must be Razorpay, `paid`, contain a nonempty
  provider payment ID, use INR, and match the commercial order total. Two
  evidence rows, a missing ID, a contradictory provider or currency, or a
  mismatched amount must leave a durable refund obligation **unbound** for
  manual reconciliation. Do not guess which captured payment to refund.
- An older failed payment attempt without its provider order ID cannot be
  proven unpaid. Reject a new UPI intent with 409 rather than opening a second
  payment window; reconcile provider records first.
- The payment-history count test now supplies the required provider order
  identity in its valid fixture, and explicitly rejects missing, cross-order
  and duplicated payment identities.
- Reject malformed refund API status values (including arrays and objects)
  without throwing a type error or treating them as processed.

### Focused development verification

Run against an isolated, disposable PostgreSQL database with mocked Razorpay:

```sh
cd backend
python -m pytest -q tests/test_payment_history_count_integrity.py tests/test_payment_intent_integrity.py tests/test_refund_capture_binding_integrity.py
python -m ruff check app/services/refunds.py app/api/v1/routes/payments.py tests/test_payment_history_count_integrity.py tests/test_payment_intent_integrity.py tests/test_refund_capture_binding_integrity.py
```

Require all four exact-head CI workflows and then staging payment/refund
acceptance before merge. No production writes or provider calls are permitted.
If a regression is found, revert this integrated application change using the
previous approved artifact, leaving refund obligations, audit records, and
territory configurations untouched. Review all unresolved refund obligations
manually; never compensate by resubmitting a refund without provider proof.


## P0 integrated release review — 2026-11-06 (PR #298)

**Release decision: HOLD.** This section records verified repository evidence, not production or Razorpay sandbox acceptance.

- Candidate: `release/gaonone-p0-integration-review-20261105` at `6935238fd614fbe630239167edb2e6a1d9d527dc`. GitHub Actions Backend, Web, Mobile and Production workflows all completed successfully on this exact SHA.
- Payment source: PR #243 `fix/verify-upi-capture-before-paid` at `ffe1a401a31acaa20c66f699d487096bb344460c`; Backend CI succeeded. **This branch is not merged into the release candidate.** Its latest fixes must be assessed by file and behavior, rather than blindly merging divergent histories.
- The release candidate is based on the stacked geography, checkout-idempotency and PostgreSQL cart-concurrency integration. Passing CI does not prove the separate payment head has been reconciled.

### Mandatory evidence before lifting HOLD

1. Produce a reviewed comparison of payment-sensitive paths (payment routes/services, refund dispatch, webhook ledger/replay, payment audit, migrations and tests) between PR #243 and PR #298. For every missing fix, either port it with focused regression tests or document why it is already covered/superseded. Do not merge divergent branches indiscriminately.
2. Confirm that the temporary delivery-zone bypass is **not active** in the candidate, including serviceability checks at cart quote and COD/UPI POST checkout. Validate confirmed in-territory, unconfirmed and outside-territory coordinates.
3. On a **disposable restored database**, capture Alembic current/heads/history; run forward migrations and the supported rollback rehearsal; verify existing orders, payment attempts, refund obligations, territories and address provenance remain readable. Never run this rehearsal on live production data.
4. Execute PostgreSQL concurrent first-cart creation, cart mutation, idempotent checkout replay and stock consistency tests against the final exact release SHA. Re-run Backend, Web, Mobile and Production CI after every integration change.
5. In Razorpay **test mode only**, validate success, failure, abandonment, provider outage, webhook-first/callback-first, duplicate webhook/payment, late capture after cancellation, refund association and historical read-only audit. Record test identifiers and outcomes without storing secrets or customer data in this document.
6. Before deployment, obtain a verified backup/restore point and an operator-approved rollout plan. Keep `PAYMENT_WEBHOOK_REPLAY_ENABLED=false` and `PAYMENT_EXPIRY_ENABLED=false` unless explicitly approved following backlog review. Do not mark an order paid from client callbacks alone.

### Rollout and rollback decision points

- **Preflight:** record immutable release SHA, review all migration revisions and deployment configuration changes, verify secrets are available to the deployment environment without printing them, verify backups are restorable, and confirm the bypass is absent.
- **Deploy (only after explicit authorization):** use the project's existing production deployment workflow, apply approved migrations with a maintenance/rollback plan, verify health and database connectivity, then run non-mutating checkout/serviceability and payment-state smoke checks.
- **Stop/rollback triggers:** any failed migration, unexpected paid state for failed UPI, accepted out-of-territory order, duplicate settlement, unresolved refund anomaly or elevated checkout error rate. Stop traffic or disable affected capabilities using approved operational controls; restore the previous application image. **Do not automatically downgrade a database with financial writes**: assess schema/data compatibility and use a reviewed forward-fix or restore procedure with a reconciliation plan.
- **Post-rollout:** inspect durable webhook backlog, provider reconciliation discrepancies, checkout errors and fulfilment gates before enabling optional payment workers.

**Unverified as of this review:** sandbox acceptance, production-like migration rehearsal, actual bypass absence, full cross-branch payment parity, and production backup/restore readiness. No deployment or APK generation is authorized.


### Payment parity audit checkpoint — 2026-11-06

The latest verified candidate head before this documentation update is `0dddebc99e`: Backend, Web, Mobile, and Production CI all completed successfully (GitHub Actions runs 42246854384, 42246854545, 42246854410, and 42246854649). These workflow successes do **not** constitute Razorpay sandbox or migration acceptance.

A fresh GitHub comparison of PR #298 against PR #243 still reports diverged history (payment head 204 commits ahead and 177 behind the candidate, 6 November). This is a branch ancestry comparison, **not** a count of missing payment fixes. The payment-sensitive changed-file inventory includes `backend/app/api/v1/routes/{payments,payment_hardening}.py`, `backend/app/services/{payments,payment_expiration,refunds}.py`, `backend/app/scripts/audit_upi_payments.py`, payment/refund regression tests and mobile retry messaging. Each requires behavior-based disposition before release approval.

Initial direct file comparison shows that the release candidate already has stronger validation in several places than the divergent payment branch:

- `payments.py` checks every historical payment attempt for provider, currency, amount, status, provider-payment identity, nonblank provider-order identity and duplicates **before** provider-history I/O. Do not overwrite this with the older branch's narrower initial active-attempt guard.
- `payment_hardening.py` checks the refund entity is a dictionary before reading its fields and explicitly requires a string provider status. Do not regress these checks when porting webhook changes.
- `refunds.py` explicitly requires a string refund status before checking accepted values. Preserve this defensive type check.

This is a **partial parity review**, not proof of complete parity. Next review the remaining behavioral differences and regression tests for capture binding, refund concurrency, payment history, webhook replay and late capture. Any changes must preserve the candidate's stronger existing guards. The temporary territory bypass, migration rehearsal, sandbox tests and production operator acceptance remain unverified.


### Exact-head CI and delivery-gate source review — 2026-11-07

- Verified GitHub Actions for release head `22b141544d`: Backend run [42264253554](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/42264253554), Web [42264253501](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/42264253501), Mobile [42264253499](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/42264253499), and Production [42264253496](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/42264253496) all completed successfully. These are code/CI results, not sandbox, staging, or production acceptance.
- Inspected `backend/app/api/v1/routes/checkout.py` on this head: quote calls `evaluate_delivery` at line 172 and POST checkout calls it again at line 238, rejecting unserviceable destinations before creating an order. This confirms both paths use the same authoritative evaluator in the reviewed source, not that deployed configuration is correct.
- Inspected `backend/app/services/delivery_serviceability.py`: it rejects inactive stores, disabled delivery, missing/inactive store-assigned service areas, missing/invalid hub or address coordinates, unconfirmed GPS/map pins, searched-place centroids and outside-territory locations. It allows historical NULL-provenance coordinates under explicitly documented compatibility behavior. No unconditional bypass was found in these reviewed paths; a repository-wide scan, real PostGIS tests, and staging configuration verification are still required before declaring the temporary bypass absent in all code paths.
- Inspected `backend/alembic/versions/0029_payment_geo_territory_merge.py`: its two parents are `0028_payment_geography_merge` and `0028_delivery_territories`, and it performs no DDL. This is source inspection only, not a successful migration or downgrade rehearsal.
- **HOLD remains in force.** Next: finish PR #243 payment-sensitive parity; test migration graph and disposable restored DB; run PostGIS coverage and concurrent checkout tests on the final changed SHA; complete test-mode Razorpay acceptance; rerun all four CI workflows on that final SHA. Never use production data for rehearsals or enable live payment operations as a substitute for evidence.


### Exact-head CI confirmation and branch-divergence review — 2026-11-07

- PR #298 head `da4ee869e8361363dd7c0c815a2f08fbcf4eb41c` has four completed, successful pull-request workflow runs: [Backend 42273975542](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/42273975542), [Web 42273976006](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/42273976006), [Mobile 42273975633](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/42273975633), and [Production 42273975537](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/42273975537). This is exact-head CI evidence for the head **before this documentation-only commit**; it is not evidence for any later head.
- Comparing `release/gaonone-p0-integration-review-20261105` to `fix/verify-upi-capture-before-paid` shows diverged ancestry (payment branch 204 commits ahead and 180 behind); this is **not** a count of unresolved fixes. The changed-file comparison includes payment routes, services, refund logic, expiration, audit tooling and additional regression tests. Preserve integrated geography and checkout work; reconcile by behavior and test coverage rather than merging branches wholesale.
- Directly inspected `backend/app/api/v1/routes/payment_hardening.py` on both heads. Both versions retain order-before-attempt locking, provider-confirmed capture with strict integer subunit comparison, duplicate-capture rejection, and the refusal to mark an order paid on an uncaptured callback. This is a **limited source parity observation** only; differences elsewhere in this file and the other payment-sensitive paths are not cleared by this inspection.
- **Release HOLD remains:** sandbox capture/failure/abandonment and refund acceptance, disposable restored PostgreSQL/PostGIS migration/rollback rehearsal, repository-wide territory bypass scan, concurrent checkout verification on the eventual final SHA, and operational backup/rollback approval are not established by these workflow results. No production deployment, financial mutation or APK build is authorized.


### Exact-head CI checkpoint — 2026-11-07

- PR #298 head `49250e63cd5b215542c72855fcdb5a56a108ad08`: Backend CI [42282760767], Web CI [42282760754], Mobile CI [42282760759], and Production CI [42282760765] all completed successfully. Links: `https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/<run-id>`.
- GitHub compare at this checkpoint: PR #243 payment branch remains **204 commits ahead and 181 behind** PR #298. This measures divergent history, not missing safeguards. Changed payment-sensitive paths still include payment routes, payment expiration, refunds, provider audit, and numerous tests. No wholesale merge is authorized.
- **HOLD remains:** CI alone does not establish payment behavior parity, a disposable PostGIS migration rehearsal, PostgreSQL race acceptance on final candidate, full territory-bypass audit, Razorpay sandbox scenarios, or operator-approved backup/rollback. The above successful runs apply to the preceding exact SHA; this documentation update requires its own CI verification.
