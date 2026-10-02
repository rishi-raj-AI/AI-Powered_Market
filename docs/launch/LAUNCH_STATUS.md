# Launch status

Updated: 2026-10-02T15:21:46Z
Verified baseline: `origin/main` = protected local main = `6825f8895367aba43355755b4e990765e0e8c887`

| Field | Status |
|---|---|
| Active worktree / branch | `gaonone-launch-phase3-reliability-followup` / `feat/launch-phase3-reliability-followup` |
| Active PR | None — open only after focused review and this project-control update |
| Current phase | Phase 3 — customer-path functional and UX validation (`IN_PROGRESS`) |
| Objective | Validate and close launch-critical customer and operations gaps without deployment or broad redesign |
| Completed | Phase 1 merged as `b730bba`; Phase 2A merged as `39ee103`; Phase 2B merged as `78983ba`; Phase 3 checkout/session reliability merged as `09e0e5c`; Phase 3 checkout idempotency merged as `dc76d50`; Phase 3 live-tracking session boundary merged as `2432dc6`; Phase 3 account-session safe return merged as `5fffca1`; Phase 3 location-state resilience merged as `dff5dc6`; Phase 3 cart-state resilience merged as `522861c`; Phase 3 address-save resilience merged as `d5b3d3c`; Phase 3 support-ticket resilience merged as `98955ae`; Phase 3 payment-intent resilience merged as `524b1d1`; Phase 3 existing-pending-UPI availability recovery merged as `5df82a2`; Phase 3 initial-UPI-intent availability recovery merged as `8f37a04`; security PR #195 merged as `168a496`; security PR #196 merged as `2b5b124`; checkout duplicate-submit PR #197 merged as `30d420c`; signed-payment-confirmation PR #198 merged as `6825f8`; release workflow is manual-dispatch only; Firebase identity/session/SMS and both Google clients are on main |
| In progress | Gate D merchant availability remediation: platform suspension/reapproval preserves merchant-owned `Store.is_active`, while existing approved-merchant eligibility keeps public reads, checkout, and store/catalog mutations fail-closed. The admin active-store metric now counts only active stores of approved merchants. No migration, backfill, automatic reopen, payment/auth/role change, or deployment is included. |
| Blocked | Docker is unavailable for local database-backed integration tests; owner Firebase configuration, device acceptance, and visual evidence remain release dependencies; none block this source/test PR |
| Next exact action | Finish focused tests/review, then commit and open an isolated PR; evaluate `backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images` only on its exact final head. Do not deploy. |
| CI baseline | All four required checks passed for Phase 2A final head `ecfeb54`; Phase 2B final head `d8cb6fa`; Phase 3 PR #184 final head `3f749a6`; Phase 3 PR #185 final head `fd5afb3`; Phase 3 PR #186 final head `77065fe`; Phase 3 PR #187 final head `cbf6b20`; Phase 3 PR #188 final head `e83e88b`; Phase 3 PR #189 final head `e96327f`; Phase 3 PR #190 final head `0e76a99`; Phase 3 PR #191 final head `53df9f9`; Phase 3 PR #192 final head `1be6de7`; Phase 3 PR #193 final head `7ee6e72`; Phase 3 PR #194 final head `5b728de`; security PR #195 final head `bdbfbfb`; security PR #196 final head `9ba269a`; checkout duplicate-submit PR #197 final head `572169b`; and signed-payment-confirmation PR #198 final head `6c331ef` before merge |
| P0 blockers | Firebase owner configuration and device acceptance; protected-main preservation |
| Owner dependencies | Firebase project/server credentials, OAuth origins, Android/iOS config/signing, domains/CORS; payment/maps decisions |
| Deferred | Product-media B2+, R2/scanner, banner enhancement, MSG91/DLT activation, scheduled fulfilment, pickup expansion, nonessential refactors/AI/cosmetic redesign |
| Latest decisions | AUTH-001–010, CHECKOUT-001–002, PAYMENT-001–004, SECURITY-001–002, SESSION-001–002, LOCATION-001, CART-001, ADDRESS-001, SUPPORT-001, RELEASE-001, MEDIA-001–002, UX-001–002, AVAILABILITY-001 |
| Safe resume point | `docs/launch/15_SESSION_HANDOFF.md`; do not deploy without explicit authorization |
