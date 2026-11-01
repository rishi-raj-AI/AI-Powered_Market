# Android legacy-address repin: stacked review and release gates

Status: draft, not merged or deployed. This branch is stacked on
`feat/android-confirmed-delivery-pin-20261102` (PR #246) and requires
the additive backend address-provenance API in PR #247.

## Customer flow

- A legacy address remains visible in the cart.
- With `--dart-define=ADDRESS_PIN_REPAIR_ENABLED=true`, unconfirmed
  addresses offer **Confirm saved address pin**.
- The customer explicitly chooses and confirms GPS or a manual map pin.
  Cancellation, invalid coordinates and unconfirmed map centres do not write.
- The client POSTs only the pin and source to the authenticated
  `/addresses/me/{id}/confirm-pin` endpoint. The backend retains original
  address details, archives the old address, and returns a replacement ID.
- The cart reloads addresses after success; no order is placed automatically.
  Quote/checkout must use the replacement ID.
- A backend rejection leaves the original address accessible. If the backend
  saved the pin but refreshing the cart fails, the UI says to reload the cart
  rather than falsely claiming the write was rejected. A timeout or unknown
  network failure is also treated as an ambiguous outcome: reload addresses
  before retrying, because the server may already have archived the old ID.

## Activation and compatibility

The repair action is **off by default**. Do not enable it against a backend
that lacks PR #247 and its migration. The endpoint must be available and its
PostGIS tests and migrations validated before an Android release enables the
flag. Old APKs remain compatible with the additive API.

This change does not alter geographic coverage, payment, checkout idempotency,
production configuration, customer historical orders, or existing address rows.
Do not interpret an address pin as a promise of store-specific delivery.
The temporary FlutterMap/OSM picker from PR #246 is still not approved for
nationwide production use. Google Maps SDK/Places and real-device validation
remain required.

## Tests and review

`mobile/test/address_pin_repair_action_test.dart` covers cancel, explicit
confirmation and new ID, backend rejection, invalid coordinates, and a
successful backend write followed by failed list refresh, and an ambiguous
network failure.

Run `flutter analyze`, `flutter test`, and the Mobile CI workflow on the
exact branch head. Also run backend PostGIS and migration tests from PR #247.
Do not deploy, merge, or publish an APK without approval.

Rollback: disable `ADDRESS_PIN_REPAIR_ENABLED` in a future mobile build.
Keep the additive database columns and backend endpoint in place for older
clients and already confirmed addresses; do not delete historical addresses.
