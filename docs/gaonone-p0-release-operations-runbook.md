# GaonOne P0 release: backup, rollback and acceptance runbook

Status: **HOLD**. This document is a preparation checklist, not evidence that any step has been executed. No production deploy, real payment/refund, production financial-data mutation, or APK build is authorized by this runbook.

## Immutable release candidate and evidence

1. Record the full Git SHA of PR #298 and freeze the release candidate. Confirm Backend, Web, Mobile and Production CI all completed successfully **for that same SHA**, after the final code change. Save run URLs and job logs.
2. Verify migration heads with Alembic on a disposable PostgreSQL/PostGIS database. Inspect the merge migration `0029_payment_geo_territory_merge.py` and its two parent revisions; do not assume downgrade support. Run upgrade, schema/data assertions, and a downgrade/restore rehearsal against disposable data only.
3. Independently run two-session PostgreSQL checkout, inventory, cancellation and refund concurrency tests using disposable records and mocked provider I/O. Capture the command, environment, SHA, test count and result.
4. **Unpaid-UPI expiry scanner fairness blocker:** `backend/app/services/payment_expiration.py` starts `cursor = None` on every invocation and bounds scans to at most 5,000 candidates (500 for `limit=1`). A permanent prefix of deferred orders can therefore starve later eligible reservations indefinitely, even though pagination advances inside one call. Before enabling `PAYMENT_EXPIRY_ENABLED`, implement concurrency-safe cross-invocation progress or durable retry scheduling. Acceptance must demonstrate, on disposable PostgreSQL with 500+ older deferred rows and `limit=1`, that a later provably unpaid order is eventually processed across repeated invocations; include concurrent-worker behavior, rollback/restart behavior, and no duplicate stock restoration or incorrect paid/cancelled transitions. Preserve order-first locking, provider-history checks, and conservative deferral on uncertain money movement.
5. Review all checkout/COD/UPI entry points for the historical temporary delivery-zone bypass. Test in-zone confirmed, unconfirmed, out-of-zone, legacy NULL-provenance, and missing/invalid location cases. Record the expected and observed results; do not replace authoritative serviceability checks with a permissive fallback.
6. Reconcile PR #243 by behavior and tests only. Do not merge its divergent history wholesale. Execute Razorpay **test-mode** scenarios only when sandbox credentials and isolated callbacks are available: capture, failure, dismissal, retry, duplicate/late capture, webhook replay/collision, expiry and refund obligation. Verify that failed/uncaptured attempts never mark orders paid.
7. Run read-only payment reconciliation against a safe staging copy, with secrets redacted; resolve every discrepancy before approval.

## Operator preparation (do not execute without separate authorization)

- Record deployment owner, maintenance window, rollback decision maker, incident channel, last-known-good application image digests, migration revision(s), and all environment/feature-flag values. Preserve disabled-by-default payment expiry/webhook replay behavior unless explicitly tested and approved.
- Take an encrypted, access-controlled, timestamped database backup using the operator's established PostgreSQL backup mechanism. Record database identity, server version, PostGIS extension version, backup size/checksum, retention location and restore owner. Never print secrets or include payment credentials in logs.
- **Restore the backup into a new isolated disposable database** and verify schema, row counts, foreign keys, order/payment/refund invariants, PostGIS queries, and application read-only smoke checks. A successful backup command alone is not a verified restore.
- Establish a rollback trigger: incorrect paid status, duplicate capture/refund, missing stock restoration, wrong delivery-zone eligibility, migration error, or critical error-rate regression. Halt traffic/financial workers safely per operator plan; preserve forensic logs and idempotency state.
- Application rollback means redeploying the recorded last-known-good image and configuration. Database rollback must be selected only after examining forward writes and migration compatibility: **never blindly restore an old database over new paid orders/refunds**. Prefer an explicitly reviewed forward-fix or controlled recovery that preserves financial history. Require operator and payment-reconciliation signoff before reopening writes.
- After authorized deployment, perform read-only checks first, then operator-approved controlled COD/test-mode payment scenarios. Compare order, inventory, payment-attempt and refund-obligation records. Record outcome and responsible signatories.

## Acceptance record

| Gate | Evidence required | Status |
| --- | --- | --- |
| Four exact-SHA CI workflows | URLs, SHA and conclusions | Reverify at final head |
| PostgreSQL/PostGIS upgrade and restore | Disposable DB logs | Unverified |
| Checkout/refund concurrency | Two-session test logs | Unverified |
| Expiry scanner fairness | Passing repeated-invocation PostgreSQL regression and concurrent-worker/restart evidence | Known blocker |
| Territory bypass audit | Entry-point inventory and negative tests | Unverified |
| Razorpay sandbox | Redacted test-mode traces | Blocked until environment verified |
| Backup and rollback rehearsal | Isolated restore report and operator approval | Unverified |

This document does **not** authorize running the operator steps. Keep the PR in draft/HOLD until code-level gates pass; operator-only staging/production acceptance remains separate.

## Verified repository checkpoint — 2026-11-18

- Release branch HEAD: `190416d90e74376ef679ed63705f664b480bc501` **before this documentation-only update**. GitHub Actions reported success for Backend CI [run 44162523156](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/44162523156), Web CI [run 44162523154](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/44162523154), Mobile CI [run 44162523178](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/44162523178), and Production CI [run 44162523171](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/44162523171). These results **do not** certify the new documentation commit or a future corrected code SHA.
- Direct comparison against PR #243 branch `fix/verify-upi-capture-before-paid`: **204 ahead / 194 behind** relative to release branch, with 65 changed files. The payment branch's `payment_expiration.py` also resets `cursor = None` per invocation; importing that version does **not** fix cross-run fairness. Selectively review payment-specific behavioral gaps and tests, not the branch history.
- Release test `backend/tests/test_payment_expiration_cross_run_fairness.py` remains `xfail(strict=True)` with 501 older deferred orders. This is a known failing acceptance target, not a successful regression. No new PostgreSQL concurrency, Razorpay sandbox, territory negative-path, migration rollback, or isolated backup/restore evidence was collected in this checkpoint.
- **HOLD remains in force.** The next engineering work is a durable cursor/retry schedule with safe multi-worker coordination, explicit restart behavior and passing PostgreSQL tests, followed by all four workflows on the exact corrected release SHA. Do not enable payment expiry based on the historical green runs.
