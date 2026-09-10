# Release Reconciliation State

- Authoritative branch: `main`
- Integrated release reconciliation PR: #166
- Current deployable SHA: `5528f86224ba2cf2533d9f5632740286c2009a14`
- Subsequent integrated fixes: #167 (Razorpay refund idempotency) and #168
  (resolved-delivery recovery queue)
- Completed capability families: full X01-X70 historical audit; area-first terminology; X01-X04 location/discovery/search intent; X07/X29 explicit substitutions; X08/X31 safe reorder preview; X11/X32 India-local store availability; X13/X36/X42 durable support workflow; X26 backend-authoritative cart/checkout quote; X38 merchant settlement visibility; X39 actionable updates; X41 factual admin delivery performance; X50/X62 notification device controls; X61 address book; X64 media; X65/X66 delivery incident recovery; X68 proof receipt; end-to-end live delivery tracking
- Recovered capabilities: area/locality search; current GPS; coordinate context; serviceability context; recent-location memory; PostGIS nearby stores; availability-aware store/product/category search; deterministic relevance/distance ranking; nearby suggestions; fresh post-pickup route insight; customer web/mobile tracking maps; rider assigned-delivery navigation; ownership-checked customer support tickets and admin resolution queue; merchant settlement ledger; owner-scoped address/device management; order-linked stored updates; merchant media upload; rider incident reporting; protected admin recovery queue; customer proof receipt
- Superseded capabilities: historical Python/cumulative discovery stacks; X12/X14/X19-X21 duplicate checkout intelligence; X13 actions already backed by current cancellation/tracking/reorder/recovery flows; X17/X24 predictive cadence replaced by explicit live reorder preview
- Obsolete capabilities: cumulative historical migrations and pre-hardening payment/order code; unsupported popularity/complement scores (X09-X10); fabricated preparation fallback (X15/X22); non-persistable scheduled-mode recommendations (X16/X23); arbitrary merchant trust percentages (X18/X25)
- Partially completed capability: X05-X06 promise/window audit remains intentionally unrecovered until checkout can persist an auditable fulfillment-window contract
- Reconciliation outcome: integrated. No outstanding historical branch remains
  eligible for merge; obsolete stacked and validation-only branches were closed
  after the current architecture was verified as their safe replacement.
- Validation before integration: Ruff passed; backend 221 passed; clean web
  build and Playwright/accessibility suite 148 passed; Flutter analysis passed
  and 3 Flutter tests passed; production environment/Compose validation and
  locked backend/web image builds passed.
- Exact-main CI: Backend CI `34341362011`, Web CI `34341362009`, Mobile CI
  `34341362013`, and Production CI `34341362031` all passed on the current
  deployable SHA.
- Current stage: foundation and delivery-first implementation complete; proceed
  with staging E2E validation and launch preparation. This is not a production
  deployment approval.
