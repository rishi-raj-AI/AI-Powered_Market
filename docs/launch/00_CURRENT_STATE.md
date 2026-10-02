# Current state

Verified 2026-10-02 UTC.

| Item | Verified state |
|---|---|
| Local main / origin/main | Both `6825f8895367aba43355755b4e990765e0e8c887` |
| Baseline CI | `backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images` passed for signed-payment-confirmation PR #198 final head `6c331ef8b53687b399e0577e7386583a0e0549ec` before merge |
| Open PR | None — the isolated merchant-availability follow-up is under focused review on `feat/launch-phase3-reliability-followup`; open a PR only after project-control update and review |
| Main checkout | Protected owner Flutter/iOS modifications exist; do not reset, clean, stash, or alter them |
| Product media B2 | Isolated `gaonone-product-media-intake` worktree; deferred |
| Auth | Firebase verifies external identity; GaonOne issues sessions and owns roles/permissions. Web and Flutter exchange Firebase Google ID tokens for GaonOne sessions. |
| Firebase auth | Immutable Firebase UID mapping, server verification, concurrent-first-login protection, disabled SMS routes, and no silent email linking are merged. |
| Production auth config | `AUTH_PROVIDER=firebase`, `SMS_AUTH_ENABLED=false`, `SMS_PROVIDER=none`; public web identifiers and server credentials are external runtime configuration. |
| Release automation | Staging deployment is `workflow_dispatch` only; merges and CI do not deploy. |
| Mobile lockfile | `mobile/pubspec.lock` is tracked |
| Visual QA | No repository screenshot/evidence record was found |

Existing web and Flutter cover customer, merchant, delivery, admin, and support surfaces. Static inspection found reusable web UI primitives, location/landmark handling, status/error UI, and some retry/connectivity support. This is not visual or device validation.

Owner Firebase credentials/OAuth origins and Android/iOS configuration/signing are release/runtime dependencies, not prerequisites for safely merging source work. The Phase 3 checkout/session slice merged at `09e0e5c`, checkout idempotency at `dc76d50`, live-tracking session boundary at `2432dc6`, account-session safe return at `5fffca1`, location-state resilience at `dff5dc6`, cart-state resilience at `522861c`, address-save resilience at `d5b3d3c`, support-ticket resilience at `98955ae`, payment-intent resilience at `524b1d1`, existing-pending-UPI availability recovery at `5df82a2`, initial-UPI-intent availability recovery at `8f37a04`, checkout duplicate-submit guard at `30d420c`, and signed-payment-confirmation recovery at `6825f8`; security PR #195 merged at `168a496` and security PR #196 merged at `2b5b124` after all four required gates passed. The active isolated follow-up preserves merchant-owned `Store.is_active` through platform suspension/reapproval while `Merchant.status` remains the public, purchase, and store/catalog-mutation eligibility gate; it corrects the admin active-store metric to use that same interpretation. It has no migration, historical backfill, automatic reopen, deployment, payment, identity, or client configuration change. Existing risky worktrees (`gaonone-real-otp-accounts`, `gaonone-web-foundation-primitives`) and the protected main checkout are preservation-only until separately authorized.
