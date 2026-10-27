# Customer market web acceptance

Recorded 2026-10-26 on `feat/launch-customer-market-web-acceptance`, created from merged main `5e6a5a6aa5e3f5f90b799ae15ba8941627f95239`; final PR outcome recorded 2026-10-27.

## Scope and evidence boundary

This is browser-functional and inspected visual evidence for customer `/market` and `/market/[id]`, using synthetic customer fixtures and mocked GaonOne API responses. It is not live Firebase, device, production, backend integration, payment-provider, or deployment evidence. No external provider, real customer data, credential, or deployment action was used.

The baseline/source review exposed five customer-facing defects: marketplace and storefront could imply an empty/no-match conclusion before their current reads were confirmed; an identical nearby query could reuse a stale completed context while its new request was pending; nearby Refresh/Clear actions overflowed at 320px; and direct Add plus alternative Choose actions did not share CART-001's synchronous cart-mutation guard. A delayed initial cart-badge read could also replace the cart returned by a storefront mutation.

## Narrow remediation

- Gate marketplace, nearby discovery, and storefront conclusions on the current request context; show loading/retry rather than unconfirmed empty/no-match states.
- Keep the last confirmed marketplace/storefront snapshot visible after a later refresh failure, with an explicit label; a retry or new discovery intent becomes unconfirmed until it returns.
- Scope 44px targets and the narrow nearby-action wrap to `.customerMarket`, without changing global control layout.
- Route direct Add and alternative Choose through one synchronous storefront cart-write guard, snapshot quantity before awaiting, invalidate an older badge read, and render only the returned authoritative cart.
- Keep the established shared GaonOne API/session-expiry handler, customer ownership, server-authoritative availability/pricing/stock/cart/authorization, configuration, and deployment behavior unchanged.

## Executed evidence

`npx tsc --noEmit --incremental false`: passed.

`npx playwright test e2e/customer-market-acceptance.spec.ts --workers=2 --reporter=dot --output=/tmp/gaonone-customer-market-remediation-focused`: **72 passed** across Chromium, Firefox, WebKit, and mobile Chrome.

The suite asserts serious/critical WCAG A/AA axe findings are absent within `main`, all rendered market buttons/selects/button-like links are at least 44 by 44 CSS pixels (with the existing 0.01px rounding tolerance), and document-level overflow is absent at 320px, 390px, and 1280px. It proves initial loading/failure/retry/confirmed empty distinctions, last-confirmed marketplace/storefront refresh behavior, reissued-same-query invalidation, synchronous forced duplicate/cart-badge race protection, and direct/alternative cart-write serialization without sleeps or timeout inflation.

`npx playwright test e2e/location.spec.ts e2e/reorder-substitutions.spec.ts e2e/customer-market-acceptance.spec.ts --workers=2 --reporter=dot --output=/tmp/gaonone-customer-market-final-regression-rerun`: **124 passed** across the same four browser projects. This retains the established location, explicit same-store alternative, session-expiry, and customer-market behavior.

`npm run build -- --webpack`: production webpack build passed for all 29 routes.

Chromium evidence command, from `web/`:

```sh
GAONONE_VISUAL_OUTPUT_DIR=../docs/launch/evidence/customer-market npx playwright test e2e/customer-market-acceptance.spec.ts --project=chromium --workers=2 --reporter=dot --output=/tmp/gaonone-customer-market-final-evidence
```

It passed all 18 Chromium cases. The inspected captures show readable marketplace, nearby-location, and storefront states at 320px/390px/1280px, touch-sized controls, no document overflow, and the nearby actions wrapping at narrow widths. The small local Next development overlay in the captures is not product UI. This is not device or complete customer acceptance.

## Inspected screenshots

