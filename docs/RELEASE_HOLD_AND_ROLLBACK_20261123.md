# GaonOne P0 release hold and rollback checklist (2026-11-23)

**Status: HOLD.** This is a preparation checklist, not evidence of a successful deployment or rehearsal.

## Exact candidate and CI
- Draft PR #298: https://github.com/rishi-raj-AI/AI-Powered_Market/pull/298
- Candidate inspected: `dbf0868a0c458e9a0c577506ff9cec7c6ad36c0a`
- Backend, Web, Mobile and Production CI reported success on that SHA. Recheck the SHA and all required jobs after **any** commit; prior green CI is not transferable.

## Blocking acceptance
1. `backend/app/services/payment_expiration.py` initializes `cursor = None` on each invocation. The bounded scan can repeatedly revisit deferred provider states. Implement and prove fair progress across invocations, restarts and concurrent workers without skipping eligible orders; replace any strict expected-failure fairness test with a passing regression.
2. Run PostgreSQL-backed checkout, webhook, stock-restoration and expiration concurrency tests (including simultaneous workers, provider outage/recovery, duplicate capture, restart and retry). Preserve order-first locking, provider identity and amount checks, single stock restoration, and refund obligations.
3. Audit checkout and geography code/config for any temporary delivery-zone bypass; demonstrate out-of-zone rejection and valid landmark/in-zone checkout.
4. Verify Alembic upgrade on a fresh and representative **non-production** PostgreSQL database; test downgrade only where migrations are explicitly reversible, otherwise rehearse snapshot restore.
5. With test credentials and an isolated Razorpay sandbox, exercise success, failure, timeout, duplicate webhook, delayed capture, reconciliation and retry. Record sanitized transaction IDs and evidence; do not call live endpoints.
6. Run Backend, Web, Mobile and Production workflows on the **final** immutable SHA, record run links and results, and obtain review of the selectively reconciled PR #243 changes. Do not wholesale merge divergent PR #243.

## Operator preparation (no production action authorized)
- Identify the last known-good deployment commit, immutable image digests, environment configuration and database migration revision.
- Before any later authorized rollout, take an encrypted database backup and record its checksum, timestamp, size, retention location and restore owner. Include object/media backups where applicable. Do not put credentials, personal data or raw payment data in Git.
- On a disposable environment, restore the backup, verify table counts and migration revision, check API health and critical order/payment read paths, and time the restore. Document any incompatibility with forward migrations.
- Prepare a staged rollout with explicit health, order placement, stock, payment and webhook monitoring, alert thresholds and rollback authority. Pause writes/workers only according to an approved operational procedure; never roll back a schema blindly when new writes may exist.
- If acceptance fails after an authorized rollout: stop further rollout, preserve logs and audit trail, evaluate financial in-flight operations, revert application images to known-good digests **only if schema compatible**, and restore the database only under an approved data-reconciliation and recovery plan. Never overwrite production financial records to hide inconsistencies.

## Evidence log
- 2026-11-23: GitHub connector read PR #298 head `dbf0868a0c458e9a0c577506ff9cec7c6ad36c0a`; all four commit-associated workflow conclusions were `success`. PR #243 head `ffe1a401a31acaa20c66f699d487096bb344460c` compared as 204 ahead / 198 behind.
- 2026-11-23: Source inspection confirmed the reset scan cursor and candidate budget. Fairness across repeated invocations remains **unverified**.
- PostgreSQL concurrency, sandbox payment scenarios, geography audit, backup restore and rollback rehearsal: **not executed in this check**.

**Deployment, real payments/refunds, production financial-data mutation, and APK generation are prohibited until separately authorized.**
