# GaonOne Priority 2–3: code-level release acceptance

This checklist applies to repository code and GitHub CI only. It does **not**
authorize a live deployment, a signed APK build, a production configuration
change, or activation of automatic dispatch or product media.

## Immutable baseline

- Priority 1 integrated implementation: [PR #235](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/235), merged.
- Overlapping delivery-area fix: [PR #240](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/240), merged as `224a358b0609090ef06de5ae0a45268065c411a0`.
  Backend, Web, Mobile and Production CI passed at source head
  `57216f96a5760833b9cfc20e63af4a64f4dcf420`.
- Secure merchant photos: [PR #239](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/239).
- Additional delivery-boundary acceptance: [PR #241](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/241).

## Required code-level gates

1. **Exact-head CI:** Backend, Web, Mobile and Production workflows must all
   pass on the final merged code, not just on an ancestor or a sibling branch.
2. **PostGIS geography:** An active overlapping zone that contains the exact
   customer pin must be selected even if a nearer, non-covering hub exists.
   Verify 1-km boundary inside/outside points, inactive zones and inactive
   hub villages. Radius zones are geography circles; no polygon model exists
   in this release.
3. **Checkout:** Address creation and cart quote must agree with the same
   PostGIS coverage predicate. A specific store's assigned zone remains
   authoritative. The place-order endpoint must reject genuinely out-of-zone
   addresses, even if another zone covers them.
4. **Web address entry:** Choosing a locality must never silently assign its
   centroid as the customer's exact entrance. Customers must select a pin
   before a new address is submitted.
5. **Merchant media:** Listing-scoped uploads require ownership, MIME/size
   checks, private quarantine and a valid HTTP 202 quarantine acknowledgement.
   Storage failures must fail closed without public raw-upload fallback.
   Alt-text edits must be owned/audited and must not change media approval.
6. **Cross-role operations:** Existing Backend CI and Playwright suites must
   remain green for COD/place-order, idempotency, merchant/rider alerts,
   dispatch contention, proof-of-delivery and settlement/recovery authorization.

## Evidence and limitations

Record the final PR numbers, merge SHAs and exact-head workflow URLs after
checks complete. A green CI run verifies repository behavior under test;
it does not prove real GPS precision, provider connectivity, production
service-area configuration or actual rider/customer experience.

Legacy addresses without an exact saved coordinate may use an older
locality-based checkout fallback. Do not treat a locality centroid as evidence
of the customer's physical location. A future migration/repinning policy
requires separate product acceptance and must not silently expand a store's
configured delivery area.

## Explicitly excluded from this task

- Live web/API/worker deployment, database migrations or server changes.
- Android APK building, signing or distribution.
- Secrets, keystore, environment variable or production configuration edits.
- Enabling `AUTO_DISPATCH_ENABLED` or `PRODUCT_MEDIA_ENABLED`.

The recurring code-development task may stop only after Priority 2, Priority 3
and the delivery-zone correction have all passed code-level validation.
