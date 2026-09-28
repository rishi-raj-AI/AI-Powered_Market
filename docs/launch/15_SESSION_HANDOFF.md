# Session handoff

## Objective

Phase 2A: separate release authorization from `main` validation, establish Firebase-to-GaonOne identity/session exchange, and fail-close SMS for the launch configuration.

## Completed

- Merged Phase 1 PR #181 with merge commit `b730bbaef995bde31062459eff5bde54666cfc7c`; all four required checks passed before merge.
- Safely fast-forwarded protected local main to that SHA; its exact seven known owner modifications remain intact.
- Created isolated `/Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/gaonone-launch-auth-foundation` on `feat/launch-auth-foundation` from the merged main.
- Changed the staging workflow to `workflow_dispatch` only; no deployment ran.
- Added the additive `external_identities` model/migration, Firebase token verifier boundary, `/auth/firebase/exchange`, and GaonOne session issuance.
- Set production example/CI to Firebase with `SMS_AUTH_ENABLED=false`; SMS send/verify and MSG91 widget routes return 404 when SMS is disabled. Legacy SMS code remains.
- First Firebase login creates a customer with no phone and a UID identity record; repeat login reuses it. No automatic email matching/linking occurs.

## Changed files

Changed: production env/validator, staging and production CI workflows, backend config/model/schema/auth/service, migration `0024_external_identities`, Firebase/config tests, nullable-phone web/Flutter client compatibility, and launch-control documents. No Google client sign-in flow or product UI redesign was added.

## Validation

Committed implementation: `4b2a1e69990e58a35d5e647ed05b4556f3fa8029` (`feat(auth): add Firebase identity foundation`). Passed: Python compilation, Ruff (`backend/app`, `backend/tests`), `git diff --check`, and production environment validation against a non-secret temporary Firebase-shaped fixture. Full pytest could not run locally because Docker is unavailable and the host Python lacks backend dependencies. Required GitHub CI remains mandatory.

## Unresolved / owner input

Firebase project/server credentials; OAuth origins; Android/iOS configuration and signing; domains/CORS; explicit phone-account linking design; visual QA; maps and Razorpay launch decisions.

## Next task

The first remediation head `5473f79` passed all four required CI gates. Final review then found that Firebase accounts intentionally have a null phone while web/Flutter client models still required a string, which would crash Flutter bootstrap and mislabel the web account. The pending narrow remediation makes client phone fields nullable, avoids sending a null Razorpay prefill contact, labels phone-unlinked accounts accurately, binds Firebase auth and FCM to the same configured project, and strengthens the concurrency assertion to prove that no duplicate Firebase account remains. Commit/push this remediation, then require all four CI gates on its new head. If green, conduct the final migration/Firebase/manual-dispatch/SMS-gating review and merge normally; do not deploy.

## Preservation contract

Never clean/reset/stash the protected main checkout or risky existing worktrees. Preserve the product-media B2 worktree. This Phase 2A worktree contains uncommitted implementation until its coherent commit is made.
