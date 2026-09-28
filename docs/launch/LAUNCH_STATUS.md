# Launch status

Updated: 2026-09-28T15:53:22Z
Verified baseline: `origin/main` = protected local main = `78983ba1327d6d2e2584dbc2d2fc9e87f51bab30`

| Field | Status |
|---|---|
| Active worktree / branch | `gaonone-launch-customer-journey` / `feat/launch-customer-journey` |
| Active PR | None — Phase 3 customer journey work has started from merged main |
| Current phase | Phase 3 — customer-path functional and UX validation (`IN_PROGRESS`) |
| Objective | Validate and close launch-critical customer-path gaps from authenticated profile through support, without deployment or broad redesign |
| Completed | Phase 1 merged as `b730bba`; Phase 2A merged as `39ee103`; Phase 2B merged as `78983ba`; release workflow is manual-dispatch only; Firebase identity/session/SMS and both Google clients are on main |
| In progress | Customer journey audit found and fixed stale checkout-quote rendering across address changes; provider-neutral session restoration is covered by the full local browser suite (260 passing checks) |
| Blocked | Docker is unavailable for local backend integration tests; owner Firebase configuration, device acceptance, and visual evidence remain release dependencies; none block this source/test PR |
| Next exact action | Commit the customer checkout/session reliability slice, open a PR, and require all four CI gates; do not deploy |
| CI baseline | All four required checks passed for Phase 2A final head `ecfeb54`; all four passed for Phase 2B final head `d8cb6fa` before merge |
| P0 blockers | Firebase owner configuration and device acceptance; protected-main preservation |
| Owner dependencies | Firebase project/server credentials, OAuth origins, Android/iOS config/signing, domains/CORS; payment/maps decisions |
| Deferred | Product-media B2+, R2/scanner, banner enhancement, MSG91/DLT activation, scheduled fulfilment, pickup expansion, nonessential refactors/AI/cosmetic redesign |
| Latest decisions | AUTH-001–010, RELEASE-001, MEDIA-001–002, UX-001–002 |
| Safe resume point | `docs/launch/15_SESSION_HANDOFF.md`; do not merge or deploy without a superseding authorization |
