# Web confirmed-pin provenance: review and rollout

Status: draft, stacked on web map initialization fix PR #245. No deployment.

## Behavior

- Selecting a Places autocomplete result positions the map and may show
  platform-wide serviceability, but is **not** treated as a doorstep.
- A deliberate map drag or an explicit browser GPS action records a
  customer-selected pin source. The customer must still press **Save address**.
- The form blocks saving a searched-place centroid without that action.
- Changing locality or editing the search invalidates prior confirmation.
- Legacy coordinates with NULL `location_confirmed_at` display as
  **confirmation unrecorded**, never as a confirmed pin.
- The server-supplied `location_confirmed_at` remains the authoritative
  recorded provenance; the frontend cannot fabricate it.

## Backend compatibility

`NEXT_PUBLIC_ADDRESS_PIN_PROVENANCE_ENABLED` defaults to false. Once backend
PR #247's additive migration and API have passed acceptance and been deployed,
a reviewed web build may enable it to submit `location_source` (`gps` or
`map_pin`) for newly saved addresses. The backend timestamps confirmation.
Do not enable before the backend rollout.

The stricter explicit-pin UX does not require new server fields and can be
reviewed independently. The platform-wide serviceability preview is not a
store-specific checkout promise; the checkout endpoint remains authoritative.

## Validation

Run Web CI, Playwright location tests, TypeScript checks and real-browser
Google Maps/Places acceptance. New Playwright tests cover rejection of
unconfirmed searched-place centroids, successful deliberate map drag, and
honest labelling of legacy coordinates.

No changes to payment verification, territory configuration, pricing,
checkout idempotency or production data. Rollback by reverting the web build
or disabling provenance submission; do not downgrade additive DB columns.
