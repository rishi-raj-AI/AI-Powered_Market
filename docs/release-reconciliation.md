# Release Reconciliation

This branch reconciles valid product capabilities from historical feature lineages onto the hardened delivery-first architecture based on `3daee3fb8485ef3e2ef5b743d5e202c71c8bd834`. Historical branches are evidence, not merge candidates: cumulative obsolete payment, migration, and state-management code is not imported.

## Capability decisions

| Historical family | Decision | Current result |
| --- | --- | --- |
| X01 universal location discovery | Selectively recovered | Area/locality search, current GPS, coordinates, serviceability context, and a reusable location selector are available on the marketplace. Provider-backed place search retains current authenticated provider controls. |
| X02 location-aware commerce search | Selectively recovered | Public PostGIS-backed store, product, and category discovery ranks available inventory deterministically by text relevance and distance. Delivery-only filtering remains backend-authoritative. |
| X03 location memory/serviceability | Selectively recovered | Up to five recent locations are stored locally without credentials or customer PII; selected coverage context is carried into nearby discovery. |
| X04 nearby search suggestions | Selectively recovered | A typed suggestions API returns only approved, active, in-stock nearby commerce results with deterministic prefix/distance ranking. |
| X05 fulfillment promise | Historical implementation obsolete | The old route generated an unmeasured ETA from straight-line distance and UTC store hours. Current India-local hours and tracking analytics remain authoritative; no fake promise is exposed. |
| X06 scheduled fulfillment windows | Partially valid intent, not recovered yet | The old route generated generic UTC slots that were not persisted on checkout or orders. A real selectable window requires an auditable order contract rather than display-only slots. |
| X07 substitutions / X29 vertical | Selectively recovered | Backend returns ranked, active, in-stock alternatives from the same approved store. Web and Flutter require the customer to choose; nothing substitutes automatically. |
| X08 reorder preview / X31 vertical | Selectively recovered | An ownership-protected preview uses current stock and prices, clamps quantities, and exposes explicit add-to-cart controls on web and Flutter. It never recreates an order silently. |
| X09 personalized feed / X28 vertical | Historical scoring obsolete | The old feed called unpersonalized inventory “popular” without popularity evidence. Current location-aware search and explicit reorder preserve the defensible intent; invented popularity is not exposed. |
| X10 basket recommendations / X27 vertical | Historical scoring obsolete | Same-category inventory was described as “complementary” without basket-affinity evidence. Same-store substitutions remain explicit and stock-authoritative; no unsupported recommendation claim is restored. |
| X11 store availability / X32 vertical | Recovered through current architecture | Backend-computed `is_open_now` uses Asia/Kolkata rules. Web discovery/storefront and Flutter marketplace now expose Open now / Closed now rather than recomputing hours client-side. |
| X12 checkout quote / X14 cart health / X19-X21 checkout intelligence | Superseded | The hardened address-specific `/cart/quote` is the single preflight contract. Historical variants duplicated stock/serviceability checks and one invented a fixed ₹20 fee. |
| X13 order recovery | Superseded in part; unsupported action rejected | Current cancellation, payment state, tracking, explicit reorder and post-pickup recovery routes cover executable actions. The historical generic “contact support” action had no support workflow behind it and is not presented as functional. |
| X15 / X22 preparation estimate | Historical implementation obsolete | It measured `updated_at - created_at` after unrelated terminal transitions and invented a 30-minute fallback. No preparation promise is shown until an auditable ready timestamp and sufficient samples exist. |
| X16 / X23 fulfillment recommendation | Historical implementation obsolete | The later version fixed India-local hours but still recommended scheduled modes that checkout cannot persist. Current UI exposes only backend-supported delivery/pickup state. |
| X17 / X24 repeat cadence | Intent covered without predictive claim | Historical code labeled products “due” from as few as two purchases. Current explicit reorder previews delivered baskets against live price and stock without claiming purchase urgency. |
| X18 / X25 merchant reliability | Historical percentage obsolete | The percentage mixed cancellations and failures with arbitrary weights/confidence bands. Verified merchant status, live availability and operational admin data remain factual; no unsupported consumer trust score is exposed. |
| X26 authoritative checkout pricing | Recovered early as a release invariant | Cart no longer displays an invented client fee. Checkout obtains an authenticated address-specific backend quote and the mutation revalidates under inventory locks. |
| Live delivery tracking | Completed and hardened | Assigned-rider GPS writes are ownership-, state-, rate-, accuracy-, timestamp-, and plausibility-guarded. Customer web and mobile surfaces show fresh rider position, accuracy, route and maps; rider mobile exposes assigned-only navigation. Provider route estimates now require pickup plus a rider fix no older than 30 seconds, so store-to-customer or stale-coordinate durations are never presented as live ETA. Exact rider PII stops after delivery, and open offers remain coarse/PII-free. |
| Old cumulative X01-X04 branch stacks | Obsolete as integration units | Their valid capability intent is recovered above; obsolete migrations and pre-hardening commerce/payment code are not merged. |

## Validation evidence

- Backend discovery lint: pass.
- Backend discovery integration tests: 6 passed.
- Web production build: pass on repository lockfile.
- Location/discovery Playwright coverage: 16 passed across Chromium, Firefox, WebKit, and mobile Chrome.
- Checkout quote backend tests: 3 passed, including area fee, stock change, and address ownership.
- Pricing Playwright coverage: 4 passed across Chromium, Firefox, WebKit, and mobile Chrome.
- Alternatives/reorder backend tests: 4 passed.
- Alternatives/reorder Playwright coverage: 8 passed across Chromium, Firefox, WebKit, and mobile Chrome.
- Flutter analysis: no issues in `lib`; Flutter smoke test: 1 passed.
- Live-tracking backend lint: pass; focused tracking/maps/route tests: 19 passed.
- Live-tracking Playwright coverage: 20 passed across Chromium, Firefox, WebKit, and mobile Chrome.
- Flutter tracking/navigation analysis completed with no errors; Flutter tests: 2 passed, including PII-free open-offer parsing.
- Store-hours/quote backend regression tests: 26 passed; India-local availability remains backend authoritative.
- Availability/area-first Playwright coverage: 20 passed across Chromium, Firefox, WebKit, and mobile Chrome.
- Flutter availability/area-first analysis: no issues; Flutter tests: 3 passed.
- No schema change or migration was required for this family.

## Remaining reconciliation

- Audit and reconcile all remaining historical feature lineages.
- Audit X09-X25 intelligence lineages and recover only explainable, evidence-backed product behavior.
- Remove remaining client-authority leaks or product-surface gaps found by the audit (the hardcoded web delivery fee is resolved).
- Run full backend, web, Playwright, mobile, migration, and production-preflight validation.
- Freeze one exact candidate SHA, open one real integration PR, require exact-SHA 4/4 CI, merge, and require exact merged-main 4/4 CI.

No staging or production deployment is performed by this reconciliation branch.
