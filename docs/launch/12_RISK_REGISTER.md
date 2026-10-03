# Risk register

| ID | Risk | Severity | Likelihood | Launch blocker | Owner | Status / mitigation |
|---|---|---:|---:|---|---|---|
| R-001 | Main push can trigger staging deployment | P0 | Medium | Yes | Engineering/owner | MITIGATED: Phase 2A merged; workflow is manual-dispatch only |
| R-002 | Firebase server credentials/config unavailable | P0 | Medium | Yes | Owner | OPEN: secure owner setup checklist |
| R-003 | Web OAuth origins missing | P0 | Medium | Yes | Owner | OPEN: configure verified launch origins |
| R-004 | Android SHA/package Firebase config missing | P0 | Medium | Yes | Owner | OPEN: configure and test release/debug boundaries |
| R-005 | iOS Google Sign-In/config/signing incomplete | P0 | Medium | Yes | Owner | OPEN: configure and device-test |
| R-006 | Existing-account linking creates duplicates | P0 | Medium | Yes | Engineering | MITIGATED: UID-only first login; no automatic email linking |
| R-007 | OTP/dev OTP becomes exposed in production | P0 | Low | Yes | Engineering | MITIGATED: explicit SMS route gate and production config tests |
| R-008 | Production CORS/domain configuration incomplete | P1 | Medium | Yes | Owner | OPEN: configuration audit |
| R-009 | Maps configuration absent | P1 | Medium | Conditional | Owner | OPEN: assess critical routes and degraded UX |
| R-010 | Razorpay credentials absent | P1 | High | No, COD path | Owner | OPEN: COD remains the launch path; source recovery makes both an existing pending UPI order and a newly created UPI order whose initial intent is unavailable provider-neutral and retry-safe while credentials are absent; owner provisioning and launch decision remain required |
| R-011 | Weak-connectivity UX fails in field | P1 | Medium | Yes | Engineering | PARTIAL: web rejects stale location/discovery responses, serializes conflicting cart/address/support/payment-intent actions, replays a same-key support ticket safely, preserves confirmed address/ticket state after list refresh failure, and retries a transient signed payment confirmation only in the current page without opening another intent; payment intent, verification, and webhook use one Order→PaymentAttempt lock order. Android field QA and durable retry behavior across a full client restart remain |
| R-012 | Android build/device instability | P1 | Medium | Yes | Engineering/owner | OPEN: build and device validation |
| R-013 | No visual QA evidence | P1 | High | Yes | Engineering | OPEN: capture critical-screen evidence |
| R-014 | Protected main edits damaged | P0 | Low | Yes | All | CONTROLLED: never clean/reset/stash main |
| R-015 | Risky worktrees corrupted | P1 | Medium | No | All | OPEN: preservation-only; no repair without authority |
| R-016 | Pinned Next.js framework version has a critical ImageResponse dependency advisory | P0 | Medium | Yes | Engineering | MITIGATED: security PR #195 merged at `168a496` after all four required gates passed on final head `bdbfbfb`; direct `next` is `16.3.8` and audit no longer reports GHSA-vcvr-r3jv-pc5j |
| R-017 | Firebase package transitively installs an advisory-affected `@grpc/grpc-js` | P1 | Low | No known GaonOne runtime path | Engineering | MITIGATED: security PR #196 merged at `2b5b124` after all four required gates passed on final head `9ba269a`; the version-scoped override changes only resolved vulnerable `@grpc/grpc-js@1.9.16` to fixed `1.13.6`. npm 10.9.2 clean install and production audit are clean; source imports only client Firebase app/auth, not Firestore or a gRPC server. Revisit only when Firebase supplies a compatible dependency range |
| R-018 | Suspending then reapproving a merchant could overwrite merchant store availability and reopen intentionally paused stores; the admin overview could count stores of suspended merchants | P1 | Medium | Yes | Engineering | MITIGATED: PR #199 merged at `99f10e` after all four required CI gates passed on final head `811faac`; platform status gates eligibility without mutating `Store.is_active`, and overview requires an approved merchant. No deployment. |
| R-019 | A normal or super admin can enumerate full household delivery-task PII through a rider-self endpoint, contrary to the assigned-rider contract | P1 | Medium | Yes | Engineering | IMPLEMENTED IN BRANCH: `/delivery/tasks/me` is delivery-role-only and assignment-scoped; scoped admin dispatch and operations endpoints remain. Python compilation, focused Ruff, and diff checks pass locally; focused review and all four required CI gates remain before merge; no migration or deployment. |
