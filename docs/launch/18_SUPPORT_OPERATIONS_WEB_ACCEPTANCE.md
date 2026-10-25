# Support operations web acceptance

Recorded 2026-10-25 UTC on `feat/launch-support-web-acceptance`, created from merged main `c25b9a15157d983788961ad247280b4acb75ab71`.

## Scope and evidence boundary

This is browser-functional and inspected visual evidence for customer `/support` and authorized-staff `/admin/support`, using synthetic customer and elevated-support fixtures plus mocked GaonOne API responses. It is not live Firebase, device, production, end-to-end backend, payment/settlement, or deployment evidence. No external provider, real customer data, credential, or deployment action was used.

The baseline acceptance run demonstrated a real low-end interaction defect: customer/staff support action controls were 40px in Chromium/mobile Chrome and 42px in Firefox/WebKit, below the 44px target. The authorized staff native assignee selector rendered at only 23px in WebKit. Existing support ownership, capability denial, public/internal visibility, idempotency, transition, and recovery tests already passed; those boundaries are intentionally outside this UI-only remedy.

## Narrow remediation

- Add the support-only marker to customer and authorized-staff support roots.
- Scope 44px minimum dimensions to support buttons and selects, with an explicit 44px selector height to cover WebKit native rendering.
- Retain server-authoritative support ownership/capabilities, ticket versioning/transitions, public/internal message separation, idempotency, and all API contracts unchanged.

## Executed evidence

`npx playwright test e2e/support-operations-acceptance.spec.ts --workers=2 --output=/tmp/gaonone-support-operations-final-scope`: **32 passed** across Chromium, Firefox, WebKit, and mobile Chrome.

At 320px, 390px, and 1280px, customer and authorized-staff cases assert serious/critical WCAG A/AA axe findings are absent within `main`, every rendered `button`/`select` is at least 44 by 44px, and no document-level horizontal overflow occurs. The suite also proves customer and staff queues show failure, retry, then empty states without timing sleeps; fixture success is released only after the visible failure state.

`npx playwright test e2e/support.spec.ts e2e/support-operations-acceptance.spec.ts --workers=2 --output=/tmp/gaonone-support-regression-final-scope`: **104 passed** across the same four browser projects. This retains coverage for customer ticket/reply replay and serialization, capability discovery failure, no-privilege fail-closed rendering, public/internal separation, assignment/status contracts, conflicts, delayed-response isolation, and support-access revocation. The host reported development-server log-flush disk-space warnings during the run, but Playwright recorded a passed final status with no failed tests; final PR CI remains the independent authority.

`npm run build -- --webpack`: production webpack build passed.

Chromium evidence command, from `web/`:

```sh
GAONONE_VISUAL_OUTPUT_DIR=../docs/launch/evidence/support-operations npx playwright test e2e/support-operations-acceptance.spec.ts --project=chromium --workers=2 --output=/tmp/gaonone-support-operations-evidence
```

It passed all 8 Chromium cases. The inspected captures show 44px actions/selects, Hindi fixture text, wrapped status controls without document overflow, and separated customer/public/internal staff content. This is not device or complete support acceptance.

## Inspected screenshots

- [Customer support — 320px](evidence/support-operations/customer-support-320px-chromium.png)
- [Customer support — 390px](evidence/support-operations/customer-support-390px-chromium.png)
- [Customer support — 1280px](evidence/support-operations/customer-support-1280px-chromium.png)
- [Authorized staff support — 320px](evidence/support-operations/admin-support-320px-chromium.png)
- [Authorized staff support — 390px](evidence/support-operations/admin-support-390px-chromium.png)
- [Authorized staff support — 1280px](evidence/support-operations/admin-support-1280px-chromium.png)

| Capture | SHA-256 |
|---|---|
| Customer support 320px | `e53a28df4ee5a0dc47076ae00c0ad9373e8bbe204fd96f96ef4c89d13a9b5c8d` |
| Customer support 390px | `8a8ee6724697a57cd9798deef7032968ef22dfb0714767efb2eb389ab7e591b1` |
| Customer support 1280px | `abb4c97a6d5b230dc118eab8a373ed0a68a9ff9e5bc281d282318e4dee1ae344` |
| Authorized staff support 320px | `af848303179e3f189b01250ebe1b66b82ce0312c7384d9c4f65b47969a8a11d5` |
| Authorized staff support 390px | `79fd021e87ece89886cbccc4a8f2b66de5017a5706f776390fc3507605e36cc5` |
| Authorized staff support 1280px | `1f7a14767b9f0b155c34fda9d8bba200d4a4379184964766053b174e6a14d1f0` |

| Source | SHA-256 |
|---|---|
| `web/app/support/page.tsx` | `d2829a756cba651ed54b7046e68985a836d1ec097acee9a2847ed149779d063f` |
| `web/app/admin/support/page.tsx` | `76b55a6870f287a6ee2af262009e9eb3c51d01d5b59e7d00d87dbbf6da478c4b` |
| `web/app/globals.css` | `b1b91e8e380ab94338f7231a43c28f2bf43cb2df6d622ca022271a644d703a2f` |
| `web/e2e/support-operations-acceptance.spec.ts` | `11d40045c7fa864080459f5ea1af80554283bb6fcec0b2bcc833cd459ae02a28` |

## Remaining gates

Focused review, exact-final-head `backend-check`, `build-and-ui`, `analyze-and-build-android`, `production-compose-and-images`, and PR review remain mandatory before merge. This does not complete Android/iOS device acceptance, Firebase owner setup, backend integration evidence, complete support/admin visual coverage, or release-candidate validation. No deployment is authorized.
