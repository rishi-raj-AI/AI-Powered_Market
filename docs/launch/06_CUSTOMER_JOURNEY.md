# Customer journey

`Google Sign-In → profile → address/locality/landmark/GPS → discovery → store/catalogue → cart → authoritative quote → COD/available payment → order → tracking/proof → support`

Current static state: these surfaces broadly exist, but authentication is OTP and requires replacement. Address/location, discovery, cart, checkout, orders and support must be exercised after auth work.

Acceptance: customer knows store, availability, authoritative price/delivery fee/total, delivery address, order state and next action. Validate bad input, serviceability failure, unavailable stock, quote change, payment unavailable, offline/retry, long localized text, and unauthorized session handling.
