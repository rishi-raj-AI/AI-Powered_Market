# Session handoff

## Objective

Phase 2B: integrate web and Flutter Google Sign-In with the merged Firebase-to-GaonOne session exchange contract.

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

## Changed files

Phase 2B changes are limited to web/Flutter Google/Firebase client adapters, public configuration validation, tests, and launch-control documents. No backend authorization contract, Google profile linking, product redesign, deployment, or provider credentials are added.

Phase 3 begins with a narrow customer checkout/session reliability slice. It invalidates an older quote as soon as the selected delivery address changes, applies only the response for the current address, and proves the case across Chromium, Firefox, WebKit, and mobile Chrome. It also verifies that a rejected cart mutation clears the GaonOne session and returns to the Google-capable login page with the storefront preserved as a safe `next` destination.

## Validation

Phase 2A final head passed all four required GitHub CI gates. Phase 2B was fully validated in CI before merge. Phase 3 local validation passed `npm run build` and the full 260-check Playwright suite across Chromium, Firefox, WebKit, and mobile Chrome; `make test-backend` remains unavailable only because the local Docker daemon is absent. Required GitHub CI remains the independent backend, Android, web/UI, and compose/image gate after PR creation. Device sign-in and visual QA remain owner-dependent evidence.

## Unresolved / owner input

Firebase project/server credentials; OAuth origins; Android/iOS configuration and signing; domains/CORS; explicit phone-account linking design; visual QA; maps and Razorpay launch decisions.

## Next task

Phase 3 is the next approved launch phase: customer-path functional and UX validation from authenticated profile through address/location, discovery, cart, authoritative quote, COD/available payment, order, tracking/proof, and support. The initial source/test audit is complete and the checkout quote/session reliability slice is ready to commit. `npm run build` and all 260 local browser checks passed; `make test-backend` could not run because the local Docker daemon is unavailable. Commit, open a PR, require all four gates, then continue the customer journey audit. Do not deploy.

## Preservation contract

Never clean/reset/stash the protected main checkout or risky existing worktrees. Preserve the product-media B2 worktree. The protected checkout has exactly seven owner-owned Flutter/iOS modifications; preserve them byte-for-byte during every main update.
