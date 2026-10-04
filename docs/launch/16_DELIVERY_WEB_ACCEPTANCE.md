# Web delivery handoff acceptance

Recorded 2026-10-04 UTC on `test/delivery-web-acceptance`, based on merged main `4e527879833f59129c4601eac7887b54dd5f6d86`.

## Scope and evidence boundary

This is browser-functional and inspected visual evidence for `/delivery/complete`, using synthetic rider/order data and mocked GaonOne API responses. It is not live Firebase, device, production, end-to-end backend, or deployment evidence. The backend's separate PR #203 CI applied migration 0026 and passed 311 tests, including proof contention/authorization cases. No real OTP, payment, location, or external provider call was made.

The unchanged screen passed COD/prepaid sequencing and code-service rejection cases, but the focused Chromium baseline failed duplicate-challenge prevention and both uncertain-completion recovery cases. Three additional layout cases failed the explicit code-label requirement. Screenshots also showed a cramped unlabelled input row on the narrow viewport. Initial-read counts were excluded from reconciliation assertions so development StrictMode's mount effects cannot create false recovery evidence.

## Narrow remediation

- One synchronous screen guard serializes every mutation and refresh; disabled controls are not the only duplicate-request protection.
- An uncertain completion response triggers one assigned-task read, not another completion. Failed reconciliation blocks further mutations until an explicit successful refresh.
- Acknowledged completion with a failed refresh also remains blocked. A definitive server rejection remains an error, not client completion.
- The exact server COD total is sent as a decimal string; no local proof/payment/delivery authority is introduced. All requests retain the shared GaonOne session boundary.
- Existing Button, FormField, Notice, Loading, and Empty primitives provide a labelled code field, larger controls, announced feedback, and distinct loading/error/empty states. No shared styling or unrelated page is changed.

## Executed evidence

`npx playwright test e2e/delivery-completion.spec.ts --workers=2 --output=/tmp/gaonone-delivery-web-final`: **60 passed** across Chromium, Firefox, WebKit, and mobile Chrome.

Cases include COD pickup → code → proof → exact cash collection → completion; paid UPI without cash collection; challenge/verification 429 and verifier 503; synchronous forced duplicate challenge; forced callbacks during held reconciliation; HTTP 503 and actual aborted completion responses; failed and acknowledged-completion refresh recovery; definitive server rejection; and initial loading/failure/empty distinctions. Response barriers replace timing sleeps.

At 320px, 390px, and 1280px each browser also passes the labelled-code assertion, 44px minimum handoff-control dimensions, no horizontal document overflow, and no serious/critical WCAG A/AA axe findings within `main`. This is not an assertion of complete accessibility compliance.

## Inspected screenshots

The following Chromium screenshots were visually inspected for clipping, text wrapping, spacing, control clarity, and displayed server price. Hindi/Marathi fixture text wraps without document overflow. These are development-server captures, so the small Next.js development indicator is tooling, not a production control. Screens show the picked-up COD state only; other states have functional tests but not yet this visual record.

- [320px narrow](evidence/delivery-web/delivery-completion-320px-chromium.png)
- [390px narrow](evidence/delivery-web/delivery-completion-390px-chromium.png)
- [1280px desktop](evidence/delivery-web/delivery-completion-1280px-chromium.png)

Capture command, from `web/`:

```sh
GAONONE_VISUAL_OUTPUT_DIR=../docs/launch/evidence/delivery-web npx playwright test e2e/delivery-completion.spec.ts --project=chromium --workers=2 --output=/tmp/gaonone-delivery-web-evidence
```

Source `web/app/delivery/complete/page.tsx` SHA-256: `1bb9fd36df888680676f2262c8d2c8323ae2b2621a76dd2f524f60948315eefe`.

| Capture | SHA-256 |
|---|---|
| 320px | `0c8889f5fa24433630881a0e0795234f1de03a5e2386dbfb8a0850cfa28e1162` |
| 390px | `1fd1fc0ed2a26bf9f579fd9773fe5010e9ace535b3c78c3065fd31f58d98d5f5` |
| 1280px | `6bc873bfbc53185aa91cb799ec26e32d927d3f7d5e71f864abb3ea2193efae93` |

## Remaining gates

Production webpack build passed, and the complete browser suite passed all 400 tests across the four configured browsers. Independent review found no unresolved P0/P1 implementation issue. Exact-final-head required CI remains mandatory before merge. This slice does not complete visual evidence for all actors/screens, low-end Android field acceptance, owner Firebase/signing setup, or release-candidate validation. No deployment is authorized.
