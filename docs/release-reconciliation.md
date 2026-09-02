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
| X07 substitutions | Valid intent, pending current vertical | Only explicit customer-selected same-store alternatives are acceptable; silent substitution remains prohibited. |
| X08 reorder preview | Valid intent, pending current vertical | Preview must use current stock and prices and must never recreate an order without customer review. |
| X26 authoritative checkout pricing | Recovered early as a release invariant | Cart no longer displays an invented client fee. Checkout obtains an authenticated address-specific backend quote and the mutation revalidates under inventory locks. |
| Old cumulative X01-X04 branch stacks | Obsolete as integration units | Their valid capability intent is recovered above; obsolete migrations and pre-hardening commerce/payment code are not merged. |

## Validation evidence

- Backend discovery lint: pass.
- Backend discovery integration tests: 6 passed.
- Web production build: pass on repository lockfile.
- Location/discovery Playwright coverage: 16 passed across Chromium, Firefox, WebKit, and mobile Chrome.
- Checkout quote backend tests: 3 passed, including area fee, stock change, and address ownership.
- Pricing Playwright coverage: 4 passed across Chromium, Firefox, WebKit, and mobile Chrome.
- No schema change or migration was required for this family.

## Remaining reconciliation

- Audit and reconcile all remaining historical feature lineages.
- Complete explicit end-to-end live tracking audit across backend, web, and mobile.
- Remove remaining client-authority leaks or product-surface gaps found by the audit (the hardcoded web delivery fee is resolved).
- Run full backend, web, Playwright, mobile, migration, and production-preflight validation.
- Freeze one exact candidate SHA, open one real integration PR, require exact-SHA 4/4 CI, merge, and require exact merged-main 4/4 CI.

No staging or production deployment is performed by this reconciliation branch.
