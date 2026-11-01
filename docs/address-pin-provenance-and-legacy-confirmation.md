# Address pin provenance and legacy-address confirmation

Status: **draft implementation, not deployed**. Base: `main` at `b96399b`.

## Source-of-truth contract

A saved address has a customer-delivery pin only when the customer explicitly
confirms a GPS fix or map selection. A village or searched-place centroid is not
a verified doorstep merely because it has latitude/longitude.

New nullable fields on `addresses`:

| Field | Meaning |
| --- | --- |
| `location_source` | `gps`, `map_pin`, or `searched_place` when the client asserts explicit confirmation |
| `location_confirmed_at` | UTC server timestamp when that assertion was saved |
| `location_accuracy_meters` | Optional reported GPS accuracy, **not** a guarantee |
| `place_id` | Optional provider place identifier |

Existing addresses remain unchanged, including coordinates. NULL provenance
must be interpreted as **legacy/unverified**. No data backfill infers confirmation.

Clients must not send `location_source` on autocomplete alone or on map
initialization. A customer must first confirm the selected pin. Place centroids
may help move the map but are not confirmed doorstep coordinates.

## API

`POST /api/v1/addresses/me` accepts the four optional metadata fields and
continues to support legacy requests. When `location_source` is supplied, a
coordinate pair is mandatory. Metadata without a source is rejected. The
server, not the client, assigns `location_confirmed_at`.

`POST /api/v1/addresses/me/{address_id}/confirm-pin` accepts:

```json
{
  "latitude": 18.5204,
  "longitude": 73.8567,
  "location_source": "map_pin",
  "location_accuracy_meters": null,
  "place_id": null
}
```

The endpoint requires the authenticated owner and an unarchived address.
It checks the point against current **platform-wide** coverage (not a promise
that every store delivers there). It locks the old address, creates a new row
with the original contact/address details and confirmed coordinates, archives
the old row, and commits atomically. The response is the replacement address
with a **new ID**. Checkout and quote must use this new ID.

This design preserves historic order foreign keys and `delivery_address`
snapshots. No old order is repointed. Customer coordinates are not emitted in
ordinary application logs.

## Rollout order

1. Verify disposable PostGIS `alembic upgrade head` and downgrade/upgrade
   cycle, schema consistency, and all backend tests.
2. Merge and deploy the additive migration **only after separate approval**.
   Until then the endpoint must not be called by mobile or web clients.
3. Integrate Android and web explicit pin confirmation. PR #246 now
   sends optional provenance after Flutter confirmation, but the existing
   backend cannot persist it until this migration is released; PR #245 stops
   the web map from silently selecting a fallback point.
4. Make legacy addresses editable via the replacement endpoint and refresh
   saved address/selected ID after confirmation. Never automatically alter
   a historical order.
5. After P0 serviceability PR #244 is reconciled, update its
   `location_confidence` reporting to distinguish confirmed vs legacy.
   Enforce stronger confidence only behind a reviewed feature flag, with
   a customer migration path and verified COD checkout tests.

## Safety / rollback

No production data is changed by this PR. Migration is additive and nullable,
with no backfill or territory changes. Application rollback can leave the
nullable columns in place. A deliberate Alembic downgrade drops provenance
columns and therefore **loses newly captured provenance**; back up and review
that loss before downgrading. Never reset volumes or overwrite environment
files.

## Remaining acceptance gates

- Required CI, PostGIS migration round-trip, negative authorization tests
- Android Google Maps SDK and Places integration with restricted client keys
- Web and Flutter explicit pin provenance submission
- Real-device GPS denial/timeout/manual selection tests
- Authorized production checkout diagnosis, store-specific quote parity,
  controlled COD smoke test and deployment approval
