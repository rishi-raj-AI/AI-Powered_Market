# Launch status

Updated: 2026-09-29T17:23:27Z
Verified baseline: `origin/main` = protected local main = `522861c019d71dc78d214149d322d2c6cf2ca245`

| Field | Status |
|---|---|
| Active worktree / branch | `gaonone-launch-address-save-resilience` / `feat/launch-address-save-resilience` |
| Active PR | #190 — address-save resilience; awaiting the required four-gate CI run |
| Current phase | Phase 3 — customer-path functional and UX validation (`IN_PROGRESS`) |
| Objective | Validate and close launch-critical customer-path gaps from authenticated profile through support, without deployment or broad redesign |
| Completed | Phase 1 merged as `b730bba`; Phase 2A merged as `39ee103`; Phase 2B merged as `78983ba`; Phase 3 checkout/session reliability merged as `09e0e5c`; Phase 3 checkout idempotency merged as `dc76d50`; Phase 3 live-tracking session boundary merged as `2432dc6`; Phase 3 account-session safe return merged as `5fffca1`; Phase 3 location-state resilience merged as `dff5dc6`; Phase 3 cart-state resilience merged as `522861c`; release workflow is manual-dispatch only; Firebase identity/session/SMS and both Google clients are on main |
| In progress | The address-save slice serializes one address form submission through serviceability verification, address creation, and reload. It disables conflicting controls, renders the confirmed address before reload, and proves a forced second submit cannot start a second serviceability or create request; a post-save refresh failure leaves the confirmed address visible. `npm run build`, the 20-check focused pricing suite, and the full 304-check local browser suite pass; independent GitHub CI remains required |
| Blocked | Docker is unavailable for local backend integration tests; owner Firebase configuration, device acceptance, and visual evidence remain release dependencies; none block this source/test PR |
| Next exact action | Require all four CI gates on PR #190's final head, conduct the focused review, and only then merge; do not deploy |
| CI baseline | All four required checks passed for Phase 2A final head `ecfeb54`; Phase 2B final head `d8cb6fa`; Phase 3 PR #184 final head `3f749a6`; Phase 3 PR #185 final head `fd5afb3`; Phase 3 PR #186 final head `77065fe`; Phase 3 PR #187 final head `cbf6b20`; Phase 3 PR #188 final head `e83e88b`; and Phase 3 PR #189 final head `e96327f` before merge |
| P0 blockers | Firebase owner configuration and device acceptance; protected-main preservation |
| Owner dependencies | Firebase project/server credentials, OAuth origins, Android/iOS config/signing, domains/CORS; payment/maps decisions |
| Deferred | Product-media B2+, R2/scanner, banner enhancement, MSG91/DLT activation, scheduled fulfilment, pickup expansion, nonessential refactors/AI/cosmetic redesign |
| Latest decisions | AUTH-001–010, CHECKOUT-001, SESSION-001–002, LOCATION-001, CART-001, ADDRESS-001, RELEASE-001, MEDIA-001–002, UX-001–002 |
| Safe resume point | `docs/launch/15_SESSION_HANDOFF.md`; do not merge or deploy without a superseding authorization |
