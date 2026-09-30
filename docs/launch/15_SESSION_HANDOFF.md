# Session handoff

## Objective

Phase 3: validate and close launch-critical customer-path reliability gaps from sign-in through support.

## Completed

- Merged Phase 1 PR #181 with merge commit `b730bbaef995bde31062459eff5bde54666cfc7c`; all four required checks passed before merge.
- Safely fast-forwarded protected local main to that SHA; its exact seven known owner modifications remain intact.
- Created isolated `/Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/gaonone-launch-auth-foundation` on `feat/launch-auth-foundation` from the merged main.
- Changed the staging workflow to `workflow_dispatch` only; no deployment ran.
- Added the additive `external_identities` model/migration, Firebase token verifier boundary, `/auth/firebase/exchange`, and GaonOne session issuance.
- Set production example/CI to Firebase with `SMS_AUTH_ENABLED=false`; SMS send/verify and MSG91 widget routes return 404 when SMS is disabled. Legacy SMS code remains.
- First Firebase login creates a customer with no phone and a UID identity record; repeat login reuses it. No automatic email matching/linking occurs.
- Merged Phase 2A PR #182 at `39ee1038e2c6c5818fbbbeebd251cbccf185a122` after all four required gates passed on final PR head `ecfeb54db388b1cd4a36630804c3a7f619477a17`.
- Safely fast-forwarded protected local main to that merge SHA; all seven owner-owned Flutter/iOS modifications remained byte-for-byte intact.
- Created isolated `/Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/gaonone-launch-google-signin` on `feat/launch-google-signin` from the merged main.
- Merged Phase 2B PR #183 at `78983ba1327d6d2e2584dbc2d2fc9e87f51bab30` after all four required gates passed on final PR head `d8cb6fa0c5957728e7d26eb5cb4d190a1e1f7bc3`.
- Performed a focused review of the Firebase/GaonOne session boundary, server-authoritative authorization, client logout/failure handling, configuration boundary, and committed-secret risk. No unresolved P0/P1 implementation issue was found.
- Safely fast-forwarded protected local main to `78983ba`; all seven owner-owned Flutter/iOS modifications remained byte-for-byte intact and no deployment ran.
- Created isolated `/Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/gaonone-launch-customer-journey` on `feat/launch-customer-journey` from that merged main.
- Merged Phase 3 PR #184 at `09e0e5cfa15f02226fa1d841d06db908706c16ac` after all four required gates passed on final PR head `3f749a634a31e2bf2f46ad56dc0993bf06a489b1`.
- PR #184 prevents an outdated address quote from rendering, preserves a safe provider-neutral login return after session expiry, and proves the client clears its GaonOne token before redirecting.
- Safely fast-forwarded protected local main to `09e0e5c`; its seven owner-owned Flutter/iOS modifications remained byte-for-byte intact and no deployment ran.
- Created isolated `/Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/gaonone-launch-customer-acceptance` on `feat/launch-customer-acceptance` from that merged main.
- Merged Phase 3 PR #185 at `dc76d5081c58691583eddebeaf45befd9bb8b867` after all four required gates passed on final PR head `fd5afb305a764b7dc14d9f4da3f036871218ed20`.
- PR #185 supplies one stable idempotency key for an unchanged web cart/address/payment attempt and reuses it after an uncertain network failure; backend user-scoped concurrency/idempotency behavior remains authoritative.
- Safely fast-forwarded protected local main to `dc76d50`; its seven owner-owned Flutter/iOS modifications remained byte-for-byte intact and no deployment ran.
- Created isolated `/Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/gaonone-launch-customer-session-resilience` on `feat/launch-customer-session-resilience` from that merged main.
- Merged Phase 3 PR #186 at `2432dc6a79a9af591117be567cd1182a6add623d` after all four required gates passed on final PR head `77065feeb0fd757a0cfbe748b5a5dd5e7cedbc02`.
- PR #186 routes customer live-tracking and route polling through the established GaonOne API boundary, so a tracking 401 clears the stale token and preserves a safe return to sign-in.
- Safely fast-forwarded protected local main to `2432dc6`; its seven owner-owned Flutter/iOS modifications remained byte-for-byte intact and no deployment ran.
- Created isolated `/Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/gaonone-launch-customer-state-recovery` on `feat/launch-customer-state-recovery` from that merged main.
- Merged Phase 3 PR #187 at `5fffca1f7349f9d9caca3b659749fb72ca3a66e6` after all four required gates passed on final PR head `cbf6b20f66d7d0581ade491afb9df38c17da8eae`.
- PR #187 preserves the account return destination chosen by the shared GaonOne session-expiry handler while retaining direct sign-in for a visitor who arrived without a session.
- Safely fast-forwarded protected local main to `5fffca1`; its seven owner-owned Flutter/iOS modifications remained byte-for-byte intact and no deployment ran.
- Created isolated `/Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/gaonone-launch-customer-location-resilience` on `feat/launch-customer-location-resilience` from that merged main.
- Merged Phase 3 PR #188 at `dff5dc6be9f46277bdeff5aaaa6ecdc1c9a207ba` after all four required gates passed on final PR head `e83e88bc43c10c814e520fda44a640ed917ac782`.
- PR #188 makes mounted marketplace location state follow the current query and rejects superseded autocomplete, selected-place, delivery-location, and nearby-discovery responses.
- Safely fast-forwarded protected local main to `dff5dc6`; its seven owner-owned Flutter/iOS modifications remained byte-for-byte intact and no deployment ran.
- Created isolated `/Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/gaonone-launch-cart-state-resilience` on `feat/launch-cart-state-resilience` from that merged main.
- Merged Phase 3 PR #189 at `522861c019d71dc78d214149d322d2c6cf2ca245` after all four required gates passed on final PR head `e96327f98ec1657a17313de3d7a8e2a9094925a0`.
- PR #189 serializes web cart mutations and renders the backend mutation result directly, so a slow overlapping quantity/clear action cannot replace the authoritative cart.
- Safely fast-forwarded protected local main to `522861c`; its seven owner-owned Flutter/iOS modifications remained byte-for-byte intact and no deployment ran.
- Created isolated `/Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/gaonone-launch-address-save-resilience` on `feat/launch-address-save-resilience` from that merged main.
- Merged Phase 3 PR #190 at `d5b3d3ccd33c62e0f047325d6f59ce62755600a4` after all four required gates passed on final PR head `0e76a9985b5bb70a0b835f40c5408807d6951dc8`.
- PR #190 serializes a web address save through serviceability, creation, and reload; a forced duplicate submit cannot start another request, and a confirmed address remains visible after its refresh fails.
- Safely fast-forwarded protected local main to `d5b3d3c`; its seven owner-owned Flutter/iOS modifications remained byte-for-byte intact, no extra local modifications appeared, and no deployment ran.
- Created isolated `/Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/gaonone-launch-support-ticket-resilience` on `feat/launch-support-ticket-resilience` from that merged main.
- Opened Phase 3 PR #191 for the support-ticket resilience slice. Its required gates must be evaluated only after the final intended branch head is pushed.

