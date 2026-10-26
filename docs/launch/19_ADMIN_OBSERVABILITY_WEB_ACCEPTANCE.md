# Admin observability web acceptance

Recorded 2026-10-25 UTC on `feat/launch-admin-operations-web-acceptance`, created from merged main `37b1028176953ea005074310fd07ffe4d2946126`.

## Scope and evidence boundary

This is browser-functional and inspected visual evidence for the authorized-admin `/admin/operations` and `/admin/delivery-performance` read-only views, using synthetic normal-admin fixtures and mocked GaonOne API responses. It is not live Firebase, device, production, backend integration, payment/settlement, or deployment evidence. No external provider, real operational data, credential, or deployment action was used.

The baseline acceptance checks exposed two truthful-state defects. `/admin/operations` rendered its inherited 40px Chromium/mobile-Chrome and 42px Firefox/WebKit Refresh target below the 44px target. Both views could show zero/empty conclusions before their initial data loaded or after a failed load, and delivery performance offered no retry or explicit no-data state. Existing backend capability checks and read-only endpoint contracts were sound and are intentionally outside this UI-only remedy.

## Narrow remediation

- Apply the existing `adminOperations` 44px control scope to the remaining admin observability roots.
- Render initial loading, visible failure and retry states; preserve an already confirmed snapshot on a later refresh failure and label it as the last confirmed data.
- Render operational empty/no-data conclusions only after a confirmed response.
- Retain the existing read-only API calls, server capability checks, operational data authority, sessions, roles, configuration, and deployment workflow unchanged.

## Executed evidence

`npx playwright test e2e/admin-observability-acceptance.spec.ts --workers=2 --output=/tmp/gaonone-admin-observability-final-scope`: **32 passed** across Chromium, Firefox, WebKit, and mobile Chrome.

At 320px, 390px, and 1280px, both views assert that serious/critical WCAG A/AA axe findings are absent within `main`, every rendered `button`/`select` is at least 44 by 44px, and no document-level horizontal overflow occurs. The suite also proves initial loading, failure, retry, and confirmed empty/no-data states without timing sleeps; synthetic responses release only after the visible loading state.

`npx playwright test e2e/admin.spec.ts e2e/admin-operations-acceptance.spec.ts e2e/admin-observability-acceptance.spec.ts --workers=2 --output=/tmp/gaonone-admin-observability-regression`: **84 passed** across the same four browser projects. This retains capability fail-closed, role-mutation, assignment/recovery, financial-return review, queue error/retry, and previously audited dashboard/recovery behavior.

`npm run build -- --webpack`: production webpack build passed.

Chromium evidence command, from `web/`:

```sh
GAONONE_VISUAL_OUTPUT_DIR=../docs/launch/evidence/admin-observability npx playwright test e2e/admin-observability-acceptance.spec.ts --project=chromium --workers=2 --output=/tmp/gaonone-admin-observability-evidence
```

It passed all 8 Chromium cases. The inspected captures show touch-sized Refresh controls, narrow stacked metrics/exception cards, readable long state labels, wrapped timing rows without document overflow, and no invented delivery prediction. The small local Next development overlay in the captures is not product UI. This is not device or complete admin acceptance.

## Inspected screenshots

- [Admin operations — 320px](evidence/admin-observability/admin-operations-320px-chromium.png)
- [Admin operations — 390px](evidence/admin-observability/admin-operations-390px-chromium.png)
- [Admin operations — 1280px](evidence/admin-observability/admin-operations-1280px-chromium.png)
- [Delivery performance — 320px](evidence/admin-observability/admin-delivery-performance-320px-chromium.png)
- [Delivery performance — 390px](evidence/admin-observability/admin-delivery-performance-390px-chromium.png)
- [Delivery performance — 1280px](evidence/admin-observability/admin-delivery-performance-1280px-chromium.png)

| Capture | SHA-256 |
|---|---|
| Admin operations 320px | `1133df9021c0632f96a60b3881c3ba06a9e03b031f57630f8a090b6cfbc5e394` |
| Admin operations 390px | `efbe19760d4bb7e5f7de52bb78fa2bfae745f870ed141429ba1eadfcac839b23` |
| Admin operations 1280px | `6b9e2d464dc5f292ed6a925ab63e53a8af17ceae148429a1e0cfba0e8aa239f2` |
| Delivery performance 320px | `c3f155c59e4fae5d20bfb63f9b49a1cf790ee4fd769b1ad288786ef1bf6dce3b` |
| Delivery performance 390px | `3e5e8a4e0ba3e3e98da85daf48a50c0600dcb1c20ead5891d6ed08b80d587ca4` |
| Delivery performance 1280px | `705ef458957d9747599b10923be4c302fbea2850e79ebd929e2cd9107bc4e12e` |

| Source | SHA-256 |
|---|---|
| `web/app/admin/operations/page.tsx` | `156786b390fb91169c318d4a5a76c34c25dc2edc378069f81573502def1d4b72` |
| `web/app/admin/delivery-performance/page.tsx` | `90bcfadf316915d56816bfcce7d3ad3e6f2fca51c5898502d6dba0b97a1f67d7` |
| `web/e2e/admin-observability-acceptance.spec.ts` | `48c62906b9986dfa19bcf9b07d456ebc021d3d69b52106856dd46eeb36da49aa` |

## Remaining gates

Focused review, exact-final-head `backend-check`, `build-and-ui`, `analyze-and-build-android`, `production-compose-and-images`, and PR review remain mandatory before merge. This does not complete Android/iOS device acceptance, Firebase owner setup, backend integration evidence, complete admin/support visual coverage, or release-candidate validation. No deployment is authorized.
