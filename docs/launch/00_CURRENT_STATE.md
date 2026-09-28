# Current state

Verified 2026-09-28 UTC.

| Item | Verified state |
|---|---|
| Local main / origin/main | Both `7d8f5cb7c718cd0d376ed1d3094679038fdedf6c` |
| Baseline CI | `backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images` passed for that SHA |
| Open PR | #177 is documentation-only and unmerged |
| Main checkout | Protected owner Flutter/iOS modifications exist; do not reset, clean, stash, or alter them |
| Product media B2 | Isolated `gaonone-product-media-intake` worktree; deferred |
| Auth | OTP/MSG91 across backend, web, and Flutter; Firebase Admin is currently FCM-only |
| Firebase auth | No server ID-token verification, UID mapping, web/mobile Google Sign-In dependency, or client flow |
| Production auth config | `AUTH_PROVIDER=local_otp`, `SMS_PROVIDER=msg91`; validation requires MSG91 for direct OTP outside development/test |
| Release automation | Source workflow can deploy staging after `main` pushes; this conflicts with explicit-release policy |
| Mobile lockfile | `mobile/pubspec.lock` is tracked |
| Visual QA | No repository screenshot/evidence record was found |

Existing web and Flutter cover customer, merchant, delivery, admin, and support surfaces. Static inspection found reusable web UI primitives, location/landmark handling, status/error UI, and some retry/connectivity support. This is not visual or device validation.

Existing risky worktrees (`gaonone-real-otp-accounts`, `gaonone-web-foundation-primitives`) and the protected main checkout are preservation-only until separately authorized.
