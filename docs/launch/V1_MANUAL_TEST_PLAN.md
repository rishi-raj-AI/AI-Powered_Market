# V1 manual acceptance and field test plan

Updated: 2026-10-28  
Use only after the owner has completed the applicable secure configuration prerequisites. This plan does not authorize a deployment, paid SMS, paid payment, or production data creation.

## Evidence rules

- Record the exact Git SHA, environment designation, device/OS/browser, role, test account type, network condition, result, and defect reference.
- Never include passwords, tokens, phone numbers, service-account JSON, payment information, or customer PII in evidence.
- A source/CI pass is not a substitute for a real-device, provider, visual, or field pass.
- Test in an isolated acceptance environment where possible. Use test-mode provider credentials and a controlled COD order; do not create a real financial obligation.
- Stop immediately on unintended production traffic, authorization leakage, data corruption, or a public availability regression.

## Entry gates

| Gate | Required evidence |
|---|---|
| Candidate provenance | Exact SHA, four required CI gates, no unexplained protected-checkout changes, and approved merge history. |
| Environment | Owner-designated staging/production label, target domain, non-secret CORS/trusted-host validation, and authorized tester list. |
| Identity | Firebase server and public client configuration in the approved secure locations; Google provider and exact authorized origins configured. |
| Mobile | Canonical Android package and iOS bundle identifier, owner signing/distribution path, valid test builds, and real test devices. |
| Operations | Restore-tested backup record, on-call/recovery contact, baseline monitor/log inspection, and a roll-forward/rollback decision owner. |
| Payments/SMS/maps | Explicitly marked enabled or deliberately disabled. Test only the enabled scope. |

## Identity and session boundary

| ID | Scenario | Expected result | Evidence |
|---|---|---|---|
| AUTH-01 | Web Google sign-in on the exact approved HTTPS origin | Google authentication succeeds, Firebase ID token is exchanged only with GaonOne backend, and app session becomes authenticated. | Browser capture with identifiers redacted; backend audit/session outcome. |
| AUTH-02 | First login with a new provider account | One customer account and one external identity are established; no phone is invented and no arbitrary email account is linked. | Admin-safe record count/query result without PII. |
| AUTH-03 | Repeat login and refresh | Existing identity resolves to the same GaonOne account; no duplicate identity/account is created. | Account/identity continuity evidence. |
| AUTH-04 | Invalid/expired/wrong-project token | Exchange is rejected without granting a session or elevated role. | Redacted response/status and absence of session. |
| AUTH-05 | Popup cancellation/provider failure | Clear recoverable UI state; no stale local token or false success. | Screen recording or screenshot. |
| AUTH-06 | Logout while provider sign-out is unavailable | Local GaonOne session is cleared; protected API/UI access is not retained. | Network/UI result. |
| AUTH-07 | Browser/app relaunch after valid session then expired session | Valid session restores as designed; expired session is cleared and returns safely to sign-in. | Before/after state and redacted API outcome. |
| AUTH-08 | Role tampering attempt from client/Firebase claims | Server permissions, not client/Firebase claims, govern merchant/rider/admin actions. | Denied endpoint/UI outcome for a low-privilege account. |

## Customer journey

| ID | Scenario | Expected result |
|---|---|---|
| CUST-01 | Discover stores and products with location denied, weak signal, and a landmark address | Honest loading/error/empty states; no false serviceability or stale result. |
| CUST-02 | Add/update cart rapidly and recover after a simulated network interruption | One authoritative cart state; no duplicate mutation or misleading price/quantity. |
| CUST-03 | Save/select a landmark-based delivery address and quote delivery | Address state, quote, serviceability, and cart remain consistent; user can recover from a failed/late response. |
| CUST-04 | Place a COD order, revisit the order, and refresh state | One intended order, server-authoritative stock/price/serviceability, truthful status. |
| CUST-05 | UPI/Razorpay path, only if owner enabled it in test mode | No fulfilment before confirmed payment; signed confirmation/webhook behavior is correct. |
| CUST-06 | Hindi/Marathi and narrow 320/390px layouts | Key actions remain readable, operable, and not obscured; no untranslated critical error makes recovery impossible. |

## Merchant, rider, support, and admin journeys

| ID | Scenario | Expected result |
|---|---|---|
| OPS-01 | Merchant accepts/rejects/packs eligible order; refresh or interruption occurs | Server transition remains authoritative; UI reconciles without duplicate/invalid action. |
| OPS-02 | Rider sees only assigned task, navigates, records proof, collects exact COD, and completes | Assignment scope, proof challenge limits, conditional COD collection, and completion rules are enforced. |
| OPS-03 | Support files/retries ticket, changes permitted state/assignee, and encounters a failed refresh | No duplicate ticket, no false finality, and explicit recovery/refresh behavior. |
| OPS-04 | Admin uses capability-derived controls and attempts an unauthorized or financially sensitive recovery | Affordances fail closed and backend rejects insufficient authority. |
| OPS-05 | Merchant media upload surface (if visible) | Do not claim a catalogue image was updated unless an end-to-end customer-visible attachment is demonstrated. |

## Device, map, and notification testing

| ID | Scenario | Expected result |
|---|---|---|
| DEV-01 | Android signed internal build: sign-in, cold start, background/foreground, logout | Same identity/session guarantees as web; no debug-signed release artifact. |
| DEV-02 | iOS owner-signed physical device: sign-in/callback, cancellation, relaunch, logout | Canonical bundle ID and callback scheme work; no provider loop. |
| DEV-03 | GPS denied/approximate/unavailable and intermittent connectivity | App explains recoverable state; delivery/location operations do not silently assert accuracy. |
| DEV-04 | Web embedded map and address autocomplete, only if Maps enabled | Browser key restrictions, billing/quota, map fallback, and address behavior pass. |
| DEV-05 | Flutter live tracking with OSM tiles | Visible attribution, policy-compliant requests, graceful degraded state, and no excessive tile traffic. |
| DEV-06 | Push notification, only after a separate client push implementation | Permission, token registration, delivery, opt-out, and APNs/Android behavior pass. |

## Release and recovery rehearsal

| ID | Scenario | Expected result |
|---|---|---|
| REL-01 | `make prod-check` using the real non-secret environment | Validation passes with explicit environment/SHA policy; no secret is printed. |
| REL-02 | Pre-deployment backup | Database and media backup complete before migration; a cold API-container prerequisite is resolved or fails safely before migration. |
| REL-03 | Normal release of a controlled candidate | Proxy is running before HTTPS smoke, all services are healthy, exact SHA is recorded. |
| REL-04 | Verification failure in a safe rehearsal | Code rollback uses a known-good SHA, keeps the additive migrated schema, starts proxy, and passes smoke/monitor or escalates clearly. |
| REL-05 | Restore drill | Database and media can be restored to an isolated target; production PostgreSQL volume remains untouched. |

## Exit criteria

- Every applicable P0/P1 case passes or has an explicit written owner waiver with risk acceptance.
- All defects are recorded in [V1_BUG_BACKLOG.md](V1_BUG_BACKLOG.md), with no open P0 and no unaccepted P1.
- The release checklist is complete for one exact candidate SHA and the owner explicitly authorizes the next stage.
