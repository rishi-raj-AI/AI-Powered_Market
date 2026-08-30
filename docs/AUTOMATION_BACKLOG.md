# GaonOne Automation Backlog

This is the execution queue for automation-mode development. Tasks are taken in priority order unless a dependency blocks them. A task is complete only after implementation, tests/validation, review, and green CI.

## Wave 0 — Automation and staging foundation

- [x] A00 Define persistent agent engineering contract in `AGENTS.md`.
- [x] A01 Define delivery-first master architecture and product boundary.
- [x] A02 Reclassify current deployment server as staging.
- [x] A03 Keep `main` as the only deployable integration branch.
- [x] A04 Preserve CI release gates before staging deployment.
- [x] A05 Preserve exact-SHA deployment, pre-deploy backup, smoke checks, monitoring, and deployed-SHA state.
- [x] A06 Record previous deployed SHA before each staging release.
- [x] A07 Validate staging workflow end-to-end after this PR reaches `main`.

## Wave 1 — Delivery lifecycle hardening

- [x] D01 Centralize order transition rules and tests.
- [x] D02 Correct assignment semantics: claiming a delivery must not mark the order `OUT_FOR_DELIVERY`.
- [x] D03 Move order to `OUT_FOR_DELIVERY` only on confirmed pickup.
- [ ] D04 Add delivery failure workflow with explicit failure reason/evidence.
- [ ] D05 Add proof-of-delivery model/API with OTP/evidence-ready design.
- [ ] D06 Add reassignment/cancellation rules for delivery partners.
- [x] D07 Add transition/audit events for material order and delivery changes.
- [ ] D08 Add end-to-end tests for customer → merchant → rider → delivered flow.

## Wave 2 — Checkout, inventory and idempotency

- [ ] C01 Lock inventory rows during checkout to prevent overselling.
- [ ] C02 Add checkout idempotency key support.
- [ ] C03 Guarantee stock restoration is idempotent on cancellation.
- [ ] C04 Harden payment/order side-effect boundaries.
- [ ] C05 Add duplicate-request and concurrent-checkout tests.

## Wave 3 — Geography and dispatch

- [ ] G01 Audit current geography schema and PostGIS usage.
- [ ] G02 Move production store-nearby/serviceability queries to indexed PostGIS operations.
- [ ] G03 Add explicit delivery/service area rules.
- [ ] G04 Add delivery-partner availability/location eligibility.
- [ ] G05 Implement dispatch V1: nearest eligible available partner.
- [ ] G06 Add dispatch tests including no-partner and race conditions.

## Wave 4 — Tracking, payments and settlement

- [ ] T01 Harden live tracking authorization and event validation.
- [ ] T02 Add stale-location and impossible-coordinate safeguards.
- [ ] P01 Audit payment webhook signature/idempotency behavior.
- [ ] P02 Model COD collection separately from commercial payment status where required.
- [ ] P03 Introduce settlement ledger foundation for merchant/delivery payouts.

## Wave 5 — Product applications

- [ ] U01 Customer order lifecycle UI against hardened APIs.
- [ ] U02 Merchant acceptance/preparation/readiness workflow.
- [ ] U03 Delivery-partner assignment/pickup/tracking/POD workflow.
- [ ] U04 Admin operations view for orders, deliveries, exceptions and refunds.
- [ ] U05 Low-bandwidth/offline-tolerant behavior for rural delivery operations.

## Wave 6 — Scale and intelligence

- [ ] S01 Observability/correlation IDs across order-delivery-payment lifecycle.
- [ ] S02 Outbox/event reliability for notifications and asynchronous side effects.
- [ ] S03 Dispatch scoring and batching.
- [ ] S04 ETA and delivery performance analytics.
- [ ] S05 Multilingual/voice ordering and merchant catalog assistance.

## Execution rule

Do not skip ahead to UI polish while a lower-wave correctness or reliability task is incomplete. Exceptions require an explicit dependency reason recorded in the PR/task summary.
