# GaonOne V1 release evidence — 2026-11-01 IST

This is an evidence ledger, **not** authorization to deploy. Each row is
pinned to an immutable GitHub commit or workflow run. Do not mark real-device,
payment, Firebase, Maps, dispatch activation or production smoke tests passed
from CI results.

## Priority 1 integrated release candidate

- Pull request: https://github.com/rishi-raj-AI/AI-Powered_Market/pull/235
- Previously verified CI baseline SHA: `04ddf31bdcb1f197035e1605c065e8007f6b8799` (historical, not the current head).
- GitHub reported the PR mergeable; it was moved from draft to **ready for review**
  on 2026-11-01 IST. It remains **unmerged** pending review and acceptance.
- Backend CI: **passed**, https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41243426895
  (400 backend tests passed against CI PostGIS/PostgreSQL, migrations applied).
- Web CI: **passed**, https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41243426911
- Mobile CI: **passed**, https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41243426842
- Production CI: **passed**, https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41243426921

## Signed Android QA artifact

- Build run: **passed**, https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41243423460
- Artifact: [gaonone-qa-apk-04ddf31bdcb1f197035e1605c065e8007f6b8799](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41243423460/artifacts/13058646487)
- APK build number: `5` (from the pinned QA workflow build command).
- Artifact ID: `13058646487`; ZIP SHA-256:
  `313195ce9adde7ee486d1fd740082a66e5806880d8e259f1c56c6c55dda5bed0`.
- APK signer certificate SHA-256, checked with `apksigner verify --print-certs`:
  `0b936a93cc249dd83131d92d23011158e7d17536724155ca312059c58f8e935b`.
  The workflow compared this with the pinned permanent GaonOne identity and passed.
- **Not yet tested:** installation and launch on a real Android device, Google
  sign-in, Firebase push delivery, Google Maps, COD checkout, rider pickup,
  delivery proof, intermittent connectivity and Hindi/Marathi readiness.
- GitHub artifact expiry reported as **2026-11-14 21:40 UTC**. Retain the
  immutable build evidence before expiry if authorized; do not replace its
  signing identity.

## Priority 2 and Priority 3

- Priority 2 merchant-media PR:
  https://github.com/rishi-raj-AI/AI-Powered_Market/pull/236
- Priority 3 acceptance PR:
  https://github.com/rishi-raj-AI/AI-Powered_Market/pull/237
- On 2026-11-01, fixed the Playwright merchant upload quarantine test on both
  branches: Next.js renders an additional route-announcer `role=alert`, so the
  assertion now selects the alert containing the quarantine error.
- At the time of this earlier snapshot, Priority 2 and 3 were draft. They were subsequently marked ready for review; this does not mean release acceptance.

## Unpassed external and operational gates

- Real handset installation and release smoke test: **not tested**.
- Google/Firebase sign-in and FCM delivery on production-connected APK:
  **not tested**.
- Maps/GPS permission and landmark fallback: **not tested**.
- Live COD, online gateway callback and merchant/rider alert receipts:
  **not tested**.
- Production S3-compatible quarantine/public bucket policy, scanner,
  object lifecycle cleanup and media feature flag: **not verified**.
- Automatic rider assignment under live concurrency, bounded radius and
  rollback drills: **not verified**. Keep `AUTO_DISPATCH_ENABLED=false`.
- Database backup/restore, production migration and deployment smoke test:
  **not verified**. Do not deploy or flip feature flags without approval.

Use [the secret-safe operator preflight](priority1-3-operator-preflight.md) and
[the release acceptance checklist](priority1-3-release-acceptance.md)
to record device, operator, environment, time, test result and rollback decision
before changing any gate from pending to passed.

## Subsequent integration checkpoint — 2026-11-01 IST

This section supersedes the **branch-status** statements above, while retaining
the original immutable CI and signing evidence.

