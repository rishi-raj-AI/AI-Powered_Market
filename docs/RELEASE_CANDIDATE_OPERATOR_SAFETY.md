# GaonOne release candidate — operator safety and rollback checklist

Status: **HOLD**. This document is a procedure, not evidence that release gates passed.

## Preconditions (all required)
- Record exact release commit SHA, four CI run URLs (backend, web, mobile, production), migration revision, container image digests and configuration checksum. All must correspond to the **same final commit**.
- Prove the cross-invocation UPI expiration fairness regression passes without xfail on PostgreSQL, including restart and two-worker contention. Keep automatic expiration disabled until sandbox and operator approval.
- Validate payment capture, failed/authorized/pending states, webhook replay, duplicate attempts, partial failure, timeout, refund obligations and COD isolation using **sandbox only**. Do not substitute mocks for provider acceptance.
- Verify checkout concurrency, inventory restoration exactly once, delivery-radius boundaries, landmark/address normalization and absence of temporary delivery-zone bypass in the release artifact.
- Apply migrations to a disposable PostgreSQL restore, validate forward/backward compatibility and rollback strategy. Destructive migrations require an explicit data-recovery plan, not an assumed downgrade.
- Obtain explicit release authorization separately. This runbook does not authorize deployment, payment/refund execution, production data changes or APK distribution.

## Backup and rehearsal
1. Freeze the release SHA and record database schema revision, images, environment keys (names only), routing configuration and feature flags. Never put credentials in logs or this document.
2. In an isolated test environment, take a consistent PostgreSQL custom-format backup using `pg_dump -Fc`; separately inventory object/media storage and external secrets/configuration. Confirm backup completion and access controls.
3. Restore with `pg_restore` to a fresh **disposable** database. Validate table counts, constraints, critical payment/order/stock relationships, migration history and application startup. Do not restore over production.
4. Rehearse migration and rollback against that restored copy; record duration, errors, checksums, and an operator-approved maximum recovery window.
5. Test old and new application versions against migration boundaries. Prefer expand/contract migrations; never assume reverse migration is safe for financial records.

## Deployment procedure — only after separate authorization
1. Announce maintenance/monitoring ownership and freeze writes if migration compatibility requires it.
2. Confirm fresh backup and tested restore, exact image digests, CI evidence, credentials, and feature flags. Keep automatic UPI expiration disabled by default.
3. Apply only approved migrations, then deploy the pinned images. Check API health, order creation, COD, delivery eligibility, payment status transitions, worker queues and audit/outbox integrity.
4. Monitor error rates, pending payment obligations, inventory reconciliation and webhook retries. Avoid live payment/refund tests unless explicitly authorized.

## Abort and rollback
- **Abort** on migration mismatch, missing backup evidence, checkout geography regression, incorrect paid status, duplicate stock restoration, provider ambiguity, or unexplained financial-state divergence.
- Stop new rollout; preserve logs and audit evidence. Disable unsafe background workers/feature flags without deleting queues or obligations.
- Roll back to pinned compatible application images **only if schema compatibility is demonstrated**. If migration is irreversible, use the rehearsed forward-fix or restore plan with an explicitly approved recovery window and data reconciliation.
- Never overwrite newer production financial data with an older backup without an operator-led reconciliation plan for intervening orders, captures, refunds and webhooks.
- Re-run smoke tests and reconcile order, payment, stock, settlement and outbox counts before declaring recovery.

## Evidence ledger
- Previous release candidate: `2e293bd651f01e632f968e71cf34f5e6286ea2fa`; four CI workflows succeeded on this older SHA. This is **not** acceptance of a corrected candidate.
- Known blocker: `backend/tests/test_payment_expiration_cross_run_fairness.py` is strict xfail; scanner restarts at the beginning on every invocation.
- PR #243 diverges from PR #298 and must be reconciled selectively, not merged wholesale.
- PostgreSQL fairness/restart/multi-worker, provider sandbox, migration rehearsal, delivery-zone verification and backup/restore acceptance: **not verified in this checklist**.

Owner sign-off and dated evidence links must be added before changing status from HOLD.
