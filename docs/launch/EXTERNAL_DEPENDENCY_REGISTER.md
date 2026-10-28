# V1 external dependency register

Updated: 2026-10-28  
Audit baseline: `main` / `origin/main` = `ebe389de31d1d473f43a65cbaa41efa53ba0ccea`  
Scope: source and public-health evidence only. No provider console, secret, device, live-server, payment, or SMS action was performed.

## Status vocabulary

| Status | Meaning |
|---|---|
| Configured | Source and the required runtime/provider configuration have independently been evidenced. |
| Unconfigured | Source supports it, but required provider/runtime values have not been evidenced. |
| Not present | No launch implementation or configuration contract was found. |
| Optional/deferred | Not required for the Firebase + COD V1 candidate unless the owner enables that capability. |
| Broken/at risk | A concrete source or operating-contract concern needs remediation or an owner decision. |
| Unverified | A provider, device, field, or server acceptance check is still required. |

## Runtime and operations

| Dependency | Status | Code/configuration evidence | Required action and owner | Acceptance evidence |
|---|---|---|---|---|
| GitHub `main` and required CI | Configured for source validation / pending review | PR [#221](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/221) is open on head `c1deb71566bb2feb661f43d5139d580aaa070588`; all four gates passed on its prior head, but the cold-backup remediation requires fresh gates on the new head. The release fix is not on `main`. | Engineering: wait for the exact-head checks and merge only after explicit approval. | PR head, all four checks, and merge SHA recorded. |
| Self-hosted deployment runner and narrow sudo entry point | Unverified | `deploy/install_deploy_runner.sh` and the proposed root-owned `/usr/local/sbin/gaonone-release` contract live on PR #221, not `main`. | Owner/admin: after approved merge, provision the root-owned checkout and runner policy on the intended host. Do not run the installer from this audit. | `sudo -n -l`, path ownership/mode inspection, and a dry-run-safe release-contract check by the administrator; never disclose secrets. |
| Deployment environment designation | Broken/at risk | `AGENTS.md` describes the current host as staging despite `.env.production` and compose filenames; current `main` defaults `GAONONE_ENVIRONMENT` to `staging`; the production workflow uses a `staging` label. | Owner: formally designate whether `gaonone.in` is staging or production, record the expected authorization/approval rules, and use that label consistently. | Signed-off environment designation and a non-secret configuration review. |
| Caddy, DNS, TLS, and public domain | Partially configured / unverified | Public `https://gaonone.in/` returned HTTPS 200 through Caddy; `/api/v1/health` and `/api/v1/health/ready` returned healthy/ready on 2026-10-28. Compose expects `DOMAIN` and `ACME_EMAIL`. | Owner/admin: verify DNS ownership, firewall 80/443/UDP 443, ACME renewal contact, and no unintended origin exposure. | DNS/TLS inspection plus post-authorized-release smoke and monitor evidence. |
| PostgreSQL/PostGIS and Redis | Partially configured / unverified | `docker-compose.prod.yml` uses internal services and named `postgres_data`; public ready check reported database and Redis OK. | Owner/admin: verify persistent volume location, capacity, restart behavior, and restore drill. Never prune, delete, or recreate `postgres_data`. | Non-destructive host inspection and documented restore exercise. |
| Backups and recovery | At risk / remediation in review | `deploy/release.sh` runs `deploy/backup.sh` before migrations, which is correct. PR #221 head `c1deb71566bb2feb661f43d5139d580aaa070588` changes the media archive from `compose exec api` to a disposable `compose run --rm --no-deps api`, so it no longer needs the long-running API service. There is still no evidence of off-host retention or restore testing. | Engineering: await all four PR #221 checks and review; do not deploy it. Owner: choose protected off-host retention and conduct a restore drill. | Test coverage for a no-running-API media backup; restore verification with no production data loss. |
| Monitoring and alerting | Not present / unverified | `deploy/monitor.sh` checks services, HTTPS endpoints, disk/memory, and backup age; no external alerting or log-retention service is configured. | Owner: select an operational monitoring/alerting and log-retention owner before release. | Alert delivery test and documented on-call/recovery procedure. |

## Identity, authentication, and messaging

| Dependency | Status | Code/configuration evidence | Required action and owner | Acceptance evidence |
|---|---|---|---|---|
| Firebase Admin token verification | Unconfigured | Backend expects `FIREBASE_PROJECT_ID` and `FIREBASE_SERVICE_ACCOUNT_JSON_B64` when `AUTH_PROVIDER=firebase`; `/auth/firebase/exchange` establishes GaonOne sessions. Production validation rejects missing values. | Owner: create/select Firebase project and place service-account material only through the server's secure secret channel. Engineering must never receive or commit it. | Token exchange with a non-production test account; invalid token, repeat-login, and role-boundary checks. |
| Google sign-in, web | Unconfigured | Web uses public Firebase web configuration (`NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_APP_ID`) and exchanges the Firebase ID token with the backend. | Owner: enable Google provider and configure exact HTTPS authorized domains/origins for launch. | Popup, cancellation, error, session restoration, logout, and backend exchange on the real launch domain. |
| Google sign-in, Android | Broken/at risk | Android application ID is `in.gaonone.gaonone_mobile`; Firebase options are runtime Dart defines. Release uses the debug signing config. | Owner: choose release signing/Play App Signing path, protect the keystore, register debug/release/Play SHA fingerprints, and provide non-secret configuration through the approved build path. | Signed internal-distribution build, real-device sign-in, logout, repeat-login, and offline retry checks. |
| Google sign-in, iOS | Broken/at risk | Flutter options hard-code `in.gaonone.gaonone_mobile`; Xcode project uses `in.gaonone.gaononeMobile`; no Google URL scheme was found in `Info.plist`. | Owner: choose one canonical bundle identifier before any Firebase/Apple registration; provision Apple team/signing and configure the Firebase callback scheme. | Physical-device sign-in/cancellation/logout on an owner-signed build. |
| Direct OTP / MSG91 | Optional/deferred | Firebase launch defaults `SMS_AUTH_ENABLED=false`; production validation rejects `DEV_OTP` and requires MSG91 fields only when SMS is enabled. | Owner: do nothing for Firebase + Google V1. If later enabled, complete MSG91 account, DLT, sender/template, balance, and secure server secret setup. | Provider sandbox/test-number flow, rate limits, and no dev OTP in deployed environment. |
| Firebase Cloud Messaging | Partially implemented / deferred | Backend supports FCM outbox delivery when FCM credentials are configured, but web has no registration flow and Flutter has no `firebase_messaging` client integration. | Engineering/owner: do not set FCM production credentials as a substitute for client registration. Plan a separate push-client phase if notifications are required. | Client permissions, device-token lifecycle, APNs (iOS), delivery, and opt-out tests. |

## Commerce, location, and media

| Dependency | Status | Code/configuration evidence | Required action and owner | Acceptance evidence |
|---|---|---|---|---|
| COD checkout | Configured in source / unverified in field | COD remains available when Razorpay is absent; server pricing, serviceability, stock, and payment state remain authoritative. | Owner/operations: test the full customer-to-rider COD handoff on a non-production candidate. | Controlled field order, exact collection, proof, settlement, cancellation/refund recovery evidence. |
| Razorpay | Optional/deferred | Backend supports orders, signatures, webhook verification, and refunds; `.env.production.example` leaves all Razorpay values blank. | Owner: decide whether UPI is in V1. If yes, establish account/KYC, test-mode credentials, restricted webhook secret, endpoint, and billing/operations owner. | Test-mode payment and signed webhook recovery; no real money during validation. |
| Google Maps Platform | Unconfigured / conditional | Backend can use Places, Geocoding, and Routes with `MAPS_PROVIDER=google` and `MAPS_API_KEY`; web can use `GOOGLE_MAPS_BROWSER_KEY` and optional map ID. Source keeps these off by default. | Owner: decide whether address autocomplete, reverse geocoding, routing, or embedded web maps are launch-critical. If enabled, create separate server/browser keys with least-privilege restrictions and billing limits. | Restricted-key verification, quota/billing alert, address and route acceptance tests. |
| OpenStreetMap public tiles | Unverified / conditional | Flutter live tracking uses `https://tile.openstreetmap.org/...` with visible attribution. | Engineering/owner: confirm User-Agent/cache behavior and expected load against the [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/); use an appropriate provider or self-hosted tiles if the policy cannot be met. | Policy-compliant real-device map test and capacity decision. |
| Legacy uploaded media volume | Partially configured / unverified | API stores uploads in mounted `media_data`; backup script archives `/app/data/uploads`. | Owner: include volume backup/recovery in the selected retention policy. | Upload/retrieve/restore test. |
| Product-media object storage and scanner | Optional/deferred | `PRODUCT_MEDIA_ENABLED=false`; production config requires S3-compatible distinct buckets and a scanner when enabled. No active provider configuration was evidenced. | Keep disabled for V1 unless the owner approves a separate media-security phase. | Quarantine, scanner, MIME, authorization, retention, and recovery tests. |
| Merchant catalog-image UX | Broken/at risk / deferred | Existing merchant media upload returns a URL, but this audit did not find an evidenced attachment/display path for catalogue imagery. | Product owner: defer/label the surface accurately or define a separately reviewed product-media workflow. | Merchant upload-to-catalogue-to-customer-display acceptance test. |

## Absent or deliberately deferred services

| Capability | Status | Finding | Decision needed |
|---|---|---|---|
| Transactional email | Not present | No SMTP/provider integration or email-dependent V1 workflow was found. | None unless email becomes a V1 requirement. |
| External search | Not present | Discovery/search is backed by the application database; no hosted search integration was found. | None for V1. |
| Product analytics and crash reporting | Not present | No active analytics/crash SDK initialization was found. | Owner may select a privacy-reviewed service after launch; it is not a release substitute. |
| External payment/SMS activation | Optional/deferred | Neither should be activated merely because code exists. | Explicit owner scope and provider approval required. |

## Authority and security rules

- Public Firebase web configuration is not a server secret; Firebase Admin credentials, `SECRET_KEY`, database credentials, provider secrets, and private signing keys are secrets and must never be committed or passed through broad sudo preservation.
- Firebase proves identity only. GaonOne issues its own session and derives roles/permissions server-side; neither Firebase claims nor client state authorize privileged actions.
- No entry in this register authorizes a deployment, provider-console change, secret sharing, paid SMS, paid payment, or live-server modification.
