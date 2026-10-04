# Current state

Verified 2026-10-04 UTC.

| Item | Verified state |
|---|---|
| Local main / origin/main | Both `4e527879833f59129c4601eac7887b54dd5f6d86` |
| Baseline CI | All four required gates passed for delivery-proof PR #203 final head `7de358f0029c0482c15bb20de1dc6955b7d1ae01` before merge. |
| Open PR | None — new isolated `test/delivery-web-acceptance` exercises the web rider handoff and recovery path. |
| Main checkout | Protected owner Flutter/iOS modifications exist; do not reset, clean, stash, or alter them |
| Product media B2 | Isolated `gaonone-product-media-intake` worktree; deferred |
| Auth | Firebase verifies external identity; GaonOne issues sessions and owns roles/permissions. Web and Flutter exchange Firebase Google ID tokens for GaonOne sessions. |
| Firebase auth | Immutable Firebase UID mapping, server verification, concurrent-first-login protection, disabled SMS routes, and no silent email linking are merged. |
| Production auth config | `AUTH_PROVIDER=firebase`, `SMS_AUTH_ENABLED=false`, `SMS_PROVIDER=none`; public web identifiers and server credentials are external runtime configuration. |
| Release automation | Staging deployment is `workflow_dispatch` only; merges and CI do not deploy. |
| Mobile lockfile | `mobile/pubspec.lock` is tracked |
| Visual QA | Bounded web delivery handoff screenshots and evidence now recorded in `16_DELIVERY_WEB_ACCEPTANCE.md`; other screens and device acceptance remain pending. |

Existing web and Flutter cover customer, merchant, delivery, admin, and support surfaces. Static inspection found reusable web UI primitives, location/landmark handling, status/error UI, and some retry/connectivity support. This is not visual or device validation.

Owner Firebase credentials/OAuth origins and Android/iOS configuration/signing are release/runtime dependencies, not prerequisites for safely merging source work. The Phase 3 checkout/session slice merged at `09e0e5c`, checkout idempotency at `dc76d50`, live-tracking session boundary at `2432dc6`, account-session safe return at `5fffca1`, location-state resilience at `dff5dc6`, cart-state resilience at `522861c`, address-save resilience at `d5b3d3c`, support-ticket resilience at `98955ae`, payment-intent resilience at `524b1d1`, existing-pending-UPI availability recovery at `5df82a2`, initial-UPI-intent availability recovery at `8f37a04`, checkout duplicate-submit guard at `30d420c`, signed-payment-confirmation recovery at `6825f8`, merchant-availability preservation at `99f10e`, delivery-task privacy at `26e35b`, and the P0 UPI fulfilment/login cold-hydration remedy at `a1fa04f`; security PR #195 merged at `168a496` and security PR #196 merged at `2b5b124` after all four required gates passed. Flutter completion merged at `f64e8bf`. Delivery-proof PR #203 merged at `4e52787` with durable proof-code limits and immutable verified evidence; the active branch validates the web rider handoff and uncertain-response recovery. Existing risky worktrees (`gaonone-real-otp-accounts`, `gaonone-web-foundation-primitives`) and the protected main checkout are preservation-only until separately authorized.
