# P0 checkout provenance — acceptance and rollback gate

Status: **draft / not production-accepted** (2026-11-03). Scope: PR #274, stacked on integrated geography/payment PR #272.

## Source-inspected defect and compatibility contract

The nullable `addresses.location_source` database field is a string, not a database-enforced enum. Before PR #274, a non-NULL, unrecognized value could be treated as `legacy_coordinates` and used to authorize delivery based on coordinates that might represent an unconfirmed locality or imported centroid. This is a **source-level fail-open risk**, not a demonstrated explanation of any particular production rejection.

After this change:
- Only **NULL** provenance with a valid coordinate pair retains the historical `legacy_coordinates` compatibility path.
- Explicit `gps` and `map_pin` sources require the server confirmation timestamp and valid coordinates.
- `searched_place`, unconfirmed GPS/map pins, and any other non-NULL provenance value fail closed with `ADDRESS_LOCATION_UNCONFIRMED`.
- Missing/invalid coordinates, disabled stores, unassigned/inactive coverage, and genuinely out-of-area addresses remain blocked.
- The **store-assigned, approved hub-centred** PostGIS radius remains authoritative for both quote and order placement. Do not expand coverage, use a store-centred radius, or bypass checks to solve a reported rejection.

## New-address provenance guard (stacked follow-up)

Source inspection also found that `POST /addresses/me` could create a **new** address with a coordinate pair and `location_source=NULL`. The central evaluator intentionally accepts NULL provenance for *historical* addresses, so this route allowed clients omitting the source to mint a new address that inherited historical trust. This is a source-level compatibility loophole, not an observed production incident.

The create route now rejects a new coordinate pair without an explicit `gps`, `map_pin` or `searched_place` source (HTTP 422 with pin-confirmation guidance). A manual/landmark address without coordinates can still be saved; checkout continues to require coordinates. An explicitly sourced searched-place centroid is saved but remains ineligible for checkout until the user confirms a pin. Existing NULL-provenance rows remain readable and retain the documented legacy evaluator compatibility. No schema or data migration is introduced. The current Next.js checkout now requires an explicit checkbox confirming that the selected map pin marks the exact delivery entrance before submitting `map_pin` provenance; selecting a searched locality alone is not enough. The current Flutter checkout sends `gps` provenance only after the user explicitly taps Attach GPS location and saves; without GPS it saves a landmark-only address that remains ineligible for checkout until pin confirmation. Older released clients that submit coordinates without a source will receive HTTP 422 and need the confirmed-pin flow; verify the upgrade/fallback UX before release. This guard is not a claim that a client-supplied GPS/map-pin source proves physical presence.

## Review and staging gates (no production changes)

1. Review the two changed code/test files and exact-head CI for Backend, Web, Mobile and Production CI. Backend must execute the restored PostGIS decision suite plus payment/idempotency regressions.
2. In a disposable PostgreSQL/PostGIS test database, verify the NULL-provenance legacy address, confirmed GPS, confirmed map pin, searched-place centroid, unknown source, no coordinates, radius boundary, wrong store assignment and inactive territory cases. For each rejected checkout, assert no order and no inventory change.
3. Stage COD success and UPI pending/failed/captured/retry/refund lifecycles with mocked or sandbox provider responses. Verify failed/ambiguous UPI is never reported paid, and retry cannot create a second charge.
4. Verify Next.js and physical Android location confirmation, manual fallback and low-connectivity flows. CI passing does not substitute for device acceptance.
5. Diagnose the actual reported rejection **only** with operator authorization for one specific store/address pair and an approved read-only database role. Use an isolated approved environment with the candidate code; do not redeploy production just to run a script.

Read-only scoped diagnostic, from the backend directory in that approved environment:

```bash
python -m app.scripts.diagnose_delivery_serviceability \
  --store-id 'AUTHORIZED_STORE_UUID' \
  --address-id 'AUTHORIZED_ADDRESS_UUID' \
  --acknowledge-authorized-access
```

The script starts a read-only transaction and rolls it back. Keep returned UUIDs, rounded distances and business configuration out of public issue comments. Never log coordinates, landmarks, personal details or database credentials.

## Deployment preparation only — explicit approval required

Before a separately authorized release: identify the exact reviewed merge SHA, verify CI at that SHA, review additive Alembic heads and rollback compatibility, verify backup restoration procedures, and record COD/UPI/Android acceptance with an operator. Keep draft territory evaluation non-authoritative; do not activate or mutate territory configurations. Do not merge payment-only PR #243 independently because its temporary geography bypass is not approved.

## Rollback

This PR adds **no migration**. Before deployment, abandon or revert its isolated changes if acceptance fails. If a future authorized release exposes a regression, roll application code back to the last approved SHA using the existing deployment process, preserve existing addresses and financial records, and rerun read-only diagnostics. Never silently revert to the old village-centre fallback or widen coverage. If other stacked migrations have been applied, review expand-and-contract compatibility rather than blindly downgrading a live database.

**Not verified:** actual production root cause, staging financial lifecycle, physical Android GPS/map pin, operator approval and production deployment.
