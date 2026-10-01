# Current state

Verified 2026-10-01 UTC.

| Item | Verified state |
|---|---|
| Local main / origin/main | Both `2b5b1244fb8df147ef0f1ef40ada5adde33453f8` |
| Baseline CI | `backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images` passed for security PR #196 final head `9ba269ac2a936da0c2d1876a0fa7754700440166` before merge |
| Open PR | None — the isolated checkout duplicate-submit guard is under focused review on `feat/launch-checkout-submit-guard-secured`; required CI must be evaluated only after a PR is opened on its final branch head |
| Main checkout | Protected owner Flutter/iOS modifications exist; do not reset, clean, stash, or alter them |
| Product media B2 | Isolated `gaonone-product-media-intake` worktree; deferred |
| Auth | Firebase verifies external identity; GaonOne issues sessions and owns roles/permissions. Web and Flutter exchange Firebase Google ID tokens for GaonOne sessions. |
| Firebase auth | Immutable Firebase UID mapping, server verification, concurrent-first-login protection, disabled SMS routes, and no silent email linking are merged. |
| Production auth config | `AUTH_PROVIDER=firebase`, `SMS_AUTH_ENABLED=false`, `SMS_PROVIDER=none`; public web identifiers and server credentials are external runtime configuration. |
| Release automation | Staging deployment is `workflow_dispatch` only; merges and CI do not deploy. |
| Mobile lockfile | `mobile/pubspec.lock` is tracked |
| Visual QA | No repository screenshot/evidence record was found |

Existing web and Flutter cover customer, merchant, delivery, admin, and support surfaces. Static inspection found reusable web UI primitives, location/landmark handling, status/error UI, and some retry/connectivity support. This is not visual or device validation.

Owner Firebase credentials/OAuth origins and Android/iOS configuration/signing are release/runtime dependencies, not prerequisites for safely merging source work. The Phase 3 checkout/session slice merged at `09e0e5c`, checkout idempotency at `dc76d50`, live-tracking session boundary at `2432dc6`, account-session safe return at `5fffca1`, location-state resilience at `dff5dc6`, cart-state resilience at `522861c`, address-save resilience at `d5b3d3c`, support-ticket resilience at `98955ae`, payment-intent resilience at `524b1d1`, existing-pending-UPI availability recovery at `5df82a2`, and initial-UPI-intent availability recovery at `8f37a04`; security PR #195 merged at `168a496` after all four required gates passed, and security PR #196 merged at `2b5b124` after all four required gates passed, removing the R-017 Firebase-transitive gRPC audit finding without changing application identity/session/role/provider/deployment behavior. The active isolated checkout slice claims a synchronous client token before the first await so a forced duplicate UPI event cannot start another checkout fetch; server payment, ownership, roles, and provider behavior remain authoritative. Existing risky worktrees (`gaonone-real-otp-accounts`, `gaonone-web-foundation-primitives`) and the protected main checkout are preservation-only until separately authorized.
