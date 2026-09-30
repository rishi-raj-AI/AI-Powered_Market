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
| R-011 | Weak-connectivity UX fails in field | P1 | Medium | Yes | Engineering | PARTIAL: web rejects stale location/discovery responses, serializes conflicting cart/address/support/payment-intent actions, replays a same-key support ticket safely, and preserves confirmed address/ticket state after list refresh failure; payment intent, verification, and webhook now use one Order→PaymentAttempt lock order; Android field QA and durable retry behavior across a full client restart remain |
| R-012 | Android build/device instability | P1 | Medium | Yes | Engineering/owner | OPEN: build and device validation |
| R-013 | No visual QA evidence | P1 | High | Yes | Engineering | OPEN: capture critical-screen evidence |
| R-014 | Protected main edits damaged | P0 | Low | Yes | All | CONTROLLED: never clean/reset/stash main |
| R-015 | Risky worktrees corrupted | P1 | Medium | No | All | OPEN: preservation-only; no repair without authority |
| R-016 | Pinned Next.js framework version has a critical ImageResponse dependency advisory | P0 | Medium | Yes | Engineering | IN PROGRESS: production audit identified direct `next` `16.3.3` as GHSA-vcvr-r3jv-pc5j-affected; no source imports `next/og` or `ImageResponse`, and the minimal `16.3.8` patch resolves the production audit to zero findings pending required CI |
