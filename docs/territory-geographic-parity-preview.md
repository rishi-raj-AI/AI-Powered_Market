# Read-only geographic parity preview (not checkout authority)

The admin-only `POST /api/v1/admin/delivery-territories/parity-preview` compares an **explicit test point** against a store's existing assigned legacy service-area circle and the separately published, **active** territory preview. It is an operational migration aid; it never changes order eligibility, payment state, store assignments or coverage.

## Access and privacy

- Disabled by default under `TERRITORY_ADMIN_PREVIEW_ENABLED=false`; requires `geography.manage`.
- Request body: `{"store_id":"UUID","latitude":18.52,"longitude":73.85}`. Do not put customer address coordinates in URLs, request logs, metrics, issue comments or screenshots. Prefer synthetic or consented test points.
- Response includes booleans and a classification only, **not coordinates, customer IDs, address text, distance or contact details**.
- `MATCH_BOTH`: both geographic models cover the test point; `LEGACY_ONLY`: possible contraction; `TERRITORY_ONLY`: possible expansion; `NEITHER`: neither model covers it.
- `NOT_COMPARABLE`: inactive/unapproved store, disabled delivery, or missing/invalid legacy coverage. It is **not** counted as a false mismatch or as permission to deliver.
- Even `MATCH_BOTH` does **not** verify doorstep-pin provenance, delivery capacity, fees, inventory, payment or full checkout parity.

## Safety limitations

The new matcher only considers **active** territories and assignments whose live geometry/exclusions exactly match the immutable published snapshot. Draft territories intentionally do not match. This tool is **not** an activation impact-preview substitute; draft geometry requires a separate reviewed analysis path before activation.

Do not enable new territories or change checkout authority based on a few sampled points. Prior to a rollout, review boundary, exclusion, overlapping-territory, active/inactive-store, legacy-provenance and COD/UPI tests with a synthetic/authorized sample matrix and independent operational approval.

The endpoint is read-only at application level; it executes SELECTs. For production diagnosis, use a least-privilege database account and a read-only transaction, and do not invoke this endpoint without explicit authorization.

## Review and rollback

Run `pytest -q backend/tests/test_territory_parity.py` from the repository root with a disposable PostGIS test database and the established backend test environment, or run the repository's Backend CI. No migration is required. Rollback is to leave the feature flag disabled or revert this isolated endpoint/service; existing legacy checkout remains unchanged. **No production deployment, data mutation or APK publication is authorized by this PR.**
