# Launch status

Updated: 2026-10-23
Verified security baseline: `origin/main` = `39c356e5df5ab733f226a77b4bd74040636ef904`; protected golden main remains at last-verified `45b4b28144b38cf11b7c2e688a7a7ae651be1078` pending a future safe fast-forward that preserves the exact seven owner-owned Flutter/iOS modifications.

| Field | Status |
|---|---|
| Active worktree / branch | `gaonone-launch-next-security-remediation` / `fix/next-security-2026-10` |
| Security PR | [#208](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/208) — narrow dependency security remediation; local validation and focused review pass, required final-head CI is pending. |
| Current phase | Launch-critical actor acceptance (Phases 3–6; current-main dependency security remediation ahead of merchant-transition rebase) |
| Objective | Validate and close launch-critical customer and operations gaps without deployment or broad redesign |
| Completed | Phase 1 merged as `b730bba`; Phase 2A merged as `39ee103`; Phase 2B merged as `78983ba`; Phase 3 checkout/session reliability merged as `09e0e5c`; checkout idempotency as `dc76d50`; live-tracking session boundary as `2432dc6`; account-session safe return as `5fffca1`; location/cart/address/support/payment-intent resilience as `dff5dc6`, `522861c`, `d5b3d3c`, `98955ae`, and `524b1d1`; security PRs #195/#196 as `168a496`/`2b5b124`; checkout duplicate-submit as `30d420c`; signed-payment-confirmation as `6825f8`; merchant availability as `99f10e`; delivery-task privacy as `26e35b`; UPI fulfilment/login cold-hydration as `a1fa04f`; Flutter delivery-completion as `f64e8bf`; delivery-proof security as `4e52787`; and web delivery-handoff PR #204 as `45b4b28`. Release workflow is manual-dispatch only; Firebase identity/session/SMS and both Google clients are on main. |
| In progress | Current `main` is affected by newly disclosed Next/React/Sharp/source-map-js advisories. The isolated dependency-only update resolves Next `16.4.2`, React/React DOM `19.0.9`, Sharp `0.35.5`, and source-map-js `1.2.2`; clean production audit, production webpack build, and all 400 browser cases pass. The validated merchant recovery awaits this security remediation before rebase and PR creation. |
| Blocked | Database-backed regressions require CI on this host; local PostgreSQL driver/Docker and Android SDK are unavailable. Firebase setup, device acceptance, and visual evidence remain release dependencies. Independent source work continues. |
| Next exact action | Evaluate all four required gates on security PR #208's final head, merge only after green CI and no unresolved P0/P1, then safely fast-forward protected main while preserving its seven owner changes. Rebase merchant-transition recovery from the new main only after this security work merges. Do not deploy. |
| CI baseline | All four required checks passed for Phase 2A final head `ecfeb54`; Phase 2B final head `d8cb6fa`; prior Phase 3/security actor-slice PRs; and web delivery-handoff #204 final head `604d342`. Security PR #208 is open; its four final-head gates remain required. |
| P0 blockers | Firebase owner configuration and device acceptance remain release gates; protected-main preservation remains mandatory. R-022 is mitigated by merged #203; R-023 needs final-head CI before mitigation is complete. |
| Owner dependencies | Firebase project/server credentials, OAuth origins, Android/iOS config/signing, domains/CORS; payment/maps decisions |
| Deferred | Product-media B2+, R2/scanner, banner enhancement, MSG91/DLT activation, scheduled fulfilment, pickup expansion, nonessential refactors/AI/cosmetic redesign |
| Latest decisions | AUTH-001–011, CHECKOUT-001–002, PAYMENT-001–005, SECURITY-001–003, SESSION-001–002, LOCATION-001, CART-001, ADDRESS-001, SUPPORT-001, RELEASE-001, MEDIA-001–002, UX-001–002, AVAILABILITY-001, DELIVERY-PRIVACY-001, DELIVERY-COMPLETION-001–002, DELIVERY-PROOF-001 |
| Safe resume point | `docs/launch/15_SESSION_HANDOFF.md`; do not deploy without explicit authorization |
