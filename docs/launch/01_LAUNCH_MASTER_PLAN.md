# Launch master plan

Goal: a secure, delivery-first GaonOne MVP for low-bandwidth rural/semi-urban India. No passenger mobility scope.

## Gates

| Gate | Exit criteria | State |
|---|---|---|
| A — repository/release control | Baseline recorded, work isolated, protected edits preserved, deployment requires explicit authorization | DONE |
| B — authentication | Firebase verification and identity mapping, GaonOne sessions, web/Flutter Google Sign-In, SMS disabled fail-closed | DONE — owner runtime/device configuration remains a release gate |
| C — customer | Sign-in through support journey, authoritative quote, COD, order/tracking/proof | IN_PROGRESS |
| D — operations | Merchant, delivery, admin/support critical paths and server authorization | IN_PROGRESS — merchant availability, rider privacy, UPI fulfilment, Flutter completion, proof limits, web handoff acceptance, dependency-security remediation, merchant order-transition recovery, and admin capability/recovery remediation are merged. PR #210 closed the capability-affordance and destructive-return P1 after all required gates passed; backend authority remains unchanged. |
| E — UX | Responsive/accessibility/loading/error/empty/retry and Android visual evidence | IN_PROGRESS — bounded web handoff, admin-operations, support, admin-observability, and customer-purchase evidence are recorded. Gate E PR #212 corrected privileged recovery controls, queue status, and destructive-confirmation focus/visibility; PR #213 corrected undersized support controls, including WebKit native selectors; PR #214 corrected admin-observability refresh controls and misleading initial/error/empty rendering; PR #215 merged the cart/checkout truthful startup/recovery state and touch-target remedy. The active isolated customer-account slice covers `/account`, `/account/addresses`, and `/account/devices`; other customer/admin states and Android field-device acceptance remain. |
| F — release | Required checks, config audit, owner setup, explicit release authorization | NOT_STARTED |

## Dependency-ordered target week

1. Control plane, release-control remediation design, Firebase design.
2. Backend Firebase identity/session work; SMS deactivation/configuration and CI correction.
3. Web and Flutter Google Sign-In.
4. Customer-path functional and UX validation.
5. Merchant, delivery, admin, and support critical paths.
6. E2E, authorization/security, accessibility, connectivity/retry, visual QA, release configuration.
7. Release candidate, full validation, owner setup, blocker fixes, controlled release decision.

Calendar targets never convert incomplete work into `DONE`. Product-media B2+ and broad redesign are excluded unless formally reclassified.