## Changed files

Phase 2B changes are limited to web/Flutter Google/Firebase client adapters, public configuration validation, tests, and launch-control documents. No backend authorization contract, Google profile linking, product redesign, deployment, or provider credentials are added.

Phase 3 first delivered a narrow customer checkout/session reliability slice. It invalidates an older quote as soon as the selected delivery address changes, applies only the response for the current address, and proves the case across Chromium, Firefox, WebKit, and mobile Chrome. It also verifies that a rejected cart mutation clears the GaonOne session and returns to the Google-capable login page with the storefront preserved as a safe `next` destination. PR #185 uses the backend's `Idempotency-Key` contract so an uncertain web checkout can retry the same logical cart/address/payment attempt safely. PR #186 routes live-tracking and route polling through the established client API boundary so a 401 cannot leave a stale token. PR #187 preserves the account bootstrap return selected by the shared expiry handler. PR #188 makes the mounted marketplace use its current location query and prevents delayed autocomplete, selected-place, delivery-location, and nearby-discovery results from overriding newer customer intent. PR #189 serializes client cart mutations and renders the backend response directly. PR #190 adds a synchronous in-flight guard before address serviceability, keeps conflicting address controls unavailable through create/reload, renders the confirmed address before reload, and proves that a forced duplicate submit cannot start another serviceability or create request. Backend serviceability, address ownership, pricing, inventory, and authorization remain authoritative. The active support slice adds additive, nullable ticket idempotency keyed by user; it replays an identical request, rejects mismatched replay payloads, safely resolves the concurrent insert race, and keeps a customer-created ticket visible before a failed list refresh. It also serializes customer replies while retaining the existing message idempotency boundary. It does not persist a ticket retry key across a full client restart; that requires a separately designed persistence contract.

