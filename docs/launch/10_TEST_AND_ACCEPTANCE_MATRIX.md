# Test and acceptance matrix

| Surface | Required evidence | State |
|---|---|---|
| Backend auth | Unit/integration tests for token verification, mapping, sessions, disabled SMS, production fail-closed config | PARTIAL — merged Phase 2A coverage passed the required CI gates; retain release/device acceptance work |
| Authorization | Customer/merchant/delivery/admin negative and ownership tests | PARTIAL — existing coverage; revalidate after auth |
| Web | Build, Playwright critical paths, accessibility and responsive visual QA | IN_PROGRESS — `npm run build` and all 304 local Playwright checks pass; Google session restoration, stale customer-quote response ordering, idempotent checkout retry, live-tracking/account session expiry, current-market location application, stale location/discovery response ordering, serialized cart mutations, a forced duplicate address-save submit, and a confirmed address surviving a failed post-save refresh are covered; visual QA remains pending |
| Flutter | Analyze, unit/widget tests, debug Android build and Android visual QA | PARTIAL — baseline CI passed; Firebase and visual work pending |
| Customer/operations | End-to-end actor journeys, state transitions, quote/payment boundaries | IN_PROGRESS — address/discovery/cart/quote/COD/order/tracking/proof/support tests are mapped; cross-browser regressions cover stale quote rendering, expired cart/live-tracking/account session handling, retrying an uncertain checkout with a stable idempotency key, current-market location application, stale autocomplete/selected-place/delivery-location/discovery results, preventing overlapping cart mutations from superseding an authoritative result, and preventing a duplicate pending address save from initiating a second network request or hiding the confirmed address after its refresh fails |
| Release | Compose/images, production config audit, owner config checklist, explicit release approval | BLOCKED |

Repository commands: `make test-backend`, `make test-web`, `make test-e2e`, and `make mobile-check`; CI also runs Android analysis/tests/build and production compose/image validation. Do not use arbitrary sleeps to stabilize async tests.
