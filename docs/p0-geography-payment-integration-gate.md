# P0 geography/payment integration gate (2026-11-05)

This branch starts at geography PR #290 head `9a200066e4bc5c5acc9d527c6b390cd0d0852efb`. It does **not** contain payment PR #243 changes yet. Do not merge or deploy it as an integrated fix.

## Source isolation

- Geography stack: PRs #287–#290; preserve confirmed-location and PostGIS serviceability checks at quotation **and** POST checkout.
- Payment PR #243: head `3f5718636aff536fe3516e6ae573df7f76312f60`, base `fix/temporary-delivery-zone-bypass`. Do not merge that branch or its bypass ancestry.
- GitHub compare of the two heads reports **diverged** (payment head ahead 185, behind 158). These counts are Git ancestry, not a conflict-free patch count.
- Review each payment commit/diff and transplant only necessary payment-integrity changes to this geography-derived branch. Resolve checkout, migration, refund and webhook changes manually; no wholesale merge or unreviewed cherry-pick.
- Check for concurrent changes from the hourly payment-fix workflow before each integration commit.

## Acceptance matrix (isolated test database and Razorpay sandbox only)

| Case | Required outcome |
| --- | --- |
| Confirmed in-territory GPS/map pin, COD | One order; inventory reserved once; idempotent replay |
| Confirmed in-territory GPS/map pin, UPI | Order/payment pending until authoritative captured payment verified |
| Unconfirmed GPS/map pin/search result | Explicit serviceability rejection before order, stock or cart mutation |
| Outside/inactive/unassigned territory | Reject even with otherwise valid payment request |
| Failed/cancelled UPI or forged client success | Never mark paid or authorize fulfilment |
| Valid captured UPI, matching amount/currency/order | Exactly-once transition to paid, safe retries and webhook races |
| Duplicate/late webhook, conflicting payment identity | No duplicate settlement or fulfilment; durable audit |
| Refund provider timeout or ambiguous response | Keep reconciliation obligation; never blindly retry money movement |
| Same idempotency key with altered cart/payment/address | Reject conflict; never create a second order |
| Legacy coordinate provenance | Preserve documented compatibility without silently trusting unconfirmed new pins |

Run backend PostgreSQL/PostGIS integration tests, web and Flutter tests, migration upgrade/downgrade review, concurrency tests and CI on the **exact integration head**. Staging payment capture/refund acceptance and physical Android GPS tests are separate gates; green unit CI is insufficient.

## Production boundary and rollback

No production queries or changes are executed from this branch. Authorized operator may run only a reviewed, scoped, read-only diagnostic under a SELECT-only role, with bounded rows and redacted coordinates/customer identifiers. Do not enable the temporary delivery-zone bypass or weaken legitimate coverage.

Before any later authorized release: backup and verify PostgreSQL restore readiness, snapshot existing environment and feature flags, review forward/backward migration compatibility, and record the prior deployed image/commit. Deploy only after explicit authorization; rollback app images and feature flags first, and never blindly reverse a data-bearing migration. Confirm payment reconciliation before any financial repair.

**Current status:** integration implementation, combined CI, sandbox, operator production diagnosis and device acceptance are pending.
