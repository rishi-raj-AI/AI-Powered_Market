# GaonOne V1 readiness audit

Updated: 2026-10-28  
Source baseline: `main` / `origin/main` = `ebe389de31d1d473f43a65cbaa41efa53ba0ccea`  
Release status: **not a release candidate**. No staging or production deployment was performed.

## Required first report

| Question | Evidence-backed answer |
|---|---|
| Current main SHA | `ebe389de31d1d473f43a65cbaa41efa53ba0ccea` in the protected checkout's local and origin-tracking refs when this audit branch was created. |
| Release PR | [#221](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/221), open and mergeable, head `4873272f003d4f7d4d04a0af69e28a7f245aeb08`, base `ebe389de31d1d473f43a65cbaa41efa53ba0ccea`. |
| PR #221 CI | `backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images` all completed successfully on that exact head. |
| Public runtime evidence | On 2026-10-28, `https://gaonone.in/` returned HTTPS 200 through Caddy; `/api/v1/health` returned `status=ok, version=0.4.0`; `/api/v1/health/ready` returned database and Redis ready. This is availability evidence only. |
| Production SHA | **Unverified.** A public health response does not attest to a Git SHA, and the visible `0.4.0` differs from the source default `0.5.0`. Only approved host inspection can establish the deployed commit. |
| Sudo/environment selector propagation | Source review of PR #221 found a narrow non-secret preservation design for `GAONONE_EXPECTED_SHA` and `GAONONE_ENVIRONMENT`, including regression coverage for manual and workflow invocation. It has not been merged or installed on a server. |
| Committed-secret scan | A targeted tracked-source scan found no obvious private-key, live Razorpay, Stripe, or Google API key pattern. This is not a substitute for repository-secret scanning or provider-key rotation policy. |

## What source validation demonstrates

- The backend has a Firebase verifier boundary and exchanges a verified Firebase identity for a GaonOne session; role and permission decisions remain server-authoritative.
- First and repeat Firebase login behavior is guarded by the external-identity uniqueness contract; automatic email linking is intentionally absent.
- Firebase launch configuration disables SMS/direct OTP by default, production validation prohibits `DEV_OTP`, and MSG91 configuration is conditional on explicitly enabling SMS.
- Web and Flutter clients contain Google/Firebase sign-in integration, local session restoration, and local logout cleanup that does not depend on a provider sign-out succeeding.
- The source contains customer, merchant, rider, support, admin, order/payment, delivery proof, COD, and operational workflows that have been through the recorded source/CI gates.
- Current `main` still has a deployment-control gap addressed only in open PR #221: it does not force an explicit SHA/environment and omits `proxy` from the normal and rollback service lists.

## What source validation does not demonstrate

- That Firebase, Google OAuth, domains, signed Android/iOS apps, Maps, Razorpay, MSG91, FCM, CORS, DNS, certificates, or server secrets are configured correctly.
- That a production or staging server runs any particular Git SHA or retains recoverable backups.
- That visual, accessibility, Hindi/Marathi, physical-device, low-network, field logistics, payment, SMS, or provider failure behavior is acceptable.
- That an external provider will accept current package/bundle identifiers or signing fingerprints.
- That a deployment, migration, migration rollback, or release authorization has occurred.

## Launch-critical findings

| Priority | Finding | State | Next safe action |
|---|---|---|---|
| P0 | Firebase/Google provider and server configuration have no owner-side acceptance evidence. | Open owner dependency | Complete secure owner setup and test the existing identity/session contract on real launch origins/devices. |
| P0 | Android release is debug-signed; iOS bundle identity disagrees with Flutter Firebase options and no Google callback scheme was found. | Open owner decision/configuration | Choose canonical identity, signing, and distribution ownership before editing registration/configuration. |
| P1 | Runtime environment is called staging in source guidance but production in filenames/configuration; deployment authorization semantics are ambiguous. | Open owner decision | Designate the live environment and document its release policy. |
| P1 | PR #221 fixes proxy startup and secure selector propagation but is unmerged/uninstalled. | Open PR | Retain as a separately reviewable release-control change; do not deploy it without approval. |
| P1 | Pre-migration media backup requires a running API container. It fails safe before migration but prevents an assured cold deployment. | New source/operational defect | Prepare a narrow remediation with regression tests while retaining backup-before-migration. |
| P1 | Current public health says `0.4.0`; source default is `0.5.0`, so code provenance is unverified. | Owner/server evidence needed | Record real checkout HEAD and `.deployed-sha` via approved non-secret inspection. |
| P2 | FCM server code exists but clients do not register devices for push. | Deferred | Keep FCM unconfigured until a separately reviewed client integration. |
| P2 | Merchant media upload is not evidenced as a complete catalogue image journey. | Deferred | Correct scope/UX or implement a reviewed product-media attachment flow. |
| P2 | No off-host backup, restore-drill, log-retention, or alert-delivery evidence. | Owner operations dependency | Select and test operational controls before release candidate authorization. |

## Exact external dependency state

The authoritative detail is in [EXTERNAL_DEPENDENCY_REGISTER.md](EXTERNAL_DEPENDENCY_REGISTER.md). The short conclusion is:

- **Required and unverified:** Firebase/Google identity, canonical mobile identity and signing, actual runtime SHA/environment, DNS/CORS/TLS policy, backup/restore proof, device/field/visual acceptance, release authorization.
- **Optional/deferred:** MSG91, Razorpay/UPI, FCM push, product-media object storage/scanning, analytics/crash reporting, external search.
- **Source remediation awaiting review:** PR #221 and a separate follow-up for the cold API-container backup prerequisite.

## Immediate safe work

1. Preserve the protected checkout and all owner-owned Flutter/iOS modifications; do not reset, clean, stash, or deploy.
2. Keep PR #221 open and unmerged until the owner approves it; do not run its server installer.
3. Record this audit, owner-action register, manual plan, bug backlog, and release checklist in a documentation-only review branch.
4. Prepare a narrowly scoped release-script remediation for the backup prerequisite only after documenting its invariants and test plan.
5. Wait for secure owner evidence before any live configuration, provider activation, app-store action, or deployment.

## Release-candidate threshold

GaonOne may be proposed as a release candidate only when one exact candidate SHA has all required CI gates green, the release-control/backup path is reviewed and merged, the owner evidence bundle in [OWNER_ACTIONS_REQUIRED.md](OWNER_ACTIONS_REQUIRED.md) is complete, the manual/field plan is passed or explicitly waived by the owner, and a human expressly authorizes the deployment step. This audit does not confer that authorization.
