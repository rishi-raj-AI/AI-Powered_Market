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
| X13 / X36 / X42 order support | Selectively recovered | Current cancellation, payment state, tracking, explicit reorder and post-pickup recovery remain direct actions. Durable ownership-checked support tickets now provide the previously missing escalation path, with deterministic triage and an admin-controlled resolution queue on web plus mobile order entry. |
| X15 / X22 preparation estimate | Historical implementation obsolete | It measured `updated_at - created_at` after unrelated terminal transitions and invented a 30-minute fallback. No preparation promise is shown until an auditable ready timestamp and sufficient samples exist. |
| X16 / X23 fulfillment recommendation | Historical implementation obsolete | The later version fixed India-local hours but still recommended scheduled modes that checkout cannot persist. Current UI exposes only backend-supported delivery/pickup state. |
| X17 / X24 repeat cadence | Intent covered without predictive claim | Historical code labeled products “due” from as few as two purchases. Current explicit reorder previews delivered baskets against live price and stock without claiming purchase urgency. |
| X18 / X25 merchant reliability | Historical percentage obsolete | The percentage mixed cancellations and failures with arbitrary weights/confidence bands. Verified merchant status, live availability and operational admin data remain factual; no unsupported consumer trust score is exposed. |
| X41 admin delivery performance | Selectively recovered | Admin-only 30-day counts and assignment-to-pickup / pickup-to-delivery medians use recorded delivery timestamps. The surface labels its sample basis and exposes no invented confidence or on-time claim. |
| X38 merchant settlement ledger / X58 admin oversight | Selectively recovered / current authority retained | Merchants now have read-only visibility into their backend-scoped settlement entries, including void state. Admin settlement authority remains backend-only; no browser control can manufacture or settle an entry. |
| X39 actionable customer updates | Selectively recovered | Stored notification events link to the referenced customer order when the backend supplies an order ID. The client does not infer references or claim push delivery. |
| X40 proof readiness | Superseded by hardened rider flow | The current rider completion surface already requires the backend proof challenge/verification and separate COD collection before guarded completion. |
| X43-X44 multilingual/catalog assist | Valid bounded intent, not release-critical | The historical deterministic parsers never mutate carts, orders, catalog, or stock. Their raw diagnostic JSON pages are not recovered as finished product UX; existing authority boundaries remain intact. |
| X45 merchant reliability operations | Historical score obsolete | It re-exposed the arbitrary weighted percentage and confidence labels rejected with X18/X25. Factual terminal counts remain available to operations without a fabricated trust score. |
| X46 order history / X67 order audit | Superseded | The current customer Order journey reads the ownership-checked backend transition ledger and shows payment/order state without inferring missing transitions. |
| X47 delivery proof audit / X68 customer proof receipt | Valid intent, pending surface reconciliation | The ownership-checked proof API is authoritative. Dedicated read-only rider/customer receipt surfaces remain to be reconciled without exposing OTP hashes or unrelated delivery data. |
| X48-X49 and X52-X57 operations controls | Superseded by current role workspaces | Current admin and merchant consoles already enforce backend authorization for account roles, merchant governance, inventory, storefront status, order transitions, dispatch and assignment recovery. The historical pages duplicated those controls. |
| X50 / X62 notification readiness and device control | Selectively recovered | Customers can see actual FCM configuration state, list only their active registrations, and unregister their own device. Stored events remain explicitly distinct from provider push delivery. |
| X51 rider presence | Current mobile capability retained | The rider mobile workspace already obtains device GPS and updates backend-authoritative presence. A duplicate web-only presence page is not required for the pilot rider application. |
| X61 customer address book | Selectively recovered | Customers can review and remove their owner-scoped saved addresses, and add a serviceability-validated exact location through checkout. |
| X63 store preparation transparency | Historical estimate obsolete | The source depended on the fabricated preparation estimate rejected with X15/X22. No preparation time or confidence is shown without auditable readiness timestamps and sufficient measured samples. |
| X64 merchant media readiness | Selectively recovered | Merchants can explicitly upload a supported catalog image through the authenticated backend media contract. The browser neither bypasses file validation nor publishes a product automatically. |
| X65 rider incident / X66 admin recovery | Recovered and hardened | Riders can report only their active assigned delivery through the guarded failure endpoint. Admins receive a protected factual failed-delivery queue; backend custody rules choose between pre-pickup reassignment and post-pickup return/refund/settlement handling. |
| X67 customer order audit | Superseded by Order journey | The current ownership-checked lifecycle surface reads the same server transition ledger and does not infer transitions. |
| X68 customer proof receipt | Selectively recovered | Customers can select their own order and view only backend-verified proof metadata through the existing ownership boundary. OTP hashes and unrelated delivery data are never exposed. |
| X69 customer payment state | Superseded by current orders | Current order cards and lifecycle already display backend payment state, provider retry eligibility and cancellation/refund state. A second read-only list would add no capability. |
| X70 role workspace navigation | Recovered through current navigation | Navigation exposes only the authenticated role's customer, merchant, rider or admin workspaces, including the newly reconciled operational surfaces. Backend authorization remains authoritative for every destination. |
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
- Support migration: single Alembic head `0018_support_tickets`; upgrade pass.
- Support backend lint: pass; workflow plus authorization regression tests: 20 passed.
- Support web production build: pass; Playwright: 8 passed across four browser profiles.
- Flutter support surface analysis: no issues; full Flutter tests: 3 passed.
- Admin delivery-performance backend tests: 4 passed with dispatch regression coverage; web production build passed; Playwright: 4 passed across four browser profiles.
- Merchant settlement, address/device ownership surfaces and actionable updates: web production build passed; Playwright: 12 passed across four browser profiles.
- Failed-delivery queue backend lint passed; recovery/dispatch regression tests: 13 passed.
- Rider incident, admin recovery, customer proof and merchant media: web production build passed; Playwright: 16 passed across four browser profiles.
- No schema change or migration was required for this family.

## Remaining reconciliation

- Audit and reconcile all remaining historical feature lineages.
- Remove remaining client-authority leaks or product-surface gaps found by the audit (the hardcoded web delivery fee is resolved).
- Run full backend, web, Playwright, mobile, migration, and production-preflight validation.
- Freeze one exact candidate SHA, open one real integration PR, require exact-SHA 4/4 CI, merge, and require exact merged-main 4/4 CI.

No staging or production deployment is performed by this reconciliation branch.
