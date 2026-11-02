# Initial delivery-territory snapshot publication (draft-only)

This is a **non-production** implementation stacked on the territory preview
and schema PRs. It adds a disabled-by-default, super-admin-only operation to
record the **first** immutable geometry snapshot of a **draft** territory.
It is deliberately **not** a coverage activation, editing, assignment,
rollback, checkout, or payment endpoint.

## Contract

`POST /api/v1/admin/delivery-territories/{territory_id}/publish-initial-draft`

- Requires `territory_admin_publish_enabled=true` in the backend environment
  (setting `TERRITORY_ADMIN_PUBLISH_ENABLED`, default **false**).
- Requires `admin.manage`, available only to an active super-admin.
- JSON: `{"expected_published_version":null,"change_reason":"Approved draft snapshot reason"}`.
- Only a never-published `status=draft` territory is eligible.
- Locks the territory and existing exclusions, checks circle/polygon geometry,
  writes a new immutable version and append-only audit record, and advances
  `published_version` **in one transaction**.
- Returns `coverage_activated=false` and `checkout_authoritative=false`.
- Does **not** set territory or assignment status to active.
- A stale expected version returns 409; incomplete geometry returns 422.
- Does not expose coordinates, customer data, or secrets.

The publishing code is intentionally narrower than the eventual general
publishing/rollback workflow. Subsequent edits, activation, assignment changes
and rollback require separate reviewed APIs with locking, audit, impact
preview and approval. In particular, every future geometry/exclusion writer
must lock the parent territory row first, otherwise concurrent edits can
invalidate the published snapshot; the preview guard then fails closed.

## Verification and release

Run the backend CI against disposable PostgreSQL/PostGIS, including
`tests/test_territory_publication.py` and
`tests/test_admin_territory_publication.py`. Verify migrations, permission
denial, immutable version/audit, optimistic version conflict, invalid geometry
and unchanged legacy checkout.

**Do not enable or deploy this feature without explicit authorization.**
The payment and geography migration stacks currently have competing Alembic
`0027` heads. Reconcile them, validate combined migrations and payment/checkout
tests, and obtain review before any integration or rollout.

Rollback: keep the feature flag off or revert this code. The API itself adds no
migration. An already committed immutable version/audit must not be deleted or
rewritten; subsequent reversal requires a separately approved compensating
version, not a destructive rollback. No production configuration was changed.
