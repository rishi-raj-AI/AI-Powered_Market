# Recovered foundations — bounded comparison acceptance

Scope: Engineering's read-only comparison of recovered `ae36c301` against integrated main `84f4865`, including the preserved original three deltas: `web/app/design-tokens.css`, `web/components/ui/FormField.tsx`, `web/e2e/foundations.spec.ts`. These identities come from the task handoff; availability/content must be confirmed during comparison. No assumption that recovery is integrated, unchanged, or validated against current main.

This is written acceptance guidance only. No Figma call, redesign, application edit, dependency addition or broad review requested. Engineering owns source comparison and evidence; Git owns recovery/integration. Visual QA remains blocked.

| ID | Bounded criterion | Evidence / disposition expected |
|---|---|---|
| FND-01 | Reconcile recovered committed files and the three preserved deltas separately | File-by-file retain/adapt/omit/conflict inventory. Preserve current support/governance fixes; do not replay a broad old checkout over main. Missing delta is explicitly unavailable, never silently recreated as recovered evidence. |
| FND-02 | Existing semantic token identities and alias values retained | Compare against saved design specification; no replacement palette or parallel system. Existing legacy aliases remain compatible. Warning #765000 and legacy --warn #9A6700 are not interchangeable. Record genuine conflicts; no token redesign. |
| FND-03 | Minimum interactive dimensions and focus reuse existing tokens |48px targets; main action min-height56px where existing contract applies. Preserve2px focus ring and2px separation with existing focus/stroke/surface semantics. No arbitrary new colors, spacing or radii. |
| FND-04 | Field label, required, help and error semantics remain valid | Unique id/htmlFor; native required, disabled and readOnly preserved. aria-describedby references actually rendered nodes and preserves caller context. Explicit error sets invalid; no-error state preserves caller invalid value. No dangling help id when busy without loadingMessage. |
| FND-05 | Field busy/error/value behavior is deterministic | Typed value not replaced by loading copy; applicable busy semantics; explicit loading message separate from value. Existing error/help precedence documented and tested. Loading alone must not remove all useful description without replacement. |
| FND-06 | Button maintains meaningful loading and native interaction behavior | Existing intents only; deterministic accessible text, duplicate suppression, keyboard behavior and disabled semantics. Do not require decorative selected variants for a submit button. Compare recovery's actual loading contract, not unverified Figma appearance. |
| FND-07 | Focus and reflow are functional, not claimed visual equivalence | Keyboard focus remains identifiable; no component-level clipping; text grows at320/360/390 and200% text for EN/HI/MR fixtures. Essential labels/errors not truncated. Ancestor/layout checks bounded to affected specimens; Figma font fidelity remains unverified. |
| FND-08 | Flutter theme/primitives reuse existing Material architecture | Compare palette, ColorScheme/theme extension and TextTheme mappings; seed generation alone is not exact token equivalence. Preserve system text scaling, disabled/focus semantics,48px logical targets and Devanagari-safe line metrics. No new font/provider/package choice. If a proposed primitive is absent, report absent instead of inventing it. |
| FND-09 | Non-foundation behavior in ae36c301 is separated | Checkout quote, localization, navigation and delivery changes require their own compatibility disposition; do not call all24 historical files styling. Server delivery_fee remains authoritative; no ₹20 constant policy, locality-as-doorstep claim, auth or financial-rule regression. |
| FND-10 | Evidence stays attached to the actual compared candidate | Previous tests are historical, not current recovery proof. For read-only comparison list required narrow regressions and conflicts; do not claim tests executed. If implementation is later authorized, run relevant TypeScript/build/component/browser and Flutter analysis/tests for changed surfaces, with candidate identity. Existing broken lint command is a tooling limitation, not a passed check. |

## Requested Engineering return

Provide: compared identities; recovered-file and three-delta availability; retain/adapt/omit/conflict decisions; concrete semantic defects; whether any non-foundation behavior would regress current main; narrow validation needed after approved changes. No broad new review or visual redesign is required.

If source is compatible, say **foundation implementation candidate suitable for scoped integration review**, not “Figma approved.” If conflicts remain, name exact files/behavior. Shared IconButton or other unimplemented designs remain deferred unless already present and within the recovered scope. No new screens are authorized by this checklist.

Written criteria delivered. Recovery/source verification: Engineering pending. Visual QA: NOT RUN / BLOCKED. Deployment approval: none.

## Web-only candidate disposition — Master Control acceptance

Master Control reports source-review acceptance of the isolated seven-file web foundation candidate based on `84f4865`. Authorized scope: semantic tokens and layout import; Button, Feedback, preserved FormField and PriceBreakdown primitives; associated tests. No screen migration, checkout behavior, localization rollout or Flutter changes are included. Source recovery remains untouched.

Engineering reports local build PASS, focused36 tests PASS and full236 tests PASS. These are attributed execution results, not rerun by Design. The focused evidence concerns server-rendered component specimens, native browser behavior and reflow. It does **not** establish hydrated React consumer integration, asynchronous state transitions in real screens, app-wide component adoption, complete accessibility, localization readiness or Figma visual equivalence. Aggregate counts are not a blanket pass for every FND criterion.

| Acceptance layer | Disposition |
|---|---|
| Seven-file web primitive scope | Accepted by Master after source review |
| Local build / focused / full tests | Engineering-reported PASS /36 /236 |
| Actual hydrated consumers and screen migration | Not included; no acceptance claimed |
| App-wide accessibility/localization | Not established by primitive specimen checks |
| Flutter foundations | Deferred; not part of candidate |
| Git publication / exact-candidate CI | Assigned to Git; results not supplied in this handoff |
| Merge / deployment | Not confirmed |
| Visual Figma QA | NOT RUN / BLOCKED |

This limited candidate disposition supersedes the pending-review status for the authorized web primitives only. Historical recovery criteria and separate non-foundation behavior remain outside its acceptance. No broad review loop, repository edits or Figma calls were performed for this documentation update.
