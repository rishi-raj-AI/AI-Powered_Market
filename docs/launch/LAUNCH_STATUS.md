# Launch status

Updated: 2026-10-24
Verified baseline: `origin/main` = protected local main = `43b683e255bc2cfc89c3f15689baeb98c31b6432`; the exact seven owner-owned Flutter/iOS modifications remain intact.

| Field | Status |
|---|---|
| Active worktree / branch | `gaonone-launch-merchant-transition-recovery` / `test/merchant-order-acceptance` |
| Security PR | [#208](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/208) merged as `43b683e` after all four required gates passed on final head `911044c`. |
| Merchant-transition PR | [#209](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/209) is open from `test/merchant-order-acceptance`. Its initial head `898b094ee304b09304305fc3a208b1fdec9b6e1f` exposed a P1 mobile merchant-console interaction defect; the responsive remediation requires a new exact final head and all four required gates before any merge. |
| Current phase | Launch-critical actor acceptance (Phases 3–6; Gate D merchant order-transition recovery active) |
| Objective | Validate and close launch-critical customer and operations gaps without deployment or broad redesign |
| Completed | Phase 1 merged as `b730bba`; Phase 2A as `39ee103`; Phase 2B as `78983ba`; customer reliability, checkout, delivery, and web handoff work through PR #204 as `45b4b28`; and dependency-security PR #208 as `43b683e`. Release workflow is manual-dispatch only; Firebase identity/session/SMS and both Google clients are on main. |
| In progress | Merchant order-transition recovery keeps `/merchant` and `/merchant/orders` server-authoritative, synchronously serializes forced duplicate actions, and reconciles uncertain responses without replay. Initial source validation on `171d01a` passed clean install, production audit (0 production vulnerabilities), production webpack build, 36 focused cross-browser cases, and 436 browser cases, but did not establish Linux mobile layout safety. Initial PR #209 head `898b094` passed three required gates and `build-and-ui` failed 6 of 436 browser cases (430 passed): visible primary-console mobile actions were intercepted by the responsive header/metadata. A narrow normal-flow, no-overlap remediation and mobile hit-target/overflow regression are locally validated; final-head CI remains required. |
| Blocked | Database-backed regressions require CI on this host; local PostgreSQL driver/Docker and Android SDK are unavailable. Firebase setup, device acceptance, and visual evidence remain release dependencies. Independent source work continues. |
| Next exact action | Commit and push the narrow responsive remediation, then evaluate all four required gates only on PR #209's new exact final head; merge only after green CI and no unresolved P0/P1; then safely fast-forward protected main while preserving its seven owner changes. Do not deploy. |
| CI baseline | All four required checks passed for security PR #208 final head `911044c`. PR #209 initial head `898b094` passed `backend-check`, `analyze-and-build-android`, and `production-compose-and-images`; `build-and-ui` failed on the Phase-209-caused mobile interaction defect. Those three green results do not transfer to the remediation head. |
| P0 blockers | Firebase owner configuration and device acceptance remain release gates; protected-main preservation remains mandatory. R-023 is mitigated; R-024 awaits final-head CI. |
| Owner dependencies | Firebase project/server credentials, OAuth origins, Android/iOS config/signing, domains/CORS; payment/maps decisions |
| Deferred | Product-media B2+, R2/scanner, banner enhancement, MSG91/DLT activation, scheduled fulfilment, pickup expansion, nonessential refactors/AI/cosmetic redesign |
| Latest decisions | AUTH-001–011, CHECKOUT-001–002, PAYMENT-001–005, SECURITY-001–003, SESSION-001–002, LOCATION-001, CART-001, ADDRESS-001, SUPPORT-001, RELEASE-001, MEDIA-001–002, UX-001–002, AVAILABILITY-001, DELIVERY-PRIVACY-001, DELIVERY-COMPLETION-001–002, DELIVERY-PROOF-001, MERCHANT-FULFILMENT-001 |
| Safe resume point | `docs/launch/15_SESSION_HANDOFF.md`; do not deploy without explicit authorization |
