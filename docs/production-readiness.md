# GaonOne production readiness

State of the remediation that followed the horizontal production-readiness
audit, and the things a human still has to do.

## What the money paths now guarantee

These are the invariants worth knowing before changing anything in
`app/services/refunds.py`, `app/services/settlements.py` or the delivery
completion routes.

- **A refund is an obligation, not a status.** Cancelling a paid order writes a
  `PaymentRefund` row in the same transaction as the cancellation. The provider
  call happens separately and is retry-safe. `PaymentStatus.REFUNDED` is written
  in exactly one place — after Razorpay confirms — and until then the order sits
  at `REFUND_PENDING`, which the clients render as "refund in progress".
- **One refund per order, enforced by the database.** The obligation is keyed
  `order-refund:{order_id}` under a unique constraint, and the provider call
  carries `X-Payment-Idempotency-Key`. Repeated cancellation cannot pay a
  customer twice, and a retry after a network timeout returns the original
  refund.
- **Money that went back is not the merchant's.** A confirmed refund voids a
  pending settlement in the same transaction. An entry that was already settled
  cannot be voided honestly, so it gets an explicit negative
  `SettlementAdjustment` instead — the ledger is annotated, never rewritten.
- **Settlement eligibility is recomputed, never assumed.** `settlement_is_eligible`
  reads authoritative order, payment and refund state. Any refund obligation at
  all makes an order unsettleable.
- **Delivery completion still requires verified proof**, and COD completion
  still requires a recorded cash collection. Neither is reachable from the
  legacy status route, which now has no branch that could act on them.
- **A delivery that fails after pickup has exactly one exit**: the admin
  `resolve-failure` endpoint, which returns the goods, ends the order as
  `returned`, voids merchant entitlement and opens the refund. If a cash
  collection is recorded against a failed delivery it refuses and asks a human
  to reconcile, rather than inventing money movement.

## Operating the background worker

The `worker` service drains two queues that must not run inside a request:
the notification outbox and owed refunds.

```
make prod-worker-status     # is it running
make prod-worker-logs       # what it is doing
```

It is built and recreated by `make prod-deploy` and `deploy/release.sh`, and
`deploy/monitor.sh` fails if it is not running. Both queues are claimed under
row locks and are idempotent, so a restart mid-tick loses nothing and two
workers duplicate nothing.

Notification delivery backs off (30s → 2h) and retires an event to `dead`
after six attempts, so one permanently failing event cannot block the queue.
Refunds retry up to eight times; after that they stay visible at
`GET /admin/refunds` and an operator can force another attempt with
`POST /admin/refunds/{id}/retry`.

## Reproducible builds

See the table in the root `README.md`. Every dependency set is locked, images
and CI install from the locks, and `scripts/check_dependency_lock.py` fails CI
if a declared dependency is missing from one.

## Rollback

`deploy/release.sh` records the previously deployed SHA and rolls back to it if
smoke or monitor checks fail after the new containers are live. The rollback
restores **code, not schema** — migrations are forward-only and additive by
contract, so the previous application runs against the newer schema. If a
migration is ever genuinely destructive, that contract breaks and the deploy
needs an expand/contract plan instead.

## Deliberately deferred

Each of these was considered and left, with the reason.

| Item | Why it was left |
|---|---|
| `alembic check` in CI | Against this schema it reports PostGIS's `spatial_ref_sys`, the GIST indexes created in raw SQL, and unique-constraint reflection artifacts as drift. Tuning it to pass means filtering exactly the differences it exists to catch. A check that has to be silenced is worse than none. |
| Platform commission | `merchant_amount` is still `order.subtotal`, so the platform take is structurally zero. Introducing one is a pricing and contractual decision, not an engineering gap. The ledger has the shape to carry it. |
| In-app pickup fulfilment | Stores carry `pickup_enabled` and the UI shows it, but checkout is delivery-only. Supporting pickup orders needs decisions about pricing, collection windows and no-show handling. The pill is honest about the store, not about an in-app flow. |
| JWT in `localStorage` / SharedPreferences | A real tradeoff rather than an oversight. Moving to httpOnly cookies changes the auth model for both clients and the mobile app cannot use them. Mitigated by a CSP and the one-hour token lifetime. |
| Device token rebinding | Re-registering a known FCM token rebinds it to the caller. That is required for the normal handover case (a different person signs in on the same handset) and `token` is uniquely constrained, so refusing the rebind would break handover to defend against an attacker who already has the token. |
| Ruff beyond `E4,E9,F` | The codebase uses a dense one-line style deliberately, and `B008` is FastAPI's own `Depends()` idiom. Enabling those rules would mean reformatting mature working code to satisfy a linter. |

## Manual intervention still required

- **`mobile/pubspec.lock`** is not committed. It could not be generated in the
  environment this work was done in — egress blocks `pub.dev` and
  `storage.googleapis.com`. Mobile CI publishes the lock it resolved as an
  artifact and warns; commit that file and Mobile CI switches to
  `flutter pub get --enforce-lockfile` automatically.
- **Production secrets** are unset by design in `.env.production.example`:
  Razorpay keys and webhook secret, the FCM service account, Google Maps keys
  and MSG91 credentials. Refunds cannot execute without Razorpay credentials —
  the obligation is still recorded and retried, so nothing is lost, but nothing
  moves either until they are configured.
