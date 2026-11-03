# P0 checkout: geography/payment integration gate (2026-11-03)

**Status: review only; no merge/deployment authorization.** Geography integration PR #276 is at `8002f5c85e1aa6cc5c5d7bfde4f74d9c5cace26a`; payment PR #243 was inspected at `e823d6e3fbec49c5192a81f62f7aa751f3e8149e`. Both remain open. The GitHub compare endpoint reports diverged histories (payment head 105 ahead, 133 behind geography; merge base `95d998c02e5d62e77c0508ae56bb41d851b55a5d`). These numbers describe ancestry, **not** 105 safe cherry-picks.

## Integration boundaries

- Keep `backend/app/services/delivery_serviceability.py` authoritative for quote **and** transactional order placement; never import the payment-only temporary delivery-zone bypass or replace approved hub-centered store assignment with a store/village-centre approximation.
- Preserve the new-address provenance guard and Next.js confirmed doorstep pin / Flutter explicit GPS provenance. Historical NULL-source addresses remain a compatibility exception; unknown non-NULL sources and searched-place centroids do not authorize checkout.
- Treat payment PR #243 as an independently advancing source, not an automatic merge target. The comparison includes overlapping `backend/app/api/v1/routes/payment_hardening.py`, `payments.py`, `backend/app/services/payment_expiration.py`, `backend/app/services/payments.py`, and payment regressions. Compare each changed function against the integrated branch; copy only missing behavior with isolated tests. Preserve geography branch's payment-history preflight before provider I/O.
- For any payment-state transition, require verified provider capture, exact order/amount/currency association, idempotent webhook handling and safe refund reconciliation. A failed, pending, unknown or ambiguous UPI attempt must not create a paid order or trigger fulfilment.
- Avoid modifying live service areas, payment records, refund records, inventory or secrets. No production data migration, deployment or production APK.

## Reviewable integration sequence

1. Freeze both head SHAs; inventory changed paths and overlap from GitHub comparison. Record each payment function as already integrated / new and safe / conflicting / excluded. Never use a wholesale checkout-file replacement.
2. Create a fresh **draft** branch from the latest green geography integration head. Cherry-pick or manually port **one independently testable payment fix at a time**, excluding the temporary geography bypass. Commit with source PR/commit reference and test evidence.
3. Run PostgreSQL/PostGIS tests for active/inactive/missing store territory, inside/outside/boundary radius, confirmed GPS/map pin, unconfirmed/unknown source, legacy NULL source, and rejection with no order/inventory mutation. Run payment-history ordering, failed capture, signed webhook replay, concurrent refund, stock restoration and idempotency regressions.
4. Run Backend, Web, Mobile and Production CI **at the resulting combined SHA**, not only at independent PR heads. Resolve any failures before declaring integration green.
5. Perform staging COD, UPI pending/failed/captured/retry/refund, low-connectivity Next.js, physical Android pin/GPS and older installed-client compatibility acceptance. Specifically check whether older clients sending coordinates without `location_source` receive 422 and show a usable upgrade/confirmation path.
6. With operator authorization only, run the scoped SELECT-only diagnostic for one affected production store/address pair as documented in `docs/p0-serviceability-provenance-acceptance.md`. Keep coordinates, identifiers and credentials out of PR comments. A CI pass is not proof of production root cause.

## Release/rollback preparation

Require a reviewed combined SHA, green exact-head CI, migration-head compatibility review, staging payment and location sign-off, and an explicit separate deployment authorization. Prepare the existing deployment rollback to the last approved application SHA; do not roll back live financial data, silently widen coverage or downgrade additive geography migrations without compatibility analysis. Keep any new territory model draft/non-authoritative until separately approved.

**Unverified:** production checkout rejection root cause, staging financial lifecycle, physical Android location behavior, older-client fallback, and production release acceptance.
