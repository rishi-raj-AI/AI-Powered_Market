# Admin operations web acceptance

Recorded 2026-10-25 UTC on `feat/launch-operations-followup`, rebased on merged main `bbcd9c310cc6946f6e99556c8bb825cec41433cd` before review.

## Scope and evidence boundary

This is browser-functional and inspected visual evidence for `/admin` and `/admin/delivery-recovery`, using synthetic elevated, normal, and missing-capability accounts plus mocked GaonOne API responses. It is not live Firebase, device, production, end-to-end backend, payment/settlement, or deployment evidence. No external provider, real customer data, credential, or deployment action was used.

The pre-remediation acceptance run demonstrated a real narrow-screen accessibility issue: the privileged surfaces rendered 40px Chromium/mobile-Chrome and 42px Firefox/WebKit controls, below the 44px touch target. Opening the post-pickup return review also left its confirm/cancel controls below the viewport and unannounced to keyboard focus. A separate status message continued to say that access was being checked while the already-authorized failed-delivery queue was loading. These findings did not weaken the existing backend capability, financial, audit, or transition boundary.

## Narrow remediation

- Scope the 44px minimum dimensions to controls within the two audited `.adminOperations` surfaces; no global redesign or role/capability change is made.
- Once `rider.operations` access is verified, render the distinct failed-delivery queue loading state rather than the access-check state.
- On an elevated operator's explicit Review action, focus and scroll the labelled consequence-review region into view. Cancel restores focus to that task's remounted Review control.
- Existing server authority remains intact: normal administrators retain only pre-pickup reassignment, while post-pickup return still requires `rider.operations`, `refund.write`, and `settlement.write`; the server performs the recovery, settlement/refund policy, locks, transition, and audit.

## Executed evidence

`npx playwright test e2e/admin-operations-acceptance.spec.ts --workers=2 --output=/tmp/gaonone-admin-operations-final-3`: **24 passed** across Chromium, Firefox, WebKit, and mobile Chrome.

At 320px, 390px, and 1280px, elevated dashboard and recovery cases assert serious/critical WCAG A/AA axe findings are absent within `main`, each rendered `button`/`select` is at least 44 by 44px, no document-level horizontal overflow occurs, the destructive review is focused and in view, and cancel returns focus to its original trigger. The same suite verifies normal-admin pre-pickup recovery without financial return, separate loading/queue-error/empty/retry states, and fail-closed behavior without recovery capability. Response barriers, rather than timing sleeps, control the queue states.

Chromium evidence command, from `web/`:

```sh
GAONONE_VISUAL_OUTPUT_DIR=../docs/launch/evidence/admin-operations npx playwright test e2e/admin-operations-acceptance.spec.ts --project=chromium --workers=2 --output=/tmp/gaonone-admin-operations-evidence
```

It passed all 6 Chromium cases. The inspected captures show controls, Hindi/Marathi fixture text, confirmation consequence text, and desktop/narrow layouts without document overflow. Existing dense operational tables remain inside their designed table containers; this is not a claim of device or complete visual acceptance.

## Inspected screenshots

- [Dashboard — 320px](evidence/admin-operations/admin-dashboard-320px-chromium.png)
- [Dashboard — 390px](evidence/admin-operations/admin-dashboard-390px-chromium.png)
- [Dashboard — 1280px](evidence/admin-operations/admin-dashboard-1280px-chromium.png)
- [Delivery recovery — 320px](evidence/admin-operations/admin-delivery-recovery-320px-chromium.png)
- [Delivery recovery — 390px](evidence/admin-operations/admin-delivery-recovery-390px-chromium.png)
- [Delivery recovery — 1280px](evidence/admin-operations/admin-delivery-recovery-1280px-chromium.png)

| Capture | SHA-256 |
|---|---|
| Dashboard 320px | `900266334f59966de216879e9d7b58507809ad0910ca761f62d751a8d8c13bee` |
| Dashboard 390px | `034124a534f9f3d927e98bedef79078ea47469a01fa347f010f0f7215e58927c` |
| Dashboard 1280px | `6fe39436ecede14ae30dbd6035ecf85bb6a631035fb1752b33f6ab025bf5e8fe` |
| Delivery recovery 320px | `bc2643b1ceeefc785d49c6009ccb0160a4b161760514eabbe93eaa41c95fbaef` |
| Delivery recovery 390px | `74c241a6b144abe840bdface7d0f850f8279a588c76eb0be9c8df8f8abfc8f92` |
| Delivery recovery 1280px | `fa1c7d6cca4cfd0b194cfd4e4ac05be08c4f00cd6e8c84c7ee368bc490d4c40f` |

| Source | SHA-256 |
|---|---|
| `web/app/admin/page.tsx` | `4bb39fc521dd797c1a119ce9e112939b62ad3446b5175988d5f8ea54cf20a26b` |
| `web/app/admin/delivery-recovery/page.tsx` | `7218fdd20ce846687118e4976e977a1727c233acfd16edc088654466278d5b47` |
| `web/app/globals.css` | `f90d3f1a1948225f17d445f0f9bde0f31104aefe0db57be19c2c4409f3244288` |
| `web/e2e/admin-operations-acceptance.spec.ts` | `b73245c1dd60f0621b8a111deba4974006a75ee21e722bb9f2b216ddac8bcf60` |

## Remaining gates

The production webpack build passed. A complete local browser invocation reached 475 passed and 3 existing deliberate non-mobile skips before two unrelated WebKit `page.goto` cases timed out immediately after the host's Next cache reported `No space left on device` (367MiB free); the new admin acceptance cases passed in all four browser targets. This is an environment-limited full-suite result, not a passing full-suite claim or a source remediation. PR #212 exact-final-head required CI and review remain mandatory before merge.

This does not complete Android/iOS device acceptance, Firebase owner setup, backend integration evidence, complete admin/support visual coverage, or release-candidate validation. No deployment is authorized.
