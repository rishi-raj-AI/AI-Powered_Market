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

Changed: production env/validator, staging and production CI workflows, backend config/model/schema/auth/service, migration `0024_external_identities`, Firebase/config tests, and launch-control documents. No web, Flutter, or product UI files changed.

## Validation

Passed: Python compilation, Ruff (`backend/app`, `backend/tests`), `git diff --check`, and production environment validation against a non-secret temporary Firebase-shaped fixture. Full pytest could not run locally because Docker is unavailable and the host Python lacks backend dependencies. Required GitHub CI remains mandatory.

## Unresolved / owner input

Firebase project/server credentials; OAuth origins; Android/iOS configuration and signing; domains/CORS; explicit phone-account linking design; visual QA; maps and Razorpay launch decisions.

## Next task

Inspect, commit, and open the Phase 2A PR. Wait for required CI; do not merge or deploy automatically. If CI is green, conduct a review of migration safety, Firebase mock tests, manual-dispatch behavior, and SMS route gating before requesting merge.

## Preservation contract

Never clean/reset/stash the protected main checkout or risky existing worktrees. Preserve the product-media B2 worktree. This Phase 2A worktree contains uncommitted implementation until its coherent commit is made.
