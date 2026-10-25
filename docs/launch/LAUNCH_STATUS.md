# Launch status

Updated: 2026-10-25
Verified baseline: `origin/main` = protected local main = `82a88a769f4191608631fbf9069d3587994516b1`; the exact seven owner-owned Flutter/iOS modifications remain intact.

| Field | Status |
|---|---|
| Active worktree / branch | `gaonone-launch-admin-operations-acceptance` / `test/admin-operations-acceptance` |
| Security PR | [#208](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/208) merged as `43b683e` after all four required gates passed on final head `911044c`. |
| Merchant-transition PR | [#209](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/209) merged as `82a88a7` after all four required gates passed on final head `a9e520c4cfe27e5bd35aa16530186f9f43a74337`. The scoped responsive remediation closed the initial P1 mobile merchant-console interaction defect. |
| Admin-operations PR | [#210](https://github.com/rishi-raj-AI/AI-Powered_Market/pull/210) is open from isolated `test/admin-operations-acceptance`. It derives privileged role/recovery affordances from backend capabilities, fails closed on discovery loss, requires explicit review before financial return, and renders server-derived recovery outcomes. Evaluate required CI only on its final exact head. |
| Current phase | Launch-critical actor acceptance (Phases 3–6; Gate D admin/support operations remediation in normal PR review/CI) |
| Objective | Validate and close launch-critical customer and operations gaps without deployment or broad redesign |
| Completed | Phase 1 merged as `b730bba`; Phase 2A as `39ee103`; Phase 2B as `78983ba`; customer reliability, checkout, delivery, and web handoff work through PR #204 as `45b4b28`; dependency-security PR #208 as `43b683e`; and merchant-transition recovery PR #209 as `82a88a7`. Release workflow is manual-dispatch only; Firebase identity/session/SMS and both Google clients are on main. |
| In progress | The smallest evidence-driven Gate D remediation: the normal admin dashboard no longer advertises role changes that only `admin.manage` can perform, and delivery recovery exposes reassign only with `rider.operations` and post-pickup return only with the additionally required financial capabilities. Capability errors fail closed; the backend remains authoritative. |
| Blocked | Database-backed regressions require CI on this host; local PostgreSQL driver/Docker and Android SDK are unavailable. Firebase setup, device acceptance, and visual evidence remain release dependencies. Independent source work continues. |
| Next exact action | Evaluate `backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images` only on PR #210's final exact head. Merge only if all pass and focused review remains clear. Do not deploy. |
| CI baseline | All four required checks passed for security PR #208 final head `911044c` and merchant-transition PR #209 final head `a9e520c`. The current isolated source passes clean `npm ci`, production webpack build, focused 28-case cross-browser recovery/a11y checks, full 456-case browser invocation (453 passed; 3 deliberate non-mobile skips of a mobile-only regression), Python compilation, focused Ruff, and `git diff --check`; database-backed regression remains a CI gate on this host. |
| P0 blockers | Firebase owner configuration and device acceptance remain release gates; protected-main preservation remains mandatory. R-023 and R-024 are mitigated. |
| Owner dependencies | Firebase project/server credentials, OAuth origins, Android/iOS config/signing, domains/CORS; payment/maps decisions |
| Deferred | Product-media B2+, R2/scanner, banner enhancement, MSG91/DLT activation, scheduled fulfilment, pickup expansion, nonessential refactors/AI/cosmetic redesign |
| Latest decisions | AUTH-001–011, CHECKOUT-001–002, PAYMENT-001–005, SECURITY-001–003, SESSION-001–002, LOCATION-001, CART-001, ADDRESS-001, SUPPORT-001, RELEASE-001, MEDIA-001–002, UX-001–002, AVAILABILITY-001, DELIVERY-PRIVACY-001, DELIVERY-COMPLETION-001–002, DELIVERY-PROOF-001, MERCHANT-FULFILMENT-001, ADMIN-OPERATIONS-001 |
| Safe resume point | `docs/launch/15_SESSION_HANDOFF.md`; do not deploy without explicit authorization |
