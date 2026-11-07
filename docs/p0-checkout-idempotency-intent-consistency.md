# P0 checkout idempotency intent consistency

## Scope and rationale

This stacked change is based on geography/payment integration PR #264, not the
payment-only PR #243. Existing checkout always returns an order for a repeated
`Idempotency-Key`, even if the caller changes the address or switches between
COD and UPI. That silently returns a different commercial intent, which is
especially misleading for payment recovery and address-confirmation retries.

The fix compares the persisted order's `address_id` and `payment_method`
against the retry payload at **both** the initial idempotency lookup and the
second lookup after the cart row lock. Mismatches return HTTP 409 with a
generic message. Identical retries return the original order even if the cart
has since been emptied or the original address archived.

No existing order, payment, stock, geographic coverage, migration or live data
is changed. This does not retroactively fingerprint cart items or prices;
future full-request fingerprints need a separate schema/compatibility design.

## Disposable-database acceptance

- Matching COD/UPI intent returns the original order, with no duplicate.
- Reused key with a different address returns 409; no order or stock change.
- Reused key with a different payment method returns 409; no order or payment change.
- The same checks hold when a competing request commits before the post-lock read.
- An identical retry still returns its original order after address archival.
- Existing geographic eligibility checks remain authoritative for **new**
  COD/UPI orders; an idempotent retry does not create a new order.

Run backend CI with PostgreSQL/PostGIS, including
`pytest -q tests/test_checkout_idempotency_payload.py tests/test_payment_geography_checkout_gate.py`.
Run all Backend, Web, Mobile and Production CI on the exact PR head. Do not
treat an independent payment-only CI pass as integrated checkout acceptance.

## Staging and production gates

Before merge: review PR #243 drift, payment capture/refund state machine,
migration ancestry, checkout geography tests and CI. Before deployment:
authorized read-only diagnosis for a known failing store/address pair, staging
COD/UPI lifecycle including failed and late payments, real-device address
confirmation, backup/restore rehearsal, and operator approval.

**No deployment or production mutation is authorized by this change.**
Rollback before release: close the draft PR / revert this commit on its
integration branch. After any future approved deployment: roll back the
application release to the previous signed image; no schema rollback is
required for this change. Preserve financial data and reconcile any in-flight
payment attempts before switching binaries.