- Priority 1 PR #235 head: `ddcb0171d37cc48b2510a21da6da01565bf02e20`.
  The previous `795a8a54` head passed Backend, Mobile, Production and signed
  QA APK checks but **failed Web CI** because the onboarding Playwright test
  attempted to click a deliberately disabled phone-registration button when
  the authentication configuration endpoint was not mocked.
- Commit `ddcb0171` updates the Playwright test to cover both enabled and
  disabled phone-auth configurations and the current success message.
  [Exact-head Web CI](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256451753)
  was still running when this checkpoint was written. Backend CI for that
  head [passed](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256451756).
- Priority 2 PR #236 head: `e3c3857e6d87a0bcb6f1874e77981c41f4d4a7a2`.
  This is a two-parent integration merge of Priority 1 fixes and the
  previously CI-green media implementation. Its **new exact-head checks
  remain pending**, regardless of earlier passes at `ed91b28f`.
- Priority 3 PR #237 was similarly reconciled onto Priority 2 at
  `50d769e82501c52d7bc543944b201214f844a9eb`, retaining its three
  release-runbook files. Its new exact-head checks remain pending.
- A permanently signed QA APK **passed** at Priority 1 commit
  `795a8a541a9e30bf169e3738fd7e18d26d7244a0` in
  [workflow 41252232691](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41252232691),
  artifact ID `13061573986`. A newer exact-head build was still running.
  Do not call any of these device-tested or production-approved.
- PRs #235, #236 and #237 are open and ready for code review, but **unmerged**.
  No production deployment, live dispatch activation or product-media
  activation has been authorized or performed.

Release decision: **NO-GO** until exact-head checks, code review, real-device
acceptance, external provider verification and the production preflight gates
are completed with recorded evidence.


## Verified CI checkpoint and subsequent safety fixes — 2026-11-01 IST

The previously pending **exact-head** checks all completed successfully:

| PR | Verified immutable SHA | Backend | Web | Mobile | Production |
| --- | --- | --- | --- | --- | --- |
| [#235](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/235) | `ddcb0171d37cc48b2510a21da6da01565bf02e20` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256451756) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256451753) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256451765) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256451770) |
| [#236](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/236) | `e3c3857e6d87a0bcb6f1874e77981c41f4d4a7a2` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256528001) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256527952) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256527959) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256527961) |
| [#237](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/237) | `4f43af1894a49ab8712576e1e7ac176bb6c22f8b` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256564457) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256564460) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256564412) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256564481) |

A newer [signed QA APK workflow 41256448299](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256448299)
**passed** for `ddcb0171d37cc48b2510a21da6da01565bf02e20`;
artifact `13063123563` was present and unexpired when checked. The workflow
compares the APK certificate SHA-256 with the existing pinned permanent
GaonOne signing identity. This verifies a build, **not installation or device
acceptance**.

Subsequent hardening was committed to Priority 1 and carried forward through
the dependent branches:

- `b0c44ee3`: unattended dispatch now locks and revalidates the order row
  before assigning a rider, preventing assignment to a concurrently cancelled
  or no-longer-ready order.
- `acd3e32d`: added regression coverage for a stale-ready order and the
  PostgreSQL `FOR UPDATE` requirement.
- `364839fa`: on logout, the Android app attempts local Firebase messaging
  token deletion even if the backend token-unregistration call fails, reducing
  push-notification leakage on shared handsets.
- `da56bb03`: merged the Priority 1 hardening into the Priority 2 branch.
- `e750e418`: merged the updated Priority 2 branch into Priority 3.

**Important:** the green CI results above belong to the *earlier immutable
SHAs*, not the subsequent hardening. New exact-head CI and a signed APK build
were triggered and were still pending at the time this checkpoint was
recorded. The open pull requests remain unmerged, and there is no production
deployment approval or verified real-device/provider acceptance. Keep
`AUTO_DISPATCH_ENABLED=false` and `PRODUCT_MEDIA_ENABLED=false`.
