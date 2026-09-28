# Customer journey

`Google Sign-In → profile → address/locality/landmark/GPS → discovery → store/catalogue → cart → authoritative quote → COD/available payment → order → tracking/proof → support`

Current static state: these surfaces broadly exist, but authentication is OTP and requires replacement. Address/location, discovery, cart, checkout, orders and support must be exercised after auth work.

Acceptance: customer knows store, availability, authoritative price/delivery fee/total, delivery address, order state and next action. Validate bad input, serviceability failure, unavailable stock, quote change, payment unavailable, offline/retry, long localized text, and unauthorized session handling.

Phase 3 evidence in progress: the checkout now discards a late quote for an unselected address rather than displaying stale delivery pricing, and an automated browser test proves session expiry sends a customer back to the provider-neutral login flow with the original storefront as the safe return destination. The full local Playwright suite passed 260 checks across Chromium, Firefox, WebKit, and mobile Chrome. This is functional browser evidence, not device or visual acceptance evidence.
