# GaonOne — Phone OTP, registration, login and profile UX acceptance

Written read-only assessment,14 September2026. Inspected primary checkout HEAD `131e30281d03332c462ba9dd0009bce3cdbb0c9e`. No Figma, application, Git, provider account or deployment changes. No real SMS was sent and no credentials were inspected. Criteria apply to existing UI; no redesign or additional identity system is proposed.

## Confirmed source contract

Sources: backend auth/user routes and schemas, services/otp.py, core/config.py; web login and API wrapper; Flutter login, account screen and main bootstrap.

- POST `/api/v1/auth/request-otp`: phone length8–20; response message and optional dev_otp. No challenge id, expires_at, retry_after or remaining-attempt fields supplied.
- POST `/api/v1/auth/verify-otp`: phone8–20, otp4–8, optional full_name max120. Returns access_token/token_type.
- POST `/api/v1/auth/widget/exchange`: widget access_token20–4096, optional full_name max120; backend verifies widget identity before login. Widget callback alone is not an authenticated GaonOne session.
- Verified new phone creates a user; existing active user is reused. Optional name only fills a missing existing name; it does not edit an existing nonempty name. Existing inactive account returns403. No separate registration endpoint or new/returning flag is returned.
- GET `/api/v1/users/me` supplies id, phone, optional full_name, role, is_super_admin, is_active, is_verified, created_at and updated_at. Inspected user routes contain no profile-update endpoint. No phone-change, avatar, email, DOB or password field is authorized by this contract.
- Direct OTP routes return410 when APP_ENV=production and AUTH_PROVIDER=msg91_widget. Web currently opens the widget, which owns phone/CAPTCHA/resend/verification UI. Flutter currently calls direct request/verify routes. Deployed configuration and provider behavior are NOT CHECKED; do not generalize the production-only410 condition to every staging setup.
- Code defaults: OTP TTL300s, send window900s/max5 requests, max6 verification attempts; access-token lifetime60min. These are defaults, not verified deployed/provider timings. Direct response does not expose remaining timing. Provider verification failures and expiry can collapse into “Invalid or expired OTP”; do not invent distinct server error reasons.

## Concrete acceptance matrix

All cases NOT RUN by Design; engineering evidence required.

| ID | Scenario | Expected existing-flow behavior |
|---|---|---|
| AUTH-01 | Enter phone | Visible label and telephone keyboard; country context clear; retain input on errors. Canonical normalization rules must come from Engineering, not frontend-only assumptions. Name remains optional and max120; no mandatory profile wizard. |
| AUTH-02 | Start OTP | One pending operation; deterministic accessible action label. Distinguish provider/widget loading from SMS requested and from verified login. Do not claim SMS delivered just because request accepted. |
| AUTH-03 | Resend/cooldown | Use widget-authoritative controls when widget owns OTP. For direct flow provide a usable resend/change-number route only against approved contract; no invented30/60s timer.429 explains temporary limit; display exact countdown only from authoritative timing. No automatic background SMS resend. |
| AUTH-04 | Wrong/expired/attempt-limited OTP | Keep phone context; allow appropriate recovery. Current combined400 message cannot justify an exact expired/incorrect/remaining-attempt diagnosis. No unsupported “one attempt left” text. |
| AUTH-05 | Change phone after code request | Old code cannot be presented as valid for newly edited phone; reset challenge UI or require a new request. Flutter currently leaves phone editable after otpSent; verify and correct this association in Engineering. |
| AUTH-06 | Widget failure/CAPTCHA/cancel/SDK timeout | Recover without duplicate widget flows; preserve optional name; accessible safe error and retry. Human verification stays human-controlled. Do not expose raw provider JSON, tokens or secrets as user messages/logs. |
| AUTH-07 | Widget callback → exchange → /me | Each stage has truthful pending/failure state. Duplicate callbacks/repeated Continue cannot cause competing exchanges. Network failure after token issuance should retry session/profile confirmation, not force another SMS by default. |
| AUTH-08 | New phone / returning phone | Same verified flow, no guessed new-user welcome or duplicate account. Returning user's nonempty name not silently overwritten. Only server role determines destination; phone verification never grants merchant/admin privileges. |
| AUTH-09 | Profile display | Show actual phone/name from /me; absent name treated as optional, not corrupted profile. No fake Save/edit success when no profile mutation exists. Address and merchant application remain separate existing domains. |
| AUTH-10 | Profile edit expectation | Current contract supports no general edit. If user requires edit, Engineering must propose minimum authorized update fields/validation; scope approval required before drawing unsupported controls. Phone change is separate security-sensitive work, not a normal name edit. |
| AUTH-11 | Offline/slow startup | Preserve a stored session during transient /me transport/5xx failure and show retry/unknown state; do not assert expired or verified from an unavailable response. Flutter's broad bootstrap catch currently logs out for all failures: concrete functional gap. |
| AUTH-12 |401 versus403 |401 invalid/expired session follows existing sign-in recovery;403 shows permission/account restriction without retry loop or privilege bypass. Do not clear a valid session merely for an unrelated forbidden action. |
| AUTH-13 | Logout | Clear current local token and sensitive UI state, return to unauthenticated view, avoid stale async responses restoring profile. No “logged out everywhere” claim: server-wide session revocation is not established by inspected contract. |
| AUTH-14 | Return after expiry | Web wrapper records ?next but login currently routes only by role. Verify safe internal return navigation before promising return to prior task; reject external destinations. Do not restore restricted pages for the wrong role. |
| AUTH-15 | Hindi/Marathi and large text | EN/HI/MR labels/errors fit30–50% expansion and200% text at320/360/390;48px targets, keyboard does not obscure Verify/Retry. Accessible name/help/error association and restrained status announcements. Widget locale/glyph/keyboard support requires actual provider UI validation, not app dictionary claims. |
| AUTH-16 | Real device / real OTP | On approved staging configuration verify actual SMS receipt, valid/invalid/expired/resend, new/returning user, optional name, disabled account, cold start/logout/expiry. Development OTP and API mocks are not real-provider evidence. Never put OTP/token/private phone in reports. |
| AUTH-17 | Mobile provider compatibility | Exercise the exact release build against intended auth mode. Current web-widget/direct-Flutter mismatch requires Engineering assessment; production widget mode rejects direct routes. No new provider/SDK or bypass selected by Design. |

