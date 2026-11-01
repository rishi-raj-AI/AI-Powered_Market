# GaonOne V1 Priority 1–3 release acceptance

This document is a **release gate**, not evidence that a gate has passed. The
application is a single marketplace for customers, merchants and delivery
partners (food, grocery, farm supplies, hardware, general retail and parcels).
Passenger transport is out of scope.

## Gate 1 — integrated code and CI

- [ ] Merge the reviewed Priority 1 integration PR after **Backend CI, Web CI,
      Mobile CI and Production CI** all pass on the exact head SHA.
- [ ] Confirm the merchant media workflow PR passes Web CI and backend media
      ownership/security tests before merging.
- [ ] Record the exact commit, migration head, environment and reviewer.
- [ ] Verify no newly introduced failing or skipped critical tests. A passing
      Next.js build alone does **not** satisfy Playwright acceptance.
- [ ] Re-run PostgreSQL dispatch concurrency tests with the actual PostGIS DB.
      Ensure a rider cannot hold two active deliveries across manual claim,
      admin assignment and worker auto-dispatch.

## Gate 2 — signed Android QA build

- [ ] Build using the repository **GaonOne QA APK** workflow, with the existing
      permanent signing keystore from protected GitHub Actions secrets.
      **Never create a replacement signing key** to make a build pass.
- [ ] Confirm the workflow verifies the APK certificate SHA-256 fingerprint
      against the pinned release identity. Record the workflow run URL, head
      SHA, artifact name, version code and signer fingerprint.
- [ ] Install that **exact artifact** on a low-end Android handset. A Flutter
      analyzer or unit-test pass is not an installed-app acceptance result.
- [ ] Verify the GaonOne launcher icon, Android launch, Google sign-in, logout,
      session expiry, Firebase push registration, Hindi/Marathi text, 44px+
      controls, slow network and intermittent connectivity.
- [ ] Validate Google Maps location search, GPS permission denial, manual
      landmark address entry and no-GPS recovery.
- [ ] Do not publish or distribute an unsigned or debug-signed APK as release.

## Gate 3 — end-to-end marketplace operations

On a staging or explicitly approved pilot environment, use separate real
customer, merchant and rider accounts and preserve evidence for each step.

| Test | Required evidence |
| --- | --- |
| COD checkout | Cart shows Place order, checkout confirms COD choice, order and stock commit once, retry is idempotent |
| Online payment | Real gateway callback and reconciliation, pending payment cannot release goods |
| Merchant alert | New order creates merchant notification; registered handset receives FCM or in-app fallback; delivery state is distinguishable from confirmed receipt |
| Rider alert | Assignment creates rider notification and customer update, no duplicate dispatch |
| Automatic rider selection | Worker chooses active, verified, online rider with fresh GPS inside configured radius; unavailable riders remain unassigned |
| Rider contention | Concurrent manual and automatic assignments never give one rider two active jobs |
| Delivery custody | Pickup, delivery proof and COD collection are recorded with actor, timestamp and auditable status transitions |
| Recovery | Failed delivery, reassignment, return-to-store, cancellation, refund and settlement follow permission gates and preserve audit records |
| Merchant controls | Approve/suspend/reactivate merchant, review owner and stores; suspended stores disappear from public listings |
| User controls | Pre-register, verify identity, deactivate/reactivate and change role; super-admin is protected and actions audited |
| Product photos | Quarantine upload is private, listing-owned and size/type checked; only approved derivative is publicly accessible |
| Accessibility | Test at 320px, 390px and desktop widths; no horizontal overflow, keyboard access and no serious/critical accessibility findings |

## Gate 4 — production configuration and safe rollout

Before deployment, verify required variables by **name/presence only**, never
print secret values or paste keystores into logs.

- [ ] Production Firebase/Google identity provider, OAuth authorized domains,
      Maps API key restrictions, FCM service credentials and Google Play
      signing configuration match the intended Android application ID.
- [ ] Razorpay and SMS/OTP provider configuration is validated in the relevant
      payment/auth mode; CSP permits only required Google, Firebase and
      payment origins.
- [ ] Postgres backup/restore, migrations, Redis, worker and web/API health
      checks pass. Capture rollback commit and database recovery plan.
- [ ] Keep `AUTO_DISPATCH_ENABLED=false` until live concurrency and
      notification acceptance passes. When approved, enable a bounded batch
      and radius, observe assignment logs, rider workload and unmatched queue.
      Rollback: disable the flag and restart the worker; manual dispatch remains.
- [ ] Keep `PRODUCT_MEDIA_ENABLED=false` until secure S3-compatible
      quarantine storage, derivative public origin, worker processing, orphan
      cleanup and upload owner checks are verified. The legacy public upload
      endpoint must never bypass quarantine once enabled.
- [ ] Verify `https://gaonone.in/api/v1/health` returns 200, TLS is valid,
      deployment SHA is recorded, and the frontend is serving that SHA.
- [ ] Perform real-device smoke tests **after** deployment; green CI does not
      prove real Firebase, Maps, payments or FCM integration.
- [ ] Obtain explicit release approval before enabling automatic dispatch,
      changing production payment settings or distributing the signed APK.

## Evidence log template

Record for each gate: date/time (IST), owner, environment, exact commit SHA,
workflow URL, device model/Android version, outcome (pass/fail/not tested),
evidence link, defect ID, and remediation/rollback decision.

Do not mark Priority 1–3 complete until all required gates have actual
evidence. Unavailable credentials, signing identity or device verification
must be reported as blockers, never silently replaced with assumptions.
