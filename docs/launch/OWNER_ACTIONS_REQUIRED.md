# Owner actions required for a V1 release candidate

Updated: 2026-10-28  
Current source baseline: `ebe389de31d1d473f43a65cbaa41efa53ba0ccea`  
This is an action register, not a request to send secrets in chat or commit them to the repository.

## P0 — must close before release-candidate authorization

1. **Name the live environment and its authority.**
   - Decide and record whether `gaonone.in` is staging or production. The current repository language is inconsistent: runtime files are named production while `AGENTS.md` describes the host as staging.
   - Provide a named owner for approvals, rollback, backup restore, and release acceptance.
   - Required evidence: non-secret server inventory, approved environment designation, and a release authorization policy.

2. **Establish the Firebase/Google identity project through a secure owner channel.**
   - Enable Google as an approved Firebase Authentication provider.
   - Configure exact web authorized domains/origins; do not add wildcards or unneeded localhost production entries.
   - Add the server-only Firebase Admin configuration to the host secret store: `FIREBASE_PROJECT_ID` and `FIREBASE_SERVICE_ACCOUNT_JSON_B64`.
   - Supply only the intentionally public web configuration through the build environment: `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, and `NEXT_PUBLIC_FIREBASE_APP_ID`.
   - Required evidence: real-domain sign-in, rejected invalid token, first/repeat login, session restoration, logout, and server-role boundary checks. No secret values in PRs, tickets, screenshots, logs, or chat.

3. **Choose a canonical iOS bundle identity before registering iOS Firebase or Apple assets.**
   - The source currently disagrees: Flutter Firebase options name `in.gaonone.gaonone_mobile`; the Xcode target names `in.gaonone.gaononeMobile`.
   - Select one owner-controlled identifier, Apple App ID, and Firebase iOS app registration. Then configure the Google callback URL scheme and the Apple team/signing profile.
   - Required evidence: signed physical-device build and Google sign-in/cancellation/logout test.

4. **Establish Android release-signing and distribution ownership.**
   - The current release build is explicitly debug-signed. Choose the protected-keystore/Play App Signing path, enrollment account, package identity, and access owners.
   - Register the resulting debug, release, and Play App Signing SHA fingerprints with Firebase as appropriate.
   - Required evidence: signed internal-distribution build, real-device Firebase sign-in, token exchange, logout, and recovery under poor connectivity.

5. **Authorize a non-destructive server inspection and backup/restore proof.**
   - Identify the actual runtime checkout, `.deployed-sha` record, named volumes, backup location, retention, and restore operator without printing `.env.production`.
   - Prove that database and uploaded-media backups can be restored in a safe non-production target. Never delete, prune, or recreate the production PostgreSQL named volume.
   - Required evidence: a timestamped non-secret restore record and the approved recovery procedure.

## P1 — required before enabling the related V1 capability

1. **Approve and merge release-control PR #221 only after normal review.**
   - PR #221 is green on its final head but remains open. Its root-owned runner installation and proxy/selector safeguards do not exist on current `main` or the live server.
   - After an explicit merge decision, an authorized administrator must provision the narrow runner path. No general root shell, arbitrary `env`, arbitrary Docker access, caller-selected checkout, or preserved secret environment is acceptable.

2. **Resolve the pre-migration media-backup runtime prerequisite.**
   - `deploy/backup.sh` invokes the running API container to archive media. A cold/failed API container safely prevents migration, but the deploy procedure currently does not make that prerequisite explicit or eliminate it.
   - Engineering will prepare a narrow, separately reviewed remediation that preserves backup-before-migration order and forward-only rollback safety. Owner acceptance is needed before any production use.

3. **Make the domain/CORS/TLS boundary explicit.**
   - Confirm the public domain, required browser origins, trusted hosts, reverse-proxy ports, certificate contact, and direct-origin firewall rules.
   - Required evidence: `make prod-check` on the real non-secret environment plus an approved external-domain inventory.

4. **Decide map scope.**
   - GPS/serviceability can operate without Google Maps. Address autocomplete, reverse geocoding, route calls, and web map rendering cannot.
   - If enabled, create separate server and browser keys, restrict them to required APIs/origins/IPs, set billing quotas/alerts, and keep server keys out of the browser. Google’s [key-security guidance](https://developers.google.com/maps/api-security-best-practices) recommends per-app keys and restrictions.

5. **Complete field and visual acceptance.**
   - Test customer, merchant, rider, and admin critical journeys at narrow/mobile layouts; Hindi/Marathi copy boundaries; landmark addresses; low-connectivity/retry behavior; COD delivery/proof/settlement; and accessibility/touch targets.
   - Required evidence: named build SHA, role, device/OS/browser, scenario, result, screenshots/logs without PII or secrets, and defect disposition.

## Optional/deferred decisions — do not activate by default

| Capability | Owner decision before enabling | Safe V1 default |
|---|---|---|
| MSG91/direct OTP | Account, DLT/sender/template, billing/abuse handling, secret placement, test numbers | Firebase Google sign-in with SMS disabled |
| Razorpay / UPI | Provider account/KYC, test-mode acceptance, webhook secret and operations/reconciliation owner | COD only |
| FCM push | Product scope, client registration/token lifecycle, Android/iOS permissions/APNs, server credential ownership | In-app notification history only |
| Product media S3/scanning | Storage/scanner provider, quarantine, lifecycle, privacy/security owner | Keep `PRODUCT_MEDIA_ENABLED=false` |
| Analytics/crash reporting | Privacy/legal review, consent/retention, cost and access owner | No third-party telemetry is required for V1 candidate |

## Safe owner evidence bundle

Provide references or a secure owner-side attestation for the following, without embedding sensitive values:

- the intended host and environment classification;
- a timestamped exact deployed SHA and `.deployed-sha` value;
- Firebase project identifier and successful non-secret test results (not service-account JSON);
- canonical Android package and iOS bundle identifier, signing/distribution owners, and real-device test evidence;
- DNS/TLS/CORS inventory and operational contacts;
- backup/restore and monitoring/alerting evidence;
- explicit go/no-go authorization for an exact candidate SHA.

Nothing in this file authorizes deployment, production configuration changes, paid provider activation, or merge of an open PR.
