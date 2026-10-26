# Customer purchase web acceptance

Recorded 2026-10-26 on `feat/launch-customer-web-acceptance`, created from merged main `03939cea7e913691a408bf8a470eefd7f85b709a`.

## Scope and evidence boundary

This is browser-functional and inspected visual evidence for the customer `/cart` and `/checkout` surfaces, using synthetic customer fixtures and mocked GaonOne API responses. It is not live Firebase, device, production, backend integration, payment-provider, or deployment evidence. No external provider, real customer data, credential, or deployment action was used.

The baseline acceptance checks exposed three customer-path defects. The cart rendered its empty state before its first cart response was confirmed. Checkout rendered its missing-address conclusion while the required cart, address, village, and payment-configuration reads were still pending or had failed. The inherited cart quantity targets measured 34px, while cart/checkout action controls measured 40px in Chromium/mobile Chrome and 42px in Firefox/WebKit.

## Narrow remediation

- Scope the 44px control rule to `.customerPurchase` roots only: cart/checkout buttons, quantity controls, and selects.
- Render an explicit initial loading state and retryable initial-load failure before either surface can make an empty/no-address conclusion.
- Preserve an already confirmed cart/checkout snapshot after a later failed reload and label it as last-confirmed data.
- Retain the existing cart mutation, quote, checkout idempotency, payment confirmation, GaonOne session, server-authoritative price/serviceability/stock, payment configuration, and deployment behavior unchanged.

## Executed evidence

`npx playwright test e2e/customer-purchase-acceptance.spec.ts --workers=2 --output=/tmp/gaonone-customer-purchase-after-remediation`: **32 passed** across Chromium, Firefox, WebKit, and mobile Chrome.

At 320px, 390px, and 1280px, both views assert that serious/critical WCAG A/AA axe findings are absent within `main`, every rendered `button`/`select`/button-like link is at least 44 by 44 CSS pixels (with a 0.01px Firefox layout-rounding tolerance), and no document-level horizontal overflow occurs. The suite also proves initial loading, failure, retry, and confirmed empty cart/checkout quote states without timing sleeps; synthetic responses release only after the visible loading state.

`npx playwright test e2e/pricing.spec.ts e2e/payment-confirmation.spec.ts e2e/location.spec.ts e2e/customer-purchase-acceptance.spec.ts --workers=2 --output=/tmp/gaonone-customer-purchase-regression`: **112 passed** across the same four browser projects. This retains authoritative fee/quote behavior, stale quote handling, cart-mutation serialization, address-save serialization, checkout idempotency, UPI intent recovery, signed-payment-confirmation recovery, and customer address/location behavior.

`npm run build -- --webpack`: production webpack build passed for all 29 routes.

Chromium evidence command, from `web/`:

```sh
GAONONE_VISUAL_OUTPUT_DIR=../docs/launch/evidence/customer-purchase npx playwright test e2e/customer-purchase-acceptance.spec.ts --project=chromium --workers=2 --output=/tmp/gaonone-customer-purchase-evidence
```

It passed all 8 Chromium cases. The inspected captures show touch-sized cart quantity and checkout controls, narrow stacked panels without document overflow, readable authoritative subtotal/fee/total information, and a clear COD/payment-disabled state. The small local Next development overlay in the captures is not product UI. This is not device or complete customer acceptance.

## Inspected screenshots

- [Cart — 320px](evidence/customer-purchase/customer-cart-320px-chromium.png)
- [Cart — 390px](evidence/customer-purchase/customer-cart-390px-chromium.png)
- [Cart — 1280px](evidence/customer-purchase/customer-cart-1280px-chromium.png)
- [Checkout — 320px](evidence/customer-purchase/customer-checkout-320px-chromium.png)
- [Checkout — 390px](evidence/customer-purchase/customer-checkout-390px-chromium.png)
- [Checkout — 1280px](evidence/customer-purchase/customer-checkout-1280px-chromium.png)

| Capture | SHA-256 |
|---|---|
| Cart 320px | `f8e22c7d3c4fe12b41c1d5d215a6573aa8a6145b0cf1cab14f148b075a48db42` |
| Cart 390px | `97b28bd553af049ea87cb159cf11cab4397c32c7a838768e42491b87488250e9` |
| Cart 1280px | `88d323403d6a6e560ff99b61cb41673bbbab4a2237319dcbd731b3327de41fee` |
| Checkout 320px | `f040f8f40b6e0132faae784dd1e86d773d2401809e5c8b2e58e0076c66e4d950` |
| Checkout 390px | `2ce06d8440392abd968ffddb2a8c4b5fc8b5ad6ee97b46c8b81cf5cfccc34d76` |
| Checkout 1280px | `623cf20720bd73dfc7739c82e78c37e939ec0a4d5c441007aa6d3e53fab79d09` |

| Source | SHA-256 |
|---|---|
| `web/app/cart/page.tsx` | `5508d9bc55d9c9b04c9a9b5719e586d957cb59aebd02e050634d62f3520b8d14` |
| `web/app/checkout/page.tsx` | `3de2fe7d7f87ecc672280fa9124474b38fa91d7cdfd989ad4f25b8243c1bd36a` |
| `web/app/globals.css` | `f621d7302ea6b8aec150db7e692609214885c87c63b7b0f871de50933be0dd96` |
| `web/e2e/customer-purchase-acceptance.spec.ts` | `d69e4eb0b9f7b5e1eabc3f234629309cf91242f10cdd07a13d4f92e98f513fe1` |

## Remaining gates

Focused review, exact-final-head [PR #215](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/215) required checks (`backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images`), and PR review remain mandatory before merge. This does not complete Android/iOS device acceptance, Firebase owner setup, backend integration evidence, complete customer visual coverage, or release-candidate validation. No deployment is authorized.
