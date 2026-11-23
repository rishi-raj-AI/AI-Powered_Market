# P0 payment-evidence synchronization on geography checkout (2026-11-03)

This draft change is stacked on PR #269 and preserves its fixed React Strict Mode payment-capture mock. It selectively ports security-sensitive changes inspected at payment PR #243 commit `ccd26be9c851dc118cc7919df3dcab04dd19971d` without importing the payment-only branch's temporary delivery-zone bypass.

## Invariants

- Razorpay captured amounts must be **integer paise**, never floating-point, boolean, string or missing values. Ambiguous evidence must not mark UPI paid, release fulfilment or restore stock.
- Any other attempt with either local paid status **or** a provider payment ID blocks duplicate settlement, even if historical records are partially inconsistent.
- A failure for one attempt cannot mark the commercial order failed when another attempt has payment evidence.
- Signed capture events with mismatched provider evidence remain pending for reconciliation rather than being marked successfully processed.
- Expiration defers unknown, authorized, processing and refunded local attempt states even if provider history is empty.
- The Next.js order screen ignores late stale fetches that would overwrite a newer paid status. The previous PR #269 deterministic webhook test is retained.

## Validation and release gate

Run the exact-head Backend, Web, Mobile and Production CI workflows. The backend regression suite must include malformed paise, partial prior-capture evidence, failure on another attempt, ambiguous expiry and webhook replay. The Web Playwright suite must include a delayed stale order refresh racing verified payment. These tests use synthetic data and do not establish production correctness.

Before deployment, require authorized read-only production serviceability diagnosis of one affected store/address pair, staging COD and UPI full-lifecycle acceptance (including provider outage, duplicate callbacks, refund reconciliation and retry), review of all stacked migrations, and physical Android pin confirmation. No production checkout bypass, real payments, territory activation or APK publication is authorized by this PR.

## Deployment / rollback (operator preparation only)

1. Record approved exact release SHA, deployed SHA, DB migration heads, health checks, and pre-release verified backup. Check the payment/geography migration merge ancestry before any rollout.
2. Deploy only after owner approval and staging signoff. Keep territory activation and unpaid reservation expiry disabled by default. Verify order quote/place, payment status and fulfillment gates with approved synthetic staging accounts.
3. If regression is detected, stop rollout and revert the application to the last known-good compatible release. Preserve additive schema, payment attempts, signed webhook ledger, refund obligations and audit history. **Do not** downgrade destructive migrations or re-run ambiguous financial actions. Reconcile provider captures/refunds before retries.

Production diagnosis, staging acceptance and device acceptance remain pending.
