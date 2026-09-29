# Launch status

Updated: 2026-09-29T08:01:47Z
Verified baseline: `origin/main` = protected local main = `5fffca1f7349f9d9caca3b659749fb72ca3a66e6`

| Field | Status |
|---|---|
| Active worktree / branch | `gaonone-launch-customer-location-resilience` / `feat/launch-customer-location-resilience` |
| Active PR | #188 — location-state resilience; awaiting the required four-gate CI run on a narrow E2E synchronization remediation |
| Current phase | Phase 3 — customer-path functional and UX validation (`IN_PROGRESS`) |
| Objective | Validate and close launch-critical customer-path gaps from authenticated profile through support, without deployment or broad redesign |
| Completed | Phase 1 merged as `b730bba`; Phase 2A merged as `39ee103`; Phase 2B merged as `78983ba`; Phase 3 checkout/session reliability merged as `09e0e5c`; Phase 3 checkout idempotency merged as `dc76d50`; Phase 3 live-tracking session boundary merged as `2432dc6`; Phase 3 account-session safe return merged as `5fffca1`; release workflow is manual-dispatch only; Firebase identity/session/SMS and both Google clients are on main |
| In progress | PR #188 makes the mounted marketplace react to its current location query and rejects stale autocomplete, selected-place, delivery-location, and nearby-discovery responses. Its narrow E2E synchronization remediation passes `npm run build` and the full 296-check local browser suite; the final GitHub CI run remains required |
| Blocked | Docker is unavailable for local backend integration tests; owner Firebase configuration, device acceptance, and visual evidence remain release dependencies; none block this source/test PR |
| Next exact action | Push the narrow E2E synchronization remediation to PR #188 and require all four CI gates on its new head; do not deploy |
| CI baseline | All four required checks passed for Phase 2A final head `ecfeb54`; Phase 2B final head `d8cb6fa`; Phase 3 PR #184 final head `3f749a6`; Phase 3 PR #185 final head `fd5afb3`; Phase 3 PR #186 final head `77065fe`; and Phase 3 PR #187 final head `cbf6b20` before merge. PR #188's initial head passed backend, Android, and compose/image gates; build/UI exposed test synchronization failures, so its updated head requires a complete fresh gate set |
| P0 blockers | Firebase owner configuration and device acceptance; protected-main preservation |
| Owner dependencies | Firebase project/server credentials, OAuth origins, Android/iOS config/signing, domains/CORS; payment/maps decisions |
| Deferred | Product-media B2+, R2/scanner, banner enhancement, MSG91/DLT activation, scheduled fulfilment, pickup expansion, nonessential refactors/AI/cosmetic redesign |
| Latest decisions | AUTH-001–010, CHECKOUT-001, SESSION-001–002, LOCATION-001, RELEASE-001, MEDIA-001–002, UX-001–002 |
| Safe resume point | `docs/launch/15_SESSION_HANDOFF.md`; do not merge or deploy without a superseding authorization |
