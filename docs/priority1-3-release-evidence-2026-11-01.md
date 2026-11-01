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


## Verified three-branch CI and signed APK — 2026-11-01 IST

The four standard CI workflows **and permanent-signer QA APK build**
completed successfully for each of the following immutable release heads.
These are **historical green baselines**, not the current branch heads:

| PR | Verified SHA | Backend | Web | Mobile | Production | Signed APK |
| --- | --- | --- | --- | --- | --- | --- |
| [#235](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/235) | `568f986e41b89433fcf96b1083ffa80dab051cb8` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261292756) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261292777) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261292830) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261292824) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261289742) |
| [#236](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/236) | `9e4b21decda7b1ae3027dce6166a1e1147b5da00` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261302749) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261302765) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261302744) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261302745) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261299515) |
| [#237](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/237) | `bd94f894ae1435c32a52ec2a9fdd6e8c87e5c28c` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261311538) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261311586) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261311499) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261311670) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261307905) |

The final Priority 3 QA build produced [artifact 13065352822](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41261307905/artifacts/13065352822).
Its signing workflow validates the pinned permanent certificate SHA-256.
Artifact publication is **not** evidence of physical handset installation.

### Subsequent FCM registration security hardening

A code review identified that any authenticated account could previously
rebind an *active* FCM device token already associated with another account.
The device registration endpoint now locks existing token rows, rejects
cross-account active-token takeover (HTTP 409), permits inactive-token
reclamation after logout, and maps first-registration unique-constraint
races to HTTP 409. Tests cover takeover, idempotent same-account updates,
inactive-token handover, concurrent insert conflicts, and push configuration.

Push readiness now requires both the Firebase project ID **and** the worker's
service-account configuration; a project ID alone is not sufficient to
advertise push as enabled. This is a configuration check, **not** proof that
FCM credentials are valid or notifications reach handsets.

- Priority 1 current head: `c0e51afb989dc4fc16d7863e5d6492f6274a0e60`.
- Priority 2 current head: `f6ca2f38074a488076665b32a708359d6e9bb804`.
- Priority 3 integration head before this evidence update:
  `e2d8a56324ba33a5f2897715e64f4b80e8fbb6c0`.
- All newer exact-head CI and signed QA APK checks were **queued/running**
  when this checkpoint was recorded. Do not transfer earlier green status
  to these commits.

**Release decision remains NO-GO:** all three PRs are unmerged, no human
reviews are recorded, no real-device/provider acceptance has been completed,
and no production deployment or feature activation was performed.

## Exact-head CI and signed QA artifacts — 2026-11-01 10:48 IST checkpoint

At this checkpoint, **all five GitHub Actions workflows passed on each
branch's then-current head**. This supersedes earlier pending-status notes,
but these immutable SHAs are now historical because further hardening commits
were made afterward.

| PR | Verified head SHA | Backend CI | Web CI | Mobile CI | Production CI | Signed QA APK |
| --- | --- | --- | --- | --- | --- | --- |
| [#235](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/235) | `c70a4cc85a2bc904e39113c3c76697e2e231af5b` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272482992) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272483066) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272482979) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272482902) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272479542) |
| [#236](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/236) | `ad094e5049a15a0755d524c5da3d3935a0f34d88` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272494605) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272494529) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272494485) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272494555) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272490459) |
| [#237](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/237) | `5f2d2d6ac9e250c7bbe6ecdd0d41fd42025d2235` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272500704) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272500694) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272500702) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272500706) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272496138) |

The corresponding unexpired signed QA artifacts were:
[#235 artifact 13069758414](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272479542/artifacts/13069758414),
[#236 artifact 13069833273](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272490459/artifacts/13069833273),
and [#237 artifact 13068969674](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41272496138/artifacts/13068969674).
GitHub reported expiry on 2026-11-15 UTC. The QA workflow verifies the
existing permanent APK signing certificate against pinned SHA-256
`0b936a93cc249dd83131d92d23011158e7d17536724155ca312059c58f8e935b`.
A passing workflow is **not** evidence of physical-device installation.

### Additional changes after the green checkpoint

- Priority 1 now safely rejects malformed, truncated, out-of-range and
  oversized route polylines, preserving the live-tracking screen and markers
  if the routing provider sends invalid geometry. Added Flutter regression tests.
- The signed QA APK workflow now fails closed when the Google OAuth server
  client ID is absent; a signed artifact must not silently omit this Android
  sign-in configuration. This check is configuration presence, **not** proof
  that Google login works on a real handset.
- Priority 2 and 3 branches were reconciled with those Priority 1 changes,
  preserving the media implementation and release documentation.
- New exact-head CI and signed APK checks were triggered; **do not mark these
  newer commits verified until their workflows finish**.

No PR has an approving human review, and none is merged. Real-device
Firebase/Google, GPS/Maps, merchant/rider push, COD, payments, dispatch,
proof-of-delivery, production backup/restore and secure media configuration
remain unverified. **NO-GO for production; keep automatic dispatch and
product media disabled.**

## 11:54 IST checkpoint — exact-head CI and signed QA build verified

All four standard workflows (Backend, Web, Mobile, Production) and the
permanent-signer QA APK workflow completed **successfully** for the following
immutable heads **before the subsequent QA provenance change**:

| PR | SHA | Backend | Web | Mobile | Production | Signed QA APK |
| --- | --- | --- | --- | --- | --- | --- |
| [#235](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/235) | `fec740966acc65cfbc764d33e025cd92a9f17222` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276548058) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276547965) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276547968) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276547976) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276544505) |
| [#236](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/236) | `126b715d5fa57439a27551bfb183e095b84a7a08` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276568432) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276568554) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276568420) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276568395) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276563140) |
| [#237](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/237) | `b5adc2e43c3b0204dfbf4c68c42f6f93e00cb45a` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276591958) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276591999) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276591978) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276591967) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276586782) |

The respective QA artifact IDs are
[13071033485](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276544505/artifacts/13071033485),
[13071721086](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276563140/artifacts/13071721086)
and [13071696676](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41276586782/artifacts/13071696676).
All were unexpired when inspected; GitHub reports expiry on 2026-11-15 UTC.

After this green checkpoint, Priority 1 commit `190ceb0d` changed only the
QA workflow: QA Android version codes now increase with the GitHub workflow
run number, and artifacts include a text provenance manifest with commit,
run ID, build number, signer certificate SHA-256 and APK SHA-256. The
pinned permanent signing identity is unchanged. Priority 2 merge commit
`4e5942a0` and Priority 3 merge commit `44ebc59a` carry the same change
through the stacked branches. **These newer commits require fresh exact-head
CI and signed APK verification.** Do not infer their success from the green
baselines above.

No physical handset, provider integration, live payment, dispatch, media
storage, database restore or production deployment gate was passed by this
CI checkpoint. **NO-GO; keep automatic dispatch and product media disabled.**

## 13:50 IST checkpoint — recovered Web CI and permanent-signer QA builds

The Playwright tracking-outage race correction has now passed **all five**
GitHub Actions workflows at each of the following immutable heads. These
results were checked against the GitHub Actions run records and APK artifact
records, not inferred from an earlier branch run.

| PR | Exact SHA | Backend | Web | Mobile | Production | Signed QA APK |
| --- | --- | --- | --- | --- | --- | --- |
| [#235](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/235) | `3e6341d8658b13721849dbec8aa13da613cd164a` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284160315) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284160271) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284160267) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284160262) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284157165) |
| [#236](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/236) | `c0223fbb6c7d22b7dc9f7b05165b2e96f38188e8` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284182721) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284182696) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284182698) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284182787) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284178508) |
| [#237](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/237) | `6e9622ab701592f3ebf131d58824c53cd8e8895d` | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284192116) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284192175) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284192088) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284192141) | [pass](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284188357) |

Signed APK artifacts: [#235: 13074169741](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284157165/artifacts/13074169741),
[#236: 13073918604](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284178508/artifacts/13073918604),
[#237: 13074329354](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41284188357/artifacts/13074329354).
All three were unexpired when checked; GitHub reported expiration on
2026-11-15 UTC. The existing permanent signing-certificate check remains
in the workflow. Artifact success does **not** imply installation or sign-in
on a physical handset.

### Subsequent signed APK configuration hardening

Priority 1 now requires the Android Maps repository variable to be present
and nonblank, alongside Firebase and Google OAuth configuration, before
building a signed QA APK. Priority 2 and Priority 3 inherit that change
through their stacked integration commits. The check does not prove the
API key is correctly restricted or that Maps, location, or search works on a
device. **The new heads need fresh exact-head CI and signed APK verification.**

The release remains **NO-GO**: no human approving review, real-device
Google/Firebase/Maps/FCM acceptance, live COD/payment/dispatch/proof-of-delivery
acceptance, secure media provider validation, backup/restore verification, or
production deployment is recorded. Keep `AUTO_DISPATCH_ENABLED=false` and
`PRODUCT_MEDIA_ENABLED=false`.
