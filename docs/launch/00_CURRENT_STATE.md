# Current state

Verified 2026-10-01 UTC.

| Item | Verified state |
|---|---|
| Local main / origin/main | Both `168a49601386d4fd08dd4d3ccd5e38a4dcc464e4` |
| Baseline CI | `backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images` passed for security PR #195 final head `bdbfbfb63513830d0dc1b551af5f4bbf0875d8e4` before merge |
| Open PR | None — the R-017 Firebase transitive-dependency remediation is isolated locally on `chore/firebase-grpc-security`; required CI must be evaluated only after a PR is opened on its final branch head |
| Main checkout | Protected owner Flutter/iOS modifications exist; do not reset, clean, stash, or alter them |
| Product media B2 | Isolated `gaonone-product-media-intake` worktree; deferred |
| Auth | Firebase verifies external identity; GaonOne issues sessions and owns roles/permissions. Web and Flutter exchange Firebase Google ID tokens for GaonOne sessions. |
| Firebase auth | Immutable Firebase UID mapping, server verification, concurrent-first-login protection, disabled SMS routes, and no silent email linking are merged. |
| Production auth config | `AUTH_PROVIDER=firebase`, `SMS_AUTH_ENABLED=false`, `SMS_PROVIDER=none`; public web identifiers and server credentials are external runtime configuration. |
| Release automation | Staging deployment is `workflow_dispatch` only; merges and CI do not deploy. |
| Mobile lockfile | `mobile/pubspec.lock` is tracked |
| Visual QA | No repository screenshot/evidence record was found |

Existing web and Flutter cover customer, merchant, delivery, admin, and support surfaces. Static inspection found reusable web UI primitives, location/landmark handling, status/error UI, and some retry/connectivity support. This is not visual or device validation.

Owner Firebase credentials/OAuth origins and Android/iOS configuration/signing are release/runtime dependencies, not prerequisites for safely merging source work. The Phase 3 checkout/session slice merged at `09e0e5c`, checkout idempotency at `dc76d50`, live-tracking session boundary at `2432dc6`, account-session safe return at `5fffca1`, location-state resilience at `dff5dc6`, cart-state resilience at `522861c`, address-save resilience at `d5b3d3c`, support-ticket resilience at `98955ae`, payment-intent resilience at `524b1d1`, existing-pending-UPI availability recovery at `5df82a2`, and initial-UPI-intent availability recovery at `8f37a04`; security PR #195 merged at `168a496` after all four required gates passed, removing direct Next.js GHSA-vcvr-r3jv-pc5j. The current separate R-017 audit finding is `firebase@12.19.0` → `@firebase/firestore@4.17.2` → `@grpc/grpc-js@1.9.16`; source imports client `firebase/app` and `firebase/auth` only, not Firestore or a gRPC server. The isolated remediation pins only that exact nested edge to `@grpc/grpc-js@1.13.6`, while retaining Firebase and application imports, and its clean install/audit/build/auth regression require focused review and CI. Existing risky worktrees (`gaonone-real-otp-accounts`, `gaonone-web-foundation-primitives`) and the protected main checkout are preservation-only until separately authorized.
