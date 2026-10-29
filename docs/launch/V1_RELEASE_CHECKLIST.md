# V1 release-candidate checklist

Updated: 2026-10-28  
Candidate SHA: _not selected_  
Environment designation: _owner decision required_  
Deployment authorization: **not granted**

## 1. Source and change control

- [ ] Candidate is an exact immutable `main` SHA with its merge history recorded.
- [ ] All four required checks are green on that exact SHA: `backend-check`, `build-and-ui`, `analyze-and-build-android`, `production-compose-and-images`.
- [ ] Open release-control PR #221 is either merged after normal approval or explicitly excluded with a documented equivalent safeguard.
- [ ] The backup prerequisite remediation has been reviewed and its regression tests pass.
- [ ] No committed secrets, accidental `.env.production`, credentials, or private signing material are present.
- [ ] Protected local main was updated only with fast-forward semantics and its known owner-owned Flutter/iOS changes remain byte-for-byte intact.
- [ ] No unexplained tracked or nonignored local changes are present in the protected checkout.

## 2. Environment and infrastructure

- [ ] Owner has formally designated the target as staging or production and named the approval/recovery owner.
- [ ] Actual server checkout HEAD and `.deployed-sha` are recorded without exposing secrets.
- [ ] `DOMAIN`, `PUBLIC_BASE_URL`, CORS, trusted hosts, ACME contact, firewall, and direct-origin policy are reviewed.
- [ ] `make prod-check` succeeds with the target's secure configuration.
- [ ] Docker/PostgreSQL/PostGIS/Redis persistent-volume capacity and restart behavior are inspected; `postgres_data` has never been deleted, pruned, or recreated.
- [ ] Backup completes before migrations, media backup has a safe cold-start contract, and backup artifacts are retained off host according to owner policy.
- [ ] Isolated database/media restore drill passed.
- [ ] Monitor/log/alert owner and recovery contacts are recorded.

## 3. Identity and mobile distribution

- [ ] Firebase project and Admin service account are installed only through the server secret channel.
- [ ] Google provider and exact web OAuth domain/origin configuration are verified.
- [ ] Firebase exchange rejects invalid tokens and preserves server-authoritative roles/permissions.
- [ ] First/repeat login, session restoration, logout, cancellation, and provider-failure flows pass on the real web origin.
- [ ] One canonical Android package, iOS bundle identifier, and Firebase registration set are selected and recorded.
- [ ] Android signed internal-distribution build passes real-device acceptance; debug/release/Play fingerprints are correctly registered.
- [ ] iOS owner-signed physical-device build passes callback, sign-in, cancellation, restoration, and logout acceptance.

## 4. Product and operations acceptance

- [ ] Customer discovery, landmark address, cart, quote, COD checkout, order tracking, and recovery paths pass under normal and poor connectivity.
- [ ] Merchant, rider, support, and admin critical workflows pass with server capability/ownership boundaries enforced.
- [ ] COD proof, exact collection, settlement, cancellation, and dispute/recovery procedures are rehearsed.
- [ ] Narrow/mobile layout, Hindi/Marathi critical copy, accessibility, touch targets, and low-end-device evidence are reviewed.
- [ ] Maps, Razorpay, MSG91, FCM, and product media are each explicitly enabled with provider acceptance or explicitly kept disabled/deferred.

## 5. Authorized deployment and verification

- [ ] Human owner has authorized deployment of one exact SHA to the named environment.
- [ ] Runner is restricted to the root-owned fixed entry point; only non-secret `GAONONE_EXPECTED_SHA` and `GAONONE_ENVIRONMENT` selectors cross sudo.
- [ ] Pre-deployment database/media backup record exists before any migration.
- [ ] Exact SHA guard passes; target does not advance unexpectedly.
- [ ] Normal release starts `api`, `web`, `worker`, and `proxy`; proxy is confirmed before HTTPS smoke tests.
- [ ] Post-deploy smoke verifies homepage, health, readiness, `.env` denial, and safe root POST behavior.
- [ ] Post-deploy monitor verifies services, disk/memory, endpoints, and recent backup age.
- [ ] Any failure follows the documented code rollback, preserves forward-only schema reality, restarts proxy, and has a named human recovery escalation.

## 6. Final decision

| Decision | Owner | Timestamp | Candidate SHA | Notes |
|---|---|---|---|---|
| Go / no-go | _pending_ | _pending_ | _pending_ | This row must be completed by the owner; it cannot be inferred from CI. |

See [V1_MANUAL_TEST_PLAN.md](V1_MANUAL_TEST_PLAN.md), [V1_BUG_BACKLOG.md](V1_BUG_BACKLOG.md), and [OWNER_ACTIONS_REQUIRED.md](OWNER_ACTIONS_REQUIRED.md) for evidence requirements.
