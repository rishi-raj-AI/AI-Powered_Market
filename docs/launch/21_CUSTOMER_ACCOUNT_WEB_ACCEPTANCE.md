# Customer account web acceptance

Recorded 2026-10-26 on `feat/launch-customer-account-web-acceptance`, created from merged main `22c2c135e0e62ac8703038eee643df6e5d3f33c7`.

## Scope and evidence boundary

This is browser-functional and inspected visual evidence for customer `/account`, `/account/addresses`, and `/account/devices`, using synthetic customer fixtures and mocked GaonOne API responses. It is not live Firebase, device, production, backend integration, payment-provider, or deployment evidence. No external provider, real customer data, credential, or deployment action was used.

The baseline checks exposed four presentation defects: `/account` did not distinguish an initial bootstrap failure from account content with an accessible retry; `/account/addresses` and `/account/devices` could render a confirmed-empty conclusion before their first required reads completed or after a failure; inherited actions measured 40px in Chromium/mobile Chrome and 42px in Firefox/WebKit; and Safari could let merchant-application input intrinsic width overflow a 320px document.

## Narrow remediation

- Render accessible initial loading and retryable failure before customer-account, address-book, or device conclusions are shown.
- Retain confirmed address/device data after a later failed refresh and label it as a last-confirmed snapshot.
- Scope 44px targets, responsive account links, and input containment to `.customerAccount`; do not change shared/global control behavior.
- Keep the established GaonOne session-expiry path, account/address/device API requests, merchant application flow, customer ownership, server-authoritative roles/permissions, configuration, and deployment behavior unchanged.

## Executed evidence

`npx playwright test e2e/customer-account-acceptance.spec.ts --workers=2 --output=/tmp/gaonone-customer-account-final`: **56 passed** across Chromium, Firefox, WebKit, and mobile Chrome.

At 320px, 390px, and 1280px, profile, address-book, and device views assert no serious/critical WCAG A/AA axe findings within `main`, every rendered `button`/`select`/button-like link is at least 44 by 44 CSS pixels (with a 0.01px Firefox layout-rounding tolerance), and no document-level horizontal overflow occurs. The suite also proves initial loading, failure, retry, confirmed state, and a confirmed address/device removal retained through a failed refresh without timing sleeps; synthetic responses release only after the visible loading state.

`npx playwright test e2e/account.spec.ts e2e/account-operations.spec.ts e2e/auth-direct.spec.ts e2e/location.spec.ts e2e/customer-account-acceptance.spec.ts --workers=2 --output=/tmp/gaonone-customer-account-regression-final`: **144 passed** across the same four browser projects. This retains the established account/session-expiry path, account operations, direct authentication flow, customer location behavior, and the new account acceptance behavior.

`npm run build -- --webpack`: production webpack build passed for all 29 routes.

Chromium evidence command, from `web/`:

```sh
GAONONE_VISUAL_OUTPUT_DIR=../docs/launch/evidence/customer-account npx playwright test e2e/customer-account-acceptance.spec.ts --project=chromium --workers=2 --output=/tmp/gaonone-customer-account-evidence
```

It passed all 14 Chromium cases. The inspected captures show readable profile/account information, touch-sized profile/address/device actions, narrow layout without document overflow, and clear address/device confirmed states. The small local Next development overlay in the captures is not product UI. This is not device or complete customer acceptance.

## Inspected screenshots

- [Profile — 320px](evidence/customer-account/customer-account-profile-320px-chromium.png)
- [Profile — 390px](evidence/customer-account/customer-account-profile-390px-chromium.png)
- [Profile — 1280px](evidence/customer-account/customer-account-profile-1280px-chromium.png)
- [Saved addresses — 320px](evidence/customer-account/customer-account-addresses-320px-chromium.png)
- [Saved addresses — 390px](evidence/customer-account/customer-account-addresses-390px-chromium.png)
- [Saved addresses — 1280px](evidence/customer-account/customer-account-addresses-1280px-chromium.png)
- [Notification devices — 320px](evidence/customer-account/customer-account-devices-320px-chromium.png)
- [Notification devices — 390px](evidence/customer-account/customer-account-devices-390px-chromium.png)
- [Notification devices — 1280px](evidence/customer-account/customer-account-devices-1280px-chromium.png)

| Capture | SHA-256 |
|---|---|
| Profile 320px | `4403a3f392e7f904e0697639bd31cc1c8a1efd9dbb1378f97db0183e1e4fefce` |
| Profile 390px | `64f2279d932ba078e869bc2decb4e07d6d65d6c62ccf46583bba362db88f3f8b` |
| Profile 1280px | `172766452da14bdb5ae910248833215b11109b08f690e43136d1a6dd442df705` |
| Saved addresses 320px | `dcc3f1b25e5a55da83189b21c216cf1ce6b24550df4c1301f34ca0f37950128a` |
| Saved addresses 390px | `b9c52225d1cb356283ab520fa732c792cbc36888529a1afee1d94abad4e04628` |
| Saved addresses 1280px | `626aabc56f78292ab3812bf0fd5ac623c3bd0e3105a7e09386954c25ad8445c1` |
| Notification devices 320px | `439c85707f9048f525edf94f6ebb5bd738590616138da5f6800e4a25edee7664` |
| Notification devices 390px | `ef4c904d2e26020b8fd8e1af8f3c8821535b0a30092ecbd0ec43552dc60b2ef4` |
| Notification devices 1280px | `5874d5bc46ca81eff2d9300bd03e73a0ed000936b200445c7c79d56489c8072c` |

| Source | SHA-256 |
|---|---|
| `web/app/account/page.tsx` | `3b1e60f6bffda8109d1ff3609cb6eddff40b5e8359296abc6f8dec5adf571a3c` |
| `web/app/account/addresses/page.tsx` | `42f9eb40dc3e0193f758868654f6be012126f6b26a466fe650f00c9e06961dff` |
| `web/app/account/devices/page.tsx` | `12538df595690ea920b264dfb2c442bf097cb75b0ab5d098860899459a4cb930` |
| `web/app/globals.css` | `cc78386ac897878cf2b66efcf03914a29abed231670363b2f83d1d7875bbc2bf` |
| `web/e2e/customer-account-acceptance.spec.ts` | `8696bc5824c71dadf2e0bda2be3b98b6be67aba7fc2a260351baf50ac29c31dd` |

## Remaining gates

Focused review, exact-final-head [PR #216](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/216) required checks (`backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images`), and PR review remain mandatory before merge. This does not complete Android/iOS device acceptance, Firebase owner setup, backend integration evidence, complete customer visual coverage, or release-candidate validation. No deployment is authorized.