- [Marketplace — 320px](evidence/customer-market/customer-market-marketplace-320px-chromium.png)
- [Marketplace — 390px](evidence/customer-market/customer-market-marketplace-390px-chromium.png)
- [Marketplace — 1280px](evidence/customer-market/customer-market-marketplace-1280px-chromium.png)
- [Nearby marketplace — 320px](evidence/customer-market/customer-market-nearby-320px-chromium.png)
- [Nearby marketplace — 390px](evidence/customer-market/customer-market-nearby-390px-chromium.png)
- [Nearby marketplace — 1280px](evidence/customer-market/customer-market-nearby-1280px-chromium.png)
- [Storefront — 320px](evidence/customer-market/customer-market-storefront-320px-chromium.png)
- [Storefront — 390px](evidence/customer-market/customer-market-storefront-390px-chromium.png)
- [Storefront — 1280px](evidence/customer-market/customer-market-storefront-1280px-chromium.png)

| Capture | SHA-256 |
|---|---|
| Marketplace 320px | `fc77afab0a786011dbd91c7b5706653b5ae94f94c8050fbf909f06e4221f0f77` |
| Marketplace 390px | `78f42b338788e277eab1daad1789e84a75cdc4bd3468fc1ab23ed7b10989e681` |
| Marketplace 1280px | `22a13066926ebd41260c8960250899b003dc6481b22b85540032533efbbd5811` |
| Nearby marketplace 320px | `f024ceffd8f1643ae211d5c14f6f4a781f5c8aefe9fc612b82157835d8c24d03` |
| Nearby marketplace 390px | `35997255d5c691b94d6adb862356c33fee95092196aeaf15853137e51b474f04` |
| Nearby marketplace 1280px | `49503b716a7dff3c6ec09447cd865589e9e4eecd06d2a0eaa41cc38e493d1e09` |
| Storefront 320px | `352f1c604f06f2980517919e5c4147c4f82c289611bfad43ffbe51c46f7794af` |
| Storefront 390px | `b345d61938ab31fc8a8caf14487f249eab8f21c1dc5e8d6624b3d637197c4fde` |
| Storefront 1280px | `ed86503e6f019abd96139533593ac29271ee5170212c5d38c11308f04015b3fb` |

| Source | SHA-256 |
|---|---|
| `web/app/market/page.tsx` | `f089715390ba5699ce06b8b59661a375f25b2182b14b7ca5c14d33512ba51cd4` |
| `web/app/market/[id]/page.tsx` | `53693829a0d0ab58e3278ff1790cef6e2d28b64144b4bdc63869925a112d960d` |
| `web/components/SubstitutionChoices.tsx` | `510bd5714f81a06b88c182e3b7347c1dcef465aa364231da459b5a73ed3b27a6` |
| `web/app/globals.css` | `e82d680f08e882093dd8fd5d76344592fc6ab0561d61e081aaaa5878b356e580` |
| `web/e2e/customer-market-acceptance.spec.ts` | `12625cc3e1bfb772cdadf0c9fbe4bda744f9b60006104fbb2c93a63eb0f406bc` |
| `web/e2e/location.spec.ts` | `1778db0104ab5bca0db7f33cd020baaf06003e476b759e007d42cb5f6b6a6720` |

## Remaining gates

[PR #217](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/217) merged normally as `50d730f53678d5c320f5c45db978f088b0945f17` after all four required checks passed on final head `3ae518cdb7810e213b1680a3b26ddc3e2a5c7296`. Its pre-remediation head `bc76e2e531700598a24047e93f7d6d2aa3e7ee8b` passed backend, Android, and compose/image validation; Web CI failed two WebKit tests after 699 passes because it interacted with a controlled nearby-search field before hydration. The test-only repair waits for the client-rendered nearby store before typing and the final head passed `backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images`. The initial Android job on that final head could not install a corrupt hosted-runner NDK archive; its retry passed on the same head, so it is an infrastructure-only event rather than an application regression. No deployment ran.

This does not complete Android/iOS device acceptance, Firebase owner setup, backend integration evidence, complete customer visual coverage, or release-candidate validation. No deployment is authorized.