## Current implementation gaps needing bounded Engineering assessment

Web Name label lacks explicit input association; error/status text lacks explicit announcement semantics; provider errors can fall back to serialized raw response; repeated widget launch remains possible after initialization; login ignores the wrapper's next destination. Verify these source observations with focused tests before patching.

Flutter has no explicit resend/change-number flow after otpSent; name's optionality is unclear; startup network failure clears stored login. Existing account view is not a general editable profile. None of these findings authorizes replacing authentication architecture.

## Phased release gates

1. **Contract/environment assessment:** confirm intended web/mobile auth mode, normalization, active staging provider readiness without exposing secrets. Document actual timing/error semantics and profile scope. No deployment readiness claim from code defaults.
2. **Functional candidate:** minimal existing-UI fixes and direct tests for AUTH-01–14/17; real hydrated/device behavior, not static specimens alone. Preserve existing backend identity, ownership and authorization. Exact-SHA CI through Git.
3. **Staging real-provider acceptance:** authorized test phones and real SMS with consent; actual supported web and low-end Android release candidate; network loss/recovery and session lifecycle. Record build/SHA/environment and redacted results. Human CAPTCHA or SMS entry may require user participation; never bypass.
4. **Mobile release readiness:** functional Android artifact, intended endpoint/provider configuration, signing/distribution ownership, upgrade/session behavior, device acceptance and release channel approved. Debug APK/CI success alone is not release approval.
5. **Visual QA:** existing Figma STOP remains. Functional release acceptance must explicitly record outstanding Figma verification; do not call typography/localization/widget visuals approved from written criteria. Product/Master determines whether the functional phase may ship with that known visual gate unresolved.

## Decisions genuinely required

- Does “profile” mean read-only existing identity or editable name? No new required data collection inferred. Existing optional name should stay optional absent a decision.
- Engineering must establish compatible existing auth configuration for web and mobile; any provider/SDK/configuration-policy change needs its own approved scope, not a design guess.
- Approve real test recipients/participation and intended staging/mobile distribution channel if not already authorized. No unsolicited SMS or paid-provider action from Design.
- If an exact cooldown/expiry countdown is required outside the widget, expose authoritative timing or approve omission; do not invent client business timing.

Written acceptance delivered; real-provider/device tests and deployed configuration NOT CHECKED. Figma visual QA BLOCKED. No functional test, staging, mobile-release or engineering approval is claimed by this document.

## Engineering-confirmed baseline clarification

Engineering independently confirms source baseline main `131e302`; no implementation change or deployed-provider test is implied.

- Direct OTP settings: TTL300 seconds; five sends per900-second rate window; six verification attempts per300-second attempt window. There is **no separate resend cooldown** in the direct contract and no expiry/cooldown metadata in its response. These source settings must not become an invented per-send countdown or claims about deployed overrides. MSG91 widget retry/timing remains provider-owned and absent from GaonOne's contract.
- Outside development, Redis failures fail closed. A service/storage failure must never fall back to development OTP, bypass verification or imply successful authentication. Current combined verification failure responses may not distinguish infrastructure failure from invalid/expired input; UX must not assert an unsupported reason.
- A newly verified phone implicitly creates an active, verified customer. Returning active users retain role and existing name; supplied name only fills an empty name. Disabled users receive403. There is no separate registration requirement or mandatory additional profile field.
- The two existing frontend flows are incompatible under the current single production AUTH_PROVIDER choice: `msg91_widget` rejects Flutter's direct routes with410; `local_otp` rejects web widget exchange with404. This is a concrete functional release blocker until Engineering resolves parity in an approved scope. Do not present one platform's passing auth test as both platforms ready.
- Existing direct real-SMS integration uses SMS_PROVIDER=msg91 and configured MSG91_AUTH_KEY/MSG91_TEMPLATE_ID. This establishes an existing code path, not credential availability, delivery success, provider selection approval or permission to send test SMS.
- No profile-update, phone-change or account-deletion endpoint is established. UI must not promise those actions. Phone-change/deletion are outside this acceptance slice unless explicitly scoped later.

AUTH-17 therefore requires a confirmed compatible web/mobile strategy before production parity acceptance. AUTH-03 must not imply a cooldown absent from the contract. AUTH-08/09 retain the existing implicit registration and optional-name rules. AUTH-11's mobile broad startup catch was observed by Design and flagged by Engineering for bounded validation before any fix; it is not reported as reproduced device behavior.

Written clarification only. Real provider, staging configuration, phone delivery and device acceptance remain NOT CHECKED; Figma visual QA remains BLOCKED.
