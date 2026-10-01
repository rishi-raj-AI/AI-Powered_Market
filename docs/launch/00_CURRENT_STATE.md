# Current state

Verified 2026-09-30 UTC.

| Item | Verified state |
|---|---|
| Local main / origin/main | Both `8f37a04c1b2dcb8c1f3e0dc66c2873b70eb54d89` |
| Baseline CI | `backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images` passed for Phase 3 PR #194 final head `5b728ded95280ffde94606974fa814a888b19214` before merge |
| Open PR | #195 — priority Next.js security update on `chore/next-security-update`; all four required CI gates must be evaluated only on its final branch head |
| Main checkout | Protected owner Flutter/iOS modifications exist; do not reset, clean, stash, or alter them |
| Product media B2 | Isolated `gaonone-product-media-intake` worktree; deferred |
| Auth | Firebase verifies external identity; GaonOne issues sessions and owns roles/permissions. Web and Flutter exchange Firebase Google ID tokens for GaonOne sessions. |
| Firebase auth | Immutable Firebase UID mapping, server verification, concurrent-first-login protection, disabled SMS routes, and no silent email linking are merged. |
| Production auth config | `AUTH_PROVIDER=firebase`, `SMS_AUTH_ENABLED=false`, `SMS_PROVIDER=none`; public web identifiers and server credentials are external runtime configuration. |
| Release automation | Staging deployment is `workflow_dispatch` only; merges and CI do not deploy. |
| Mobile lockfile | `mobile/pubspec.lock` is tracked |
| Visual QA | No repository screenshot/evidence record was found |

Existing web and Flutter cover customer, merchant, delivery, admin, and support surfaces. Static inspection found reusable web UI primitives, location/landmark handling, status/error UI, and some retry/connectivity support. This is not visual or device validation.

Owner Firebase credentials/OAuth origins and Android/iOS configuration/signing are release/runtime dependencies, not prerequisites for safely merging source work. The Phase 3 checkout/session slice merged at `09e0e5c`, checkout idempotency at `dc76d50`, live-tracking session boundary at `2432dc6`, account-session safe return at `5fffca1`, location-state resilience at `dff5dc6`, cart-state resilience at `522861c`, address-save resilience at `d5b3d3c`, support-ticket resilience at `98955ae`, payment-intent resilience at `524b1d1`, existing-pending-UPI availability recovery at `5df82a2`, and initial-UPI-intent availability recovery at `8f37a04`; PR #194 routes only a post-create initial intent `503` to the existing neutral pending-order path without changing backend availability authority, payment state, roles, or provider configuration. A fresh production dependency audit identified the direct `next` `16.3.3` pin as affected by critical GHSA-vcvr-r3jv-pc5j; repository source has no `next/og` or `ImageResponse` use, but the active security branch pins the available patch `16.3.8` and its lockfile. The same current audit reports a separate pre-existing high `@grpc/grpc-js` finding through Firebase's unused Firestore dependency; source imports only client `firebase/app` and `firebase/auth`, not Firestore or a gRPC server. It is tracked for a separately reviewed remediation and does not alter the narrowly scoped Next.js patch. Existing risky worktrees (`gaonone-real-otp-accounts`, `gaonone-web-foundation-primitives`) and the protected main checkout are preservation-only until separately authorized.
