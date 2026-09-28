# Current state

Verified 2026-09-28 UTC.

| Item | Verified state |
|---|---|
| Local main / origin/main | Both `dc76d5081c58691583eddebeaf45befd9bb8b867` |
| Baseline CI | `backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images` passed for Phase 3 PR #185 final head `fd5afb3` before merge |
| Open PR | No launch PR is open; the current Phase 3 customer-path slice is isolated on `feat/launch-customer-session-resilience` |
| Main checkout | Protected owner Flutter/iOS modifications exist; do not reset, clean, stash, or alter them |
| Product media B2 | Isolated `gaonone-product-media-intake` worktree; deferred |
| Auth | Firebase verifies external identity; GaonOne issues sessions and owns roles/permissions. Web and Flutter exchange Firebase Google ID tokens for GaonOne sessions. |
| Firebase auth | Immutable Firebase UID mapping, server verification, concurrent-first-login protection, disabled SMS routes, and no silent email linking are merged. |
| Production auth config | `AUTH_PROVIDER=firebase`, `SMS_AUTH_ENABLED=false`, `SMS_PROVIDER=none`; public web identifiers and server credentials are external runtime configuration. |
| Release automation | Staging deployment is `workflow_dispatch` only; merges and CI do not deploy. |
| Mobile lockfile | `mobile/pubspec.lock` is tracked |
| Visual QA | No repository screenshot/evidence record was found |

Existing web and Flutter cover customer, merchant, delivery, admin, and support surfaces. Static inspection found reusable web UI primitives, location/landmark handling, status/error UI, and some retry/connectivity support. This is not visual or device validation.

Owner Firebase credentials/OAuth origins and Android/iOS configuration/signing are release/runtime dependencies, not prerequisites for safely merging source work. The Phase 3 checkout/session slice merged at `09e0e5c`, and the checkout idempotency slice merged at `dc76d50`; the current isolated slice ensures a live-tracking 401 uses the established GaonOne session-expiry boundary rather than leaving a stale customer token. Existing risky worktrees (`gaonone-real-otp-accounts`, `gaonone-web-foundation-primitives`) and the protected main checkout are preservation-only until separately authorized.