PR #188's initial web/UI CI run exposed two test synchronization races, not an application behavior regression: new location checks could type before the authenticated client had hydrated, and the existing session-clear assertion could evaluate during the redirect teardown. The narrow remediation waits for the authenticated control before those location interactions and polls the cleared session value through redirect teardown. It changes no production behavior and passed all four required GitHub gates on the final head before merge.

## Validation

Phase 2A final head passed all four required GitHub CI gates. Phase 2B was fully validated in CI before merge. Phase 3 PR #184 passed the full required CI set before merge; its local validation passed `npm run build` and the full 260-check Playwright suite across Chromium, Firefox, WebKit, and mobile Chrome. Phase 3 PR #185 passed all four required gates; its local validation passed `npm run build` and the full 264-check Playwright suite across the same targets. Phase 3 PR #186 passed all four required gates; its local validation passed `npm run build` and the full 268-check Playwright suite. Phase 3 PR #187 passed all four required gates; its local validation passed `npm run build` and the full 276-check Playwright suite. Phase 3 PR #188 passed all four required gates; its local validation passed `npm run build` and the full 296-check Playwright suite. Phase 3 PR #189 passed all four required gates; its local validation passed `npm run build` and the full 300-check Playwright suite. Phase 3 PR #190 passed all four required gates; its local validation passed `npm run build`, the 20-check focused pricing suite, and the full 304-check Playwright suite. The current support slice passes Python compilation, focused Ruff, the migration-head check, `npm run build -- --webpack`, the 72-check focused support suite, and the full 312-check Playwright suite locally. The standard local Turbopack build was blocked by host disk exhaustion while writing its cache; this is an environment failure, not a source failure. `make test-backend` remains unavailable only because the local Docker daemon is absent. Required GitHub CI remains the independent backend, Android, web/UI, and compose/image gate after PR creation. Device sign-in and visual QA remain owner-dependent evidence.

## Unresolved / owner input

Firebase project/server credentials; OAuth origins; Android/iOS configuration and signing; domains/CORS; explicit phone-account linking design; visual QA; maps and Razorpay launch decisions.

## Next task

Phase 3 remains the approved launch phase: customer-path functional and UX validation from authenticated profile through address/location, discovery, cart, authoritative quote, COD/available payment, order, tracking/proof, and support. PR #191 contains the support-ticket resilience slice. After its final intended branch head is pushed, require all four gates on that exact head, review the nullable migration, user/key replay boundary, concurrent-insert recovery, ownership preservation, client retry key, and forced-duplicate tests before merge. Do not deploy.

## Preservation contract

Never clean/reset/stash the protected main checkout or risky existing worktrees. Preserve the product-media B2 worktree. The protected checkout has exactly seven owner-owned Flutter/iOS modifications; preserve them byte-for-byte during every main update.
