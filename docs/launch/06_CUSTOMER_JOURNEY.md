# Customer journey

`Google Sign-In → profile → address/locality/landmark/GPS → discovery → store/catalogue → cart → authoritative quote → COD/available payment → order → tracking/proof → support`

Current state: Firebase/Google exchange authentication is on main; address/location, discovery, cart, checkout, orders and support must continue to be exercised as one customer path.

Acceptance: customer knows store, availability, authoritative price/delivery fee/total, delivery address, order state and next action. Validate bad input, serviceability failure, unavailable stock, quote change, payment unavailable, offline/retry, long localized text, and unauthorized session handling.

Phase 3 evidence in progress: the checkout now discards a late quote for an unselected address rather than displaying stale delivery pricing, and an automated browser test proves session expiry sends a customer back to the provider-neutral login flow with the original storefront as the safe return destination. That slice merged in PR #184 as `09e0e5c` after all four CI gates passed. The current slice supplies and preserves an idempotency key for the same cart/address/payment checkout attempt, so a connection loss can safely retry against the backend's existing order contract; the full local Playwright suite passes 264 checks across Chromium, Firefox, WebKit, and mobile Chrome. This is functional browser evidence, not device or visual acceptance evidence.
