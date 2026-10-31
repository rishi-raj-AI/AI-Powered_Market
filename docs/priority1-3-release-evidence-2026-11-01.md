# GaonOne V1 release evidence — 2026-11-01 IST

This is an evidence ledger, **not** authorization to deploy. Each row is
pinned to an immutable GitHub commit or workflow run. Do not mark real-device,
payment, Firebase, Maps, dispatch activation or production smoke tests passed
from CI results.

## Priority 1 integrated release candidate

- Pull request: https://github.com/rishi-raj-AI/AI-Powered_Market/pull/235
- Head SHA: `04ddf31bdcb1f197035e1605c065e8007f6b8799`
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
- Priority 2 and 3 **remain draft** until the new exact-head CI passes and
  a reviewer accepts the media/rollout safety gates.

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
