# P0 payment/geography + P1 territory migration convergence (review only)

## Why this branch exists

The payment integrity branch introduced `0027_webhook_retry_schedule`.
The address-provenance branch introduced `0027_address_location_provenance`.
The territory foundation PR #250 already uses `0028_delivery_territories`
with `0027_address_location_provenance` as its parent.

PR #258 introduced `0028_payment_geography_merge`, joining the two
`0027` revisions. This branch **preserves all four existing revision IDs
and their parentage** and adds an ancestry-only merge:

```text
0027_webhook_retry_schedule --------------------\
                                                 0028_payment_geography_merge --\
0027_address_location_provenance ----------------/                                \
        \                                                                          0029_payment_geography_territories_merge
         0028_delivery_territories ------------------------------------------------/
```

No production data is rewritten by the new merge revision. The copied
`0028_delivery_territories` migration creates seven draft-only tables,
spatial indexes and immutable-history guards. It neither backfills nor
activates coverage. Legacy service areas remain authoritative for checkout.

## Review and test requirements

- Do not merge the original #250 migration separately without reviewing
  the ancestry: it has been copied **unchanged** here to avoid a second
  incompatible `0028` revision.
- Backend CI uses disposable PostGIS databases for payment-first,
  geography-first and territory-first upgrades. It checks a single Alembic
  head, address provenance columns, payment webhook scheduling columns,
  all seven territory tables and zero seeded territory rows.
- Keep P0 checkout geography gating from #257 and payment capture/
  idempotency protections from #243; this PR changes no checkout route.
- Later territory PRs #251–#256 must be ported/rebased against this bridge
  in reviewable chunks, with immutable snapshot and publication safeguards.
  This branch is **not** an activation switch or an admin editor.
- Run combined COD/UPI quote/order, retry, webhook replay, stock reservation
  and cancellation tests on the final merged head before release.

## Operator-only staging verification (never production mutation)

On a disposable staging clone with a verified backup and the new application
image, run `alembic heads` (expect one head), then `alembic upgrade head`
with a restricted migration role. Check the resulting `alembic_version`
and presence of the seven tables. Confirm no territory is active and
the legacy serviceability evaluator remains authoritative.

Before any future production migration, independently verify the deployed
commit and live migration heads **read-only**, compare the schema with the
expected graph, review backups, lock budget and restore drill, and obtain
explicit release authorization. Do not assume production is at b96399b
solely because it was previously reported.

## Rollback

For an application-only failure, redeploy the previous approved image while
leaving additive columns and draft territory tables intact. Never run a
destructive territory downgrade after any territory, version or audit record
exists. If a migration fails, stop rollout and inspect the actual transactional
state and `alembic_version` before any repair. Do not delete audit history,
payment events, addresses, orders or live coverage records.

## Unverified acceptance

Production store/address root-cause diagnosis, combined branch staging
acceptance, physical Android map-pin flow, territory publication/rollback,
and release approval are pending. CI success alone is not production proof.
