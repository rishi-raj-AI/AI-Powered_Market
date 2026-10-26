# Historical current-state snapshot

> Superseded by [`LAUNCH_STATUS.md`](LAUNCH_STATUS.md) and [`15_SESSION_HANDOFF.md`](15_SESSION_HANDOFF.md). This retained 2026-10-24 snapshot is historical context only and must not be used as the active baseline, PR, CI, or resume state.

Verified 2026-10-24 UTC.

| Item | Verified state |
|---|---|
| Remote main / current baseline | `origin/main` = `43b683e255bc2cfc89c3f15689baeb98c31b6432`, merging security PR #208 after #204–#206. |
| Protected golden main | Safely fast-forwarded to `43b683e255bc2cfc89c3f15689baeb98c31b6432`; the exact seven owner-owned Flutter/iOS modifications remain intact. |
| Baseline CI | All four required gates passed for security PR #208 final head `911044cee4423881134f564fe5abf7aa7714035a` before merge. |
| Active recovery | Isolated `gaonone-launch-merchant-transition-recovery` / `test/merchant-order-acceptance` is rebased on the new main at source commit `171d01a`. Its initial PR #209 head `898b094` passed `backend-check`, `analyze-and-build-android`, and `production-compose-and-images`, but `build-and-ui` failed 6 of 436 Playwright cases (430 passed): all six were mobile-Chrome primary `/merchant` action clicks intercepted by responsive header/metadata. This is a Phase-209-caused P1 layout defect, not an authorization/backend regression or CI infrastructure failure. The narrow responsive remediation is locally validated; CI must be evaluated only on its new exact final head. |
| Main checkout | Protected owner Flutter/iOS modifications exist; do not reset, clean, stash, or alter them |
| Product media B2 | Isolated `gaonone-product-media-intake` worktree; deferred |
| Auth | Firebase verifies external identity; GaonOne issues sessions and owns roles/permissions. Web and Flutter exchange Firebase Google ID tokens for GaonOne sessions. |
| Firebase auth | Immutable Firebase UID mapping, server verification, concurrent-first-login protection, disabled SMS routes, and no silent email linking are merged. |
| Production auth config | `AUTH_PROVIDER=firebase`, `SMS_AUTH_ENABLED=false`, `SMS_PROVIDER=none`; public web identifiers and server credentials are external runtime configuration. |
| Release automation | Staging deployment is `workflow_dispatch` only; merges and CI do not deploy. |
| Mobile lockfile | `mobile/pubspec.lock` is tracked |
| Visual QA | Bounded web delivery handoff screenshots and evidence now recorded in `16_DELIVERY_WEB_ACCEPTANCE.md`; other screens and device acceptance remain pending. |

Existing web and Flutter cover customer, merchant, delivery, admin, and support surfaces. Static inspection found reusable web UI primitives, location/landmark handling, status/error UI, and some retry/connectivity support. This is not visual or device validation.

Owner Firebase credentials/OAuth origins and Android/iOS configuration/signing are release/runtime dependencies, not prerequisites for safely merging source work. The Phase 3 checkout/session slice merged at `09e0e5c`, checkout idempotency at `dc76d50`, live-tracking session boundary at `2432dc6`, account-session safe return at `5fffca1`, location-state resilience at `dff5dc6`, cart-state resilience at `522861c`, address-save resilience at `d5b3d3c`, support-ticket resilience at `98955ae`, payment-intent resilience at `524b1d1`, existing-pending-UPI availability recovery at `5df82a2`, initial-UPI-intent availability recovery at `8f37a04`, checkout duplicate-submit guard at `30d420c`, signed-payment-confirmation recovery at `6825f8`, merchant-availability preservation at `99f10e`, delivery-task privacy at `26e35b`, and the P0 UPI fulfilment/login cold-hydration remedy at `a1fa04f`; security PR #195 merged at `168a496` and security PR #196 merged at `2b5b124` after all four required gates passed. Flutter completion merged at `f64e8bf`. Delivery-proof PR #203 merged at `4e52787` with durable proof-code limits and immutable verified evidence; web delivery-handoff PR #204 merged at `45b4b28`; dependency-security PR #208 merged at `43b683e`. Merchant transition recovery is now rebased; initial source validation and focused review passed on `171d01a`, but initial PR head `898b094` exposed the mobile layout defect. The responsive remediation now requires all four gates on its new exact final head before any merge. Existing risky worktrees (`gaonone-real-otp-accounts`, `gaonone-web-foundation-primitives`) and the protected main checkout are preservation-only until separately authorized.
