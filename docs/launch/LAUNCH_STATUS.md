# Launch status

Updated: 2026-09-30T17:21:15Z
Verified baseline: `origin/main` = protected local main = `5df82a2fdf17c3b394f63d9e5a98c36575b6cb2d`

| Field | Status |
|---|---|
| Active worktree / branch | `gaonone-launch-checkout-payment-availability` / `feat/launch-checkout-payment-availability` |
| Active PR | #194 — initial UPI checkout payment-availability recovery; all four required CI gates must be evaluated only on its final branch head |
| Current phase | Phase 3 — customer-path functional and UX validation (`IN_PROGRESS`) |
| Objective | Validate and close launch-critical customer-path gaps from authenticated profile through support, without deployment or broad redesign |
| Completed | Phase 1 merged as `b730bba`; Phase 2A merged as `39ee103`; Phase 2B merged as `78983ba`; Phase 3 checkout/session reliability merged as `09e0e5c`; Phase 3 checkout idempotency merged as `dc76d50`; Phase 3 live-tracking session boundary merged as `2432dc6`; Phase 3 account-session safe return merged as `5fffca1`; Phase 3 location-state resilience merged as `dff5dc6`; Phase 3 cart-state resilience merged as `522861c`; Phase 3 address-save resilience merged as `d5b3d3c`; Phase 3 support-ticket resilience merged as `98955ae`; Phase 3 payment-intent resilience merged as `524b1d1`; Phase 3 existing-pending-UPI availability recovery merged as `5df82a2`; release workflow is manual-dispatch only; Firebase identity/session/SMS and both Google clients are on main |
| In progress | Only after a successful UPI checkout, the initial `paymentIntent` HTTP `503` is handed to the existing provider-neutral pending-order recovery path; checkout failures, other intent errors, backend ownership, payment state, roles, and availability authority remain unchanged. The 24 focused cross-browser test cases completed successfully; the runner could not persist generated reporting output because this host reached `ENOSPC`. Webpack compilation, type checking, and static-page generation completed before final packaging likewise hit host `ENOSPC`. Required GitHub CI remains the independent gate. |
| Blocked | Docker is unavailable for local backend integration tests; owner Firebase configuration, device acceptance, and visual evidence remain release dependencies; none block this source/test PR |
| Next exact action | Verify all four CI gates on PR #194's exact final head and conduct focused review before any merge; do not deploy |
| CI baseline | All four required checks passed for Phase 2A final head `ecfeb54`; Phase 2B final head `d8cb6fa`; Phase 3 PR #184 final head `3f749a6`; Phase 3 PR #185 final head `fd5afb3`; Phase 3 PR #186 final head `77065fe`; Phase 3 PR #187 final head `cbf6b20`; Phase 3 PR #188 final head `e83e88b`; Phase 3 PR #189 final head `e96327f`; Phase 3 PR #190 final head `0e76a99`; Phase 3 PR #191 final head `53df9f9`; Phase 3 PR #192 final head `1be6de7`; and Phase 3 PR #193 final head `7ee6e72` before merge |
| P0 blockers | Firebase owner configuration and device acceptance; protected-main preservation |
| Owner dependencies | Firebase project/server credentials, OAuth origins, Android/iOS config/signing, domains/CORS; payment/maps decisions |
| Deferred | Product-media B2+, R2/scanner, banner enhancement, MSG91/DLT activation, scheduled fulfilment, pickup expansion, nonessential refactors/AI/cosmetic redesign |
| Latest decisions | AUTH-001–010, CHECKOUT-001, PAYMENT-001–003, SESSION-001–002, LOCATION-001, CART-001, ADDRESS-001, SUPPORT-001, RELEASE-001, MEDIA-001–002, UX-001–002 |
| Safe resume point | `docs/launch/15_SESSION_HANDOFF.md`; do not deploy without explicit authorization |
