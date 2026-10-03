# Current state

Verified 2026-10-03 UTC.

| Item | Verified state |
|---|---|
| Local main / origin/main | Both `26e35b0439ce903c67b676ba699add6231799e11` |
| Baseline CI | `backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images` passed for delivery-task privacy PR #200 final head `57b3571f0141914cba29c1897fd5f273aac608a2` before merge |
| Open PR | [#201](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/201) is green on final head `31d0d38` but held behind the isolated P0 UPI fulfilment gate on `fix/upi-fulfilment-gate`; do not merge it first |
| Main checkout | Protected owner Flutter/iOS modifications exist; do not reset, clean, stash, or alter them |
| Product media B2 | Isolated `gaonone-product-media-intake` worktree; deferred |
| Auth | Firebase verifies external identity; GaonOne issues sessions and owns roles/permissions. Web and Flutter exchange Firebase Google ID tokens for GaonOne sessions. |
| Firebase auth | Immutable Firebase UID mapping, server verification, concurrent-first-login protection, disabled SMS routes, and no silent email linking are merged. |
| Production auth config | `AUTH_PROVIDER=firebase`, `SMS_AUTH_ENABLED=false`, `SMS_PROVIDER=none`; public web identifiers and server credentials are external runtime configuration. |
| Release automation | Staging deployment is `workflow_dispatch` only; merges and CI do not deploy. |
| Mobile lockfile | `mobile/pubspec.lock` is tracked |
| Visual QA | No repository screenshot/evidence record was found |

Existing web and Flutter cover customer, merchant, delivery, admin, and support surfaces. Static inspection found reusable web UI primitives, location/landmark handling, status/error UI, and some retry/connectivity support. This is not visual or device validation.

Owner Firebase credentials/OAuth origins and Android/iOS configuration/signing are release/runtime dependencies, not prerequisites for safely merging source work. The Phase 3 checkout/session slice merged at `09e0e5c`, checkout idempotency at `dc76d50`, live-tracking session boundary at `2432dc6`, account-session safe return at `5fffca1`, location-state resilience at `dff5dc6`, cart-state resilience at `522861c`, address-save resilience at `d5b3d3c`, support-ticket resilience at `98955ae`, payment-intent resilience at `524b1d1`, existing-pending-UPI availability recovery at `5df82a2`, initial-UPI-intent availability recovery at `8f37a04`, checkout duplicate-submit guard at `30d420c`, signed-payment-confirmation recovery at `6825f8`, merchant-availability preservation at `99f10e`, and delivery-task privacy at `26e35b`; security PR #195 merged at `168a496` and security PR #196 merged at `2b5b124` after all four required gates passed. The current P0 prerequisite prevents unpaid UPI orders from becoming delivery-ready or proceeding through dispatch, pickup, or completion; COD remains collection-gated. It has no migration, Firebase/identity, role-model, client configuration, secrets, or deployment change. Existing risky worktrees (`gaonone-real-otp-accounts`, `gaonone-web-foundation-primitives`) and the protected main checkout are preservation-only until separately authorized.
