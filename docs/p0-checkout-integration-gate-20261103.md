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

## Bidirectional source inventory (2026-11-03 follow-up)

Compared payment `e823d6e` against geography `8002f5c` in **both directions**. GitHub compare describes ancestry relative to a merge base; per-file additions/deletions are not proof of behavior missing from either head. The following paths require **function-level** reconciliation, not wholesale cherry-picking:

| Path | Integration action | Verification |
| --- | --- | --- |
| `backend/app/api/v1/routes/payment_hardening.py` | Compare signed event parsing, capture/refund state transitions, malformed payload handling | Invalid signature, contradictory refund, duplicate/replayed webhook, captured-only fulfilment |
| `backend/app/api/v1/routes/payments.py` | Compare payment-intent preflight, history reconciliation, provider order binding | Missing/duplicate/cross-order history, both UUID orderings, ambiguous retries |
| `backend/app/services/payment_expiration.py` | Compare expiry and stock release sequencing | Pending/failed/expired versus captured, idempotent release |
| `backend/app/services/payments.py` | Compare provider capture/amount/currency binding | Wrong order, amount, currency, partial evidence, provider timeout |
| `backend/app/api/v1/routes/checkout.py` | Preserve geography-head evaluator; **exclude temporary delivery-zone bypass** | Quote/order parity, no out-of-zone order or stock mutation |
| `backend/app/services/delivery_serviceability.py` | Retain authoritative geography-head service | Inside/outside/boundary, inactive/missing territory, provenance |
| `backend/alembic/versions/0027_address_location_provenance.py`, `0028_delivery_territory_foundation.py`, `0028_payment_geography_merge.py`, `0029_payment_geo_territory_merge.py` | Validate heads/dependencies against final combined ancestry; never replay migrations blindly | Alembic heads/history, clean upgrade on disposable PostGIS database |

**Evidence from comparison:** Payment-to-geography shows payment route/service and regression changes; geography-to-payment additionally shows the scoped read-only diagnostic, centralized delivery evaluator, address provenance and territory migrations. Some payment tests occur in **both** comparisons because their common ancestor predates the implementations; do not classify these as missing merely because a file appears in a diff.

**Safe execution order:** (1) freeze current head SHAs again before editing; (2) inspect functions and tests side-by-side; (3) identify a genuinely missing payment behavior; (4) port only that behavior to a fresh branch based on the green geography head; (5) run focused PostgreSQL/PostGIS and payment regressions, then all four exact-head CI workflows; (6) complete staging and device acceptance. If both heads have moved, repeat the comparison rather than relying on this snapshot.

No code integration, CI execution, staging test or production diagnostic is claimed by this inventory.
