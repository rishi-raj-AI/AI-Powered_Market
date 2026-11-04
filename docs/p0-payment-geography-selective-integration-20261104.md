# P0 payment/geography selective integration gate (2026-11-04)

## Evidence snapshot
- Geography draft PR #283 head: `57c9db4e3569d276ca9ea863ceb1bf9d8883f6af`; Backend, Web, Mobile and Production CI successful for this exact SHA (runs 41741664849, 41741664667, 41741664771, 41741664762).
- Payment candidate branch: `fix/p0-integrated-payment-capture-binding-20261103`. GitHub compare from geography head reports diverged, **6 ahead / 44 behind**, merge base `e5d1371b6d107e056e3eaa6cdff4ea40d84d07ba`.
- Payment candidate changes: `backend/app/api/v1/routes/payments.py`, `backend/app/services/refunds.py`, `backend/tests/test_payment_history_count_integrity.py`, `backend/tests/test_payment_intent_integrity.py`, `backend/tests/test_refund_capture_binding_integrity.py`, `docs/p0-integrated-capture-binding-acceptance.md`.
- Inspected geography-side `delivery_serviceability.py`: the evaluator uses assigned active service areas, rejects missing/unconfirmed new coordinates, and permits legacy NULL-provenance coordinates only under compatibility rules. No evidence here that production configuration is correct.
- Inspected geography-side `payments.py`: payment-intent creation locks the commercial order, rejects non-UPI and ineligible payment/order statuses; `refunds.py` binds refunds to a unique captured attempt and keeps obligations when evidence is ambiguous.

## Selective integration sequence (not yet executed)
1. Freeze both source SHAs and inspect **full** payment candidate diffs against geography, especially payment capture identity, refund dispatch, row-lock ordering, and retry semantics. Do not blindly merge diverged histories.
2. Create a new branch from geography head; selectively port only reviewed payment capture-binding and refund changes plus associated tests, preserving geography evaluator and transactional checkout recheck. Exclude PR #242 temporary service-area/radius/coordinate bypass and any equivalent behavior from PR #243.
3. Require tests on combined head: valid in-zone confirmed GPS/map pin and legacy coordinate COD success; out-of-zone confirmed pin and legacy coordinate rejection; unconfirmed GPS/map pin rejection; missing territory, inactive territory, disabled delivery, boundary and overlap; rejected checkout creates no order or payment intent.
4. Payment acceptance on combined head: failed/cancelled UPI must never mark paid or fulfil; provider-verified capture and amount/currency/order binding; webhook replay and duplicate event idempotency; provider outage remains pending reconciliation; no duplicate refunds; concurrent cancellation/capture/refund row-lock cases; COD remains independent of UPI.
5. Run Backend PostgreSQL/PostGIS CI, Web, Mobile and Production CI on **exact combined SHA**. Record run URLs and conclusions. Run staging-only sandbox Razorpay lifecycle and Android GPS/pin real-device checks before any release approval.
6. Authorized production diagnosis, if separately approved: use existing scoped read-only diagnostic with a read-only database role and a single store/address pair. Do not expose coordinates, names or tokens in logs. No production mutation, territory publication, deployment or APK publication in this PR.
7. Deployment preparation only: snapshot approved SHA and migrations, verify restorable DB backup, preserve env/Caddy, document rollback to previous image and schema-compatible state, then obtain separate operator approval. Do not roll back by deleting volumes or overwriting secrets.

## Acceptance state
This document is a reconciliation checklist, **not** proof of a combined build or a production root cause. No payment source code has been ported and no combined-head tests have been run by this documentation change. Production diagnosis, staging COD/UPI, physical Android, and release approval remain pending.
