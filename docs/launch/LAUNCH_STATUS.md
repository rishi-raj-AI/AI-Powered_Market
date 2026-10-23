# Launch status

Updated: 2026-10-23
Verified baseline: `origin/main` = protected local main = `43b683e255bc2cfc89c3f15689baeb98c31b6432`; the exact seven owner-owned Flutter/iOS modifications remain intact.

| Field | Status |
|---|---|
| Active worktree / branch | `gaonone-launch-merchant-transition-recovery` / `test/merchant-order-acceptance` |
| Security PR | [#208](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/208) merged as `43b683e` after all four required gates passed on final head `911044c`. |
| Merchant-transition PR | [#209](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/209) is open from `test/merchant-order-acceptance`; its exact final branch head must pass all four required gates before any merge. |
| Current phase | Launch-critical actor acceptance (Phases 3–6; Gate D merchant order-transition recovery active) |
| Objective | Validate and close launch-critical customer and operations gaps without deployment or broad redesign |
| Completed | Phase 1 merged as `b730bba`; Phase 2A as `39ee103`; Phase 2B as `78983ba`; customer reliability, checkout, delivery, and web handoff work through PR #204 as `45b4b28`; and dependency-security PR #208 as `43b683e`. Release workflow is manual-dispatch only; Firebase identity/session/SMS and both Google clients are on main. |
| In progress | Merchant order-transition recovery keeps `/merchant` and `/merchant/orders` server-authoritative, synchronously serializes forced duplicate actions, and reconciles uncertain responses without replay. On rebased source commit `171d01a`, clean install, production audit (0 production vulnerabilities), production webpack build, 36 focused cross-browser cases, and all 436 browser cases passed; focused review found no unresolved P0/P1. |
| Blocked | Database-backed regressions require CI on this host; local PostgreSQL driver/Docker and Android SDK are unavailable. Firebase setup, device acceptance, and visual evidence remain release dependencies. Independent source work continues. |
| Next exact action | Evaluate all four required gates on PR #209's final head; merge only after green CI and no unresolved P0/P1; then safely fast-forward protected main while preserving its seven owner changes. Do not deploy. |
| CI baseline | All four required checks passed for security PR #208 final head `911044c`. Merchant recovery PR #209 CI is running and must be evaluated only on its final head. |
| P0 blockers | Firebase owner configuration and device acceptance remain release gates; protected-main preservation remains mandatory. R-023 is mitigated; R-024 awaits final-head CI. |
| Owner dependencies | Firebase project/server credentials, OAuth origins, Android/iOS config/signing, domains/CORS; payment/maps decisions |
| Deferred | Product-media B2+, R2/scanner, banner enhancement, MSG91/DLT activation, scheduled fulfilment, pickup expansion, nonessential refactors/AI/cosmetic redesign |
| Latest decisions | AUTH-001–011, CHECKOUT-001–002, PAYMENT-001–005, SECURITY-001–003, SESSION-001–002, LOCATION-001, CART-001, ADDRESS-001, SUPPORT-001, RELEASE-001, MEDIA-001–002, UX-001–002, AVAILABILITY-001, DELIVERY-PRIVACY-001, DELIVERY-COMPLETION-001–002, DELIVERY-PROOF-001, MERCHANT-FULFILMENT-001 |
| Safe resume point | `docs/launch/15_SESSION_HANDOFF.md`; do not deploy without explicit authorization |
