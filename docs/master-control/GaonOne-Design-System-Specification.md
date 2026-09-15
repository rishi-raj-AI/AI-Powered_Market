# GaonOne — Design System Implementation Specification

Status: documentation for review; no implementation authorized. Prepared 10 September 2026.

## 1. Authority and saved design status

Figma is the visual source of truth; existing application behavior, authorization and API contracts are authoritative for functionality. This document specifies future implementation and does not itself approve code changes. No Figma calls or application edits were made while preparing it.

Saved file: [GaonOne — Product System](https://www.figma.com/design/fHmFfvFQXnh7WAFYAOSvMP). Design evidence is the last successful local session ledger, not a fresh inspection. Preserve all existing nodes and instances. The ledger contains an earlier inventory with the original page name; the completed-steps record and later saved page structure take precedence.

Exactly three pages:

- **Readme:** Product Principles; Design Decisions; Bharat UX Principles; Accessibility Standards; Localization Standards; Component Naming Convention; Figma → Code Rules; Approval Status.
- **Foundations:** A. Color Tokens; B. Typography; C. Spacing; D. Radius; E. Layout; F. Motion; G. Focus & Accessibility; H. Buttons; I. Inputs & Forms; J. Feedback States; K. Navigation; L. Commerce Components; M. Address Components; N. Order & Delivery Components; O. Component QA.
- **Future Work:** Customer; Merchant; Rider; Operations; Prototypes; Language QA; Developer Handoff; Deprecated.

Saved: 79 variables in four single-mode collections, 15 text styles, one focus effect style, A–G reference boards, `Action/Button` (23 variants, node 8:51), and `Form/Field` (7 variants, node 9:40). Typography was visually inspected in the earlier session. Button QA remains unresolved; Field creation was recorded but visual QA was not completed. Saved Button variants: Primary, Secondary and Destructive each have Default, Hover, Pressed, Focused, Disabled and Loading (18 total); Tertiary has Default, Hover, Pressed, Focused and Disabled (5). Saved Field variants: Default, Hover, Pressed, Focused, Disabled, Loading and Error (7). No additional variants are claimed saved. Remaining component sections and QA are placeholders, not completed components. No product screens are approved or created by this specification.

Repository snapshot: `5528f86224ba2cf2533d9f5632740286c2009a14`. Current web uses Next.js, React and plain CSS; there is no Tailwind mapping to introduce. Flutter uses Material 3 with a seed-based theme. Existing implementations below are reuse/extraction locations, not claims that matching reusable components already exist. All proposed reusable names and theme extensions remain uncreated.

## 2. Common implementation contract

These rules apply to every inventory entry below and are part of its accessibility, responsive and localization requirements.

- Interactive hit areas are at least 48×48 logical pixels; main actions use a 56px minimum height. Text wraps and increases height. Do not impose maximum text heights or truncate essential labels, prices, errors, addresses or payment status.
- Web uses semantic buttons, links, fields, lists and headings; native controls retain keyboard behavior. Flutter uses Material controls and explicit Semantics only where needed, avoiding duplicate announcements. Icon-only actions require localized accessible names. Focus order follows reading order.
- Keyboard focus is visible, unobscured and distinct from selected/error states. Dialogs restore focus; errors identify the field and recovery action. Status changes use restrained announcements; spinners are decorative alongside one meaningful busy announcement.
- Target accessible contrast: 4.5:1 ordinary text, 3:1 large text and meaningful control/focus boundaries. These are acceptance targets, not a conformance claim. Disabled controls need legible explanatory context even when contrast exemptions apply.
- Use auto layout with wrapping, hug-content text and fill-container fields in Figma; use flexible layout and minimum sizes in code. At 320px, 16px gutters leave 288px usable width. No body horizontal scrolling. A larger viewport does not justify smaller controls.
- English uses Inter where available; Hindi and Marathi use Noto Sans Devanagari with platform fallbacks. Body/labels 16/24, supporting 14/20, titles 20/28 and 24/32. Do not force struts or line boxes that clip glyphs. Font acquisition/bundling is a later decision, not permission to add dependencies.
- UI text comes from localization resources; never concatenate sentence fragments. Preserve user-entered names and addresses. Format INR using locale-aware formatting while keeping server decimal amounts authoritative. Accept compatible pasted input without silently changing API validation rules. Mark web language as en, hi or mr; provide equivalent app locale semantics.
- Separate interaction state from domain state: an order can be `preparing` while its refresh action is loading. Loading and offline never mean success. Preserve known content during refresh, identify stale information, and keep retry actions explicit. Do not implement a new offline mutation queue.
- A state is applicable only when the component has that behavior. Static cards do not need hover/loading variants merely to fill a matrix. Compose existing Button/Field/status components instead of multiplying full-card cosmetic variants.

## 3. Component inventory

**State shorthand:** `I` = default, hover on pointer devices, pressed, focused, disabled. `L` = loading only while a real operation is pending. `E` = error with an actionable explanation. `S` = selected/unselected for choice controls. Focus and error/selected/loading can coexist and must be demonstrated without generating every permutation as a cosmetic Figma variant. Required callbacks are UI adapters to existing operations, not new API fields.

All entries inherit section 2. Web and Flutter paths are current reuse locations; missing shared wrappers are explicitly future extraction work. Workspace/delivery specifications document existing contracts, but their role-specific design is deferred until the customer critical path is approved.

### 3.1. Action/Button

- **Purpose:** Submit or invoke one clear action.
- **Variants:** Primary, Secondary, Tertiary, Destructive; Loading and Disabled are states, not intents.
- **States:** I; L for asynchronous actions; errors shown through linked feedback.
- **Required properties/interface:** label, intent, onActivate, disabled, busy, loadingLabel; optional leadingIcon and describedBy.
- **Accessibility:** Native button; type explicit; busy announced once; suppress duplicate activation while retaining focus.
- **Responsive behavior:** Minimum 56px for main actions; wrap long labels; mobile primary fills available width.
- **Localization:** Separate action/loading strings; destructive action uses its actual verb.
- **Existing web location:** [web/app/globals.css](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/globals.css>); [web/app/checkout/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/checkout/page.tsx>)
- **Existing Flutter location:** [mobile/lib/main.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/main.dart>); [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>)
- **Saved status:** Saved set; fixes and visual QA required.

### 3.2. Form/Field

- **Purpose:** Shared labeled control shell and text input.
- **Variants:** Text; wrapper slots for specialized controls.
- **States:** I + L + E.
- **Required properties/interface:** id, label, value, onChange, name, required, disabled, help, errorMessage, placeholder; loadingMessage separately.
- **Accessibility:** Label association; describedBy help/error; invalid state; never placeholder-only.
- **Responsive behavior:** Fill width; control minimum48; help/error grow vertically.
- **Localization:** Preserve entered value across locale/state changes; no forced uppercase.
- **Existing web location:** [web/app/globals.css](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/globals.css>); [web/app/account/addresses/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/account/addresses/page.tsx>)
- **Existing Flutter location:** [mobile/lib/main.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/main.dart>); [mobile/lib/src/screens/account_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/account_screen.dart>)
- **Saved status:** Saved set; fixes and visual QA required.

### 3.3. Form/Search

- **Purpose:** Find stores, products or localities through existing search.
- **Variants:** Search with optional clear action.
- **States:** I + L + E; empty results is Feedback/Empty.
- **Required properties/interface:** query, label, onQueryChange, onClear, resultsStatus, busy.
- **Accessibility:** Search input semantics; label clear button; announce result count after update, not each keystroke.
- **Responsive behavior:** Full width on phone; clear action48; result panel fits viewport.
- **Localization:** Unicode queries and long village names; distinguish no results from failed request.
- **Existing web location:** [web/components/UniversalLocationSearch.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/components/UniversalLocationSearch.tsx>); [web/app/market/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/market/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/market_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/market_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.4. Form/Phone

- **Purpose:** Collect existing authentication or recipient phone number.
- **Variants:** Country prefix presentation appropriate to existing India contract.
- **States:** I + E; L during submit through parent action.
- **Required properties/interface:** label, phone, onChange, required, errorMessage, autocompletePurpose.
- **Accessibility:** Telephone keyboard and autocomplete; visible country code; errors explain expected format.
- **Responsive behavior:** One fluid field; prefix cannot steal typing width.
- **Localization:** Avoid numeric type that removes leading characters; normalize only as existing contract allows.
- **Existing web location:** [web/app/login/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/login/page.tsx>); [web/app/account/addresses/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/account/addresses/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/login_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/login_screen.dart>); [mobile/lib/src/screens/account_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/account_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.5. Form/Code

- **Purpose:** Enter authentication or delivery proof code.
- **Variants:** OTP/Code; single accessible input with optional visual grouping.
- **States:** I + E; L during verification.
- **Required properties/interface:** label, value, onChange, codeLength from flow, errorMessage, purpose.
- **Accessibility:** One logical input; paste/autofill support; no per-cell keyboard trap; proof OTP six digits.
- **Responsive behavior:** Full row at320 without six undersized touch targets.
- **Localization:** Numeric input purpose and localized instructions; do not translate actual code.
- **Existing web location:** [web/app/login/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/login/page.tsx>); [web/app/delivery/complete/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/delivery/complete/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/login_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/login_screen.dart>); [mobile/lib/src/screens/role_workspaces.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/role_workspaces.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.6. Form/Select

- **Purpose:** Choose a bounded option from existing data.
- **Variants:** Select; searchable choice composes Search where necessary.
- **States:** I + L + E + S.
- **Required properties/interface:** label, options with stable ids, selectedId, onSelect, required, busy.
- **Accessibility:** Native select where suitable; otherwise complete listbox/combobox semantics and keyboard support.
- **Responsive behavior:** Long option labels wrap in presented result; no clipped selected meaning.
- **Localization:** Display translated label while submitting unchanged id.
- **Existing web location:** [web/app/account/addresses/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/account/addresses/page.tsx>); [web/components/UniversalLocationSearch.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/components/UniversalLocationSearch.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/account_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/account_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.7. Form/Checkbox

- **Purpose:** Toggle an independent existing choice.
- **Variants:** Unchecked, Checked; mixed only if a real aggregate interaction exists.
- **States:** I + S; E for required choice.
- **Required properties/interface:** id, label, checked, onChange, disabled, errorMessage.
- **Accessibility:** Checkbox semantics; entire label target48; Space toggles.
- **Responsive behavior:** Label wraps beside control; whole row grows.
- **Localization:** Translate complete label, including consent meaning; no preselected new consent.
- **Existing web location:** [web/app/merchant/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/merchant/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/role_workspaces.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/role_workspaces.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.8. Form/Radio

- **Purpose:** Choose exactly one option in a group.
- **Variants:** Unselected, Selected.
- **States:** I + S + E.
- **Required properties/interface:** groupName, groupLabel, optionId, label, selected, onSelect.
- **Accessibility:** Radio group semantics; arrow keys on web; label target48.
- **Responsive behavior:** Stack choices on mobile; no truncation.
- **Localization:** Full translated labels; preserve stable values such as cod/upi.
- **Existing web location:** [web/app/checkout/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/checkout/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.9. Form/Textarea

- **Purpose:** Enter directions, notes or failure detail.
- **Variants:** Multiline.
- **States:** I + E; L through parent save action.
- **Required properties/interface:** label, value, onChange, maxLength from contract, help, errorMessage.
- **Accessibility:** Associated label; explain limits; do not announce counter every character.
- **Responsive behavior:** Grow vertically; web resize allowed; keyboard does not hide submit.
- **Localization:** Devanagari-safe multiline input; show contract limit without assuming one glyph equals one code unit.
- **Existing web location:** [web/app/account/addresses/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/account/addresses/page.tsx>); [web/app/delivery/incidents/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/delivery/incidents/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/account_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/account_screen.dart>); [mobile/lib/src/screens/role_workspaces.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/role_workspaces.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.10. Feedback/Notice

- **Purpose:** Inline Notice, Error, Success and Warning communicate a local outcome.
- **Variants:** Info/Inline Notice, Error, Success, Warning; optional action.
- **States:** Static tone; action uses I + L.
- **Required properties/interface:** tone, title optional, message, action optional, announcement policy.
- **Accessibility:** Meaningful icon plus text; alert only urgent new errors; success/info polite.
- **Responsive behavior:** Wrap; action moves below copy at320.
- **Localization:** Complete localized recovery sentence; no raw server traceback.
- **Existing web location:** [web/app/globals.css](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/globals.css>); [web/app/checkout/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/checkout/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>); [mobile/lib/src/widgets/order_support_card.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/widgets/order_support_card.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.11. Feedback/Loading

- **Purpose:** Indicate real content or action work.
- **Variants:** Inline; content placeholder only where structure is known.
- **States:** Loading.
- **Required properties/interface:** accessibleLabel, scope, retainedContent optional.
- **Accessibility:** Single status announcement; decorative animation hidden from semantics.
- **Responsive behavior:** Reserve likely content space without forcing translated text heights.
- **Localization:** Localized loading label; no fabricated percentage or ETA.
- **Existing web location:** [web/app/market/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/market/page.tsx>); [web/app/checkout/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/checkout/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/market_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/market_screen.dart>); [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.12. Feedback/Empty

- **Purpose:** Explain a genuinely empty collection.
- **Variants:** Empty cart, no results, no orders via content properties.
- **States:** Empty; optional action I.
- **Required properties/interface:** title, explanation, actionLabel, onAction.
- **Accessibility:** Logical heading and action; distinguish empty from loading/error.
- **Responsive behavior:** Simple text and small optional icon; no large illustration requirement.
- **Localization:** Explain next step in ordinary language.
- **Existing web location:** [web/app/cart/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/cart/page.tsx>); [web/app/orders/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/orders/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>); [mobile/lib/src/screens/orders_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/orders_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.13. Feedback/Retry

- **Purpose:** Recover a failed read or an operation safe to retry.
- **Variants:** Inline or section recovery.
- **States:** E; action I + L.
- **Required properties/interface:** message, onRetry, retryLabel, busy, operationSafety.
- **Accessibility:** Focus stays on retry; new result announced; repeated requests suppressed.
- **Responsive behavior:** Stack message/action on narrow screens.
- **Localization:** Explain what retry does; no generic technical error codes alone.
- **Existing web location:** [web/app/market/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/market/page.tsx>); [web/app/checkout/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/checkout/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/market_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/market_screen.dart>); [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.14. Feedback/Offline

- **Purpose:** Explain connectivity loss and stale content.
- **Variants:** Offline, reconnecting using message/state properties.
- **States:** Offline; retry I + L if applicable.
- **Required properties/interface:** connectionState, lastUpdated optional, message, retry optional.
- **Accessibility:** Polite transition announcement; does not trap or steal focus.
- **Responsive behavior:** Banner wraps without covering header, footer or focused input.
- **Localization:** Say which action needs connection; never promise saved submission without evidence.
- **Existing web location:** [web/components/ConnectivityBanner.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/components/ConnectivityBanner.tsx>); [web/app/delivery/offline/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/delivery/offline/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/customer_shell.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/customer_shell.dart>); [mobile/lib/src/screens/role_workspaces.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/role_workspaces.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.15. Feedback/PendingAction

- **Purpose:** Show a submitted action whose outcome is not yet confirmed.
- **Variants:** Pending with check-status action if contract supports it.
- **States:** L; E on confirmed failure.
- **Required properties/interface:** operationLabel, statusMessage, onCheckStatus optional, busy.
- **Accessibility:** Polite status; no success icon until server confirms.
- **Responsive behavior:** Fits checkout and order panels without replacing useful order data.
- **Localization:** Distinguish processing payment from order placed; never tell user to pay twice.
- **Existing web location:** [web/app/checkout/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/checkout/page.tsx>); [web/app/orders/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/orders/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>); [mobile/lib/src/screens/orders_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/orders_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.16. Navigation/AppHeader

- **Purpose:** Orient the user and expose current-context actions.
- **Variants:** Customer; role-specific composition deferred.
- **States:** Child actions I; active route S.
- **Required properties/interface:** title, navigationActions, currentRoute, backAction optional.
- **Accessibility:** Header landmark; back labeled; no heading-order jumps.
- **Responsive behavior:** Wrap title or reduce optional actions; maintain48 targets.
- **Localization:** Long titles; no English-only icon tooltips.
- **Existing web location:** [web/components/Nav.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/components/Nav.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/customer_shell.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/customer_shell.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.17. Navigation/BottomNavigation

- **Purpose:** Switch approved customer destinations.
- **Variants:** Single semantic family.
- **States:** I + S.
- **Required properties/interface:** items id/label/icon/destination, activeId, onNavigate.
- **Accessibility:** Navigation landmark/current page; labels remain visible.
- **Responsive behavior:** Safe-area padding; content clears bar; adapt to large text without clipped labels.
- **Localization:** HI/MR labels validated; do not invent destination count before customer navigation approval.
- **Existing web location:** [web/components/Nav.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/components/Nav.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/customer_shell.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/customer_shell.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.18. Navigation/WorkspaceNavigation

- **Purpose:** Navigate authorized merchant/rider/operations areas.
- **Variants:** Role-scoped composition; design deferred.
- **States:** I + S.
- **Required properties/interface:** authorizedItems, activeId, roleContext.
- **Accessibility:** Navigation semantics; hidden UI is not authorization.
- **Responsive behavior:** Desktop rail; compact menu on mobile only after role design approval.
- **Localization:** Translate role and task labels, keep status enums internal.
- **Existing web location:** [web/components/Nav.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/components/Nav.tsx>); [web/app/admin/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/admin/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/role_workspaces.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/role_workspaces.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.19. Navigation/LocationSummary

- **Purpose:** Show current service locality and change action.
- **Variants:** Known locality, missing locality.
- **States:** Action I; L during resolve; E on failure.
- **Required properties/interface:** village/locality display, district context, onChange, serviceStatus.
- **Accessibility:** Named change-location button; location text readable without icon.
- **Responsive behavior:** Two or more lines allowed; action remains48.
- **Localization:** Village, taluka and district names preserved; no ambiguous truncated duplicates.
- **Existing web location:** [web/components/UniversalLocationSearch.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/components/UniversalLocationSearch.tsx>); [web/app/market/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/market/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/market_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/market_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.20. Commerce/StoreCard

- **Purpose:** Open a store with truthful availability.
- **Variants:** Store content; available/unavailable is domain data.
- **States:** Link I; loading belongs collection.
- **Required properties/interface:** storeId, name, locality, availability, image optional, onOpen.
- **Accessibility:** Single main link; image alt only if informative; closed status textual.
- **Responsive behavior:** Single column at320 when detail needs it; no nested conflicting click targets.
- **Localization:** Long local shop names wrap; no invented ratings, delivery time or trust claims.
- **Existing web location:** [web/app/market/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/market/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/market_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/market_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.21. Commerce/ProductCard

- **Purpose:** Explain product, unit, price and permitted add action.
- **Variants:** Available, unavailable content; image optional.
- **States:** Add I + L; E on mutation failure.
- **Required properties/interface:** productId, name, unit, serverPrice, availability, quantity, onAdd.
- **Accessibility:** Name/unit/price associated; add accessible name includes product.
- **Responsive behavior:** Stack action below details at320; reserve image area only if useful.
- **Localization:** Keep unit meaning; long bilingual product names wrap.
- **Existing web location:** [web/app/market/[id]/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/market/[id]/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/store_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/store_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.22. Commerce/QuantityStepper

- **Purpose:** Change cart quantity using existing validation.
- **Variants:** Shared decrement/value/increment.
- **States:** Each action I + L; E; boundary disabled.
- **Required properties/interface:** productId, label, quantity, allowedBounds, onChange, busy.
- **Accessibility:** Separate labeled increase/decrease; announce confirmed quantity; 48 targets.
- **Responsive behavior:** Minimum action48 + value space +48; wrap surrounding row rather than shrink.
- **Localization:** Localized accessible name includes product; explain zero/removal behavior from existing flow.
- **Existing web location:** [web/app/cart/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/cart/page.tsx>); [web/app/market/[id]/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/market/[id]/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>); [mobile/lib/src/screens/store_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/store_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.23. Commerce/CartLine

- **Purpose:** Review item and update/remove it.
- **Variants:** Shared item row; unavailable item message.
- **States:** Child I + L; E.
- **Required properties/interface:** cartItem, productName, unitPrice, quantity, onChange, onRemove.
- **Accessibility:** Logical list item; remove names product; avoid entire row clickable.
- **Responsive behavior:** Price and stepper move to separate row at320 or large text.
- **Localization:** Wrap name/unit; never truncate monetary values.
- **Existing web location:** [web/app/cart/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/cart/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.24. Commerce/PriceBreakdown

- **Purpose:** Display authoritative item subtotal, fee and total.
- **Variants:** Quote, confirmed order via supplied data.
- **States:** Loading, ready, error/stale through composed feedback.
- **Required properties/interface:** subtotal, deliveryFee, total, sourceStatus, blockers optional.
- **Accessibility:** Label/value associations; total emphasized semantically, not color alone.
- **Responsive behavior:** Two columns with wrapping labels; amount remains readable.
- **Localization:** INR formatting; distinguish estimate/stale quote from confirmed total.
- **Existing web location:** [web/app/checkout/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/checkout/page.tsx>); [web/app/orders/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/orders/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>); [mobile/lib/src/screens/orders_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/orders_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.25. Commerce/PaymentChoice

- **Purpose:** Choose COD or the existing UPI/Razorpay flow.
- **Variants:** COD, UPI; method option data.
- **States:** I + S; disabled when existing eligibility denies; L/E on payment action.
- **Required properties/interface:** method cod/upi, supportedMethods, onSelect, explanatoryText, paymentStatus.
- **Accessibility:** Radio-group semantics; provider launch a separately named action.
- **Responsive behavior:** Stack choices; disclosure text grows.
- **Localization:** Explain when payment occurs; Razorpay callback alone is not paid confirmation.
- **Existing web location:** [web/app/checkout/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/checkout/page.tsx>); [web/lib/razorpay.ts](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/lib/razorpay.ts>)
- **Existing Flutter location:** [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.26. Address/LocalityPicker

- **Purpose:** Select existing village/locality identity.
- **Variants:** Search, result list, selected summary composition.
- **States:** I + L + E + S; empty separate.
- **Required properties/interface:** query, results with villageId/context, selectedId, onSelect.
- **Accessibility:** Search/list selection semantics; announce chosen locality.
- **Responsive behavior:** Full-width results at320; contextual district/taluka wraps.
- **Localization:** Support HI/MR queries as backend currently permits; document unsupported matching rather than invent it.
- **Existing web location:** [web/components/UniversalLocationSearch.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/components/UniversalLocationSearch.tsx>); [web/components/AddressLocationPicker.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/components/AddressLocationPicker.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/account_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/account_screen.dart>); [mobile/lib/src/screens/market_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/market_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.27. Address/LandmarkAddressForm

- **Purpose:** Collect village-based address and familiar directions.
- **Variants:** Create/edit via same form.
- **States:** Fields I + E; save L.
- **Required properties/interface:** villageId, label, recipientName/phone optional, houseDetails optional, landmark, directions optional, coordinates optional, onSave.
- **Accessibility:** Explicit required fields; field errors and submission summary; location permission optional route.
- **Responsive behavior:** One column phone; optional map never blocks manual entry.
- **Localization:** Landmark required2–240 characters; label max40; preserve native-script address.
- **Existing web location:** [web/app/account/addresses/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/account/addresses/page.tsx>); [web/components/AddressLocationPicker.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/components/AddressLocationPicker.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/account_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/account_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.28. Address/AddressCard

- **Purpose:** Review or select saved delivery address.
- **Variants:** Display, selectable with separate edit action.
- **States:** Selection I + S; edit I; E if unavailable.
- **Required properties/interface:** addressId, locality, landmark, recipient, details, selected, onSelect, onEdit.
- **Accessibility:** Radio semantics when choosing; edit distinct and named.
- **Responsive behavior:** All essential address lines wrap; no fixed card height.
- **Localization:** Use locality/landmark priority; optional house details not mandatory Western street schema.
- **Existing web location:** [web/app/account/addresses/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/account/addresses/page.tsx>); [web/app/checkout/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/checkout/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/account_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/account_screen.dart>); [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.29. Address/ServiceabilityNotice

- **Purpose:** Explain server serviceability and next allowed step.
- **Variants:** Serviceable, not serviceable, unknown.
- **States:** Loading/error check; change action I.
- **Required properties/interface:** serviceable/unknown, blockerMessage, locality, onChangeLocation.
- **Accessibility:** Textual status; unknown never rendered as green success.
- **Responsive behavior:** Inline wrapping notice.
- **Localization:** Plain local-language reason; do not promise expansion dates.
- **Existing web location:** [web/app/checkout/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/checkout/page.tsx>); [web/components/UniversalLocationSearch.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/components/UniversalLocationSearch.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/cart_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/cart_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.30. Order/OrderCard

- **Purpose:** Summarize a real order for customer review.
- **Variants:** Customer summary; role actions deferred.
- **States:** Link/actions I + L; E.
- **Required properties/interface:** orderId, storeName, itemsSummary, total, orderStatus, paymentStatus, onOpen.
- **Accessibility:** Separate order/payment labels; dates human-readable.
- **Responsive behavior:** Stack totals/statuses on narrow cards; readable reference.
- **Localization:** Translate enum labels without changing enum values; no status inferred from color.
- **Existing web location:** [web/app/orders/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/orders/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/orders_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/orders_screen.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.31. Order/Progress

- **Purpose:** Explain actual lifecycle and current next step.
- **Variants:** Standard lifecycle; returned/cancelled branches from data.
- **States:** Domain current/completed/future; refresh L/E/offline.
- **Required properties/interface:** orderStatus, deliveryStatus, events if available, lastUpdated.
- **Accessibility:** Ordered list; current step explicit; no false completed milestones.
- **Responsive behavior:** Vertical at320/large text; horizontal only if all labels fit.
- **Localization:** Use understandable status phrases; no invented ETA.
- **Existing web location:** [web/app/orders/lifecycle/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/orders/lifecycle/page.tsx>); [web/components/LiveTracking.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/components/LiveTracking.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/orders_screen.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/orders_screen.dart>); [mobile/lib/src/widgets/customer_live_tracking.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/widgets/customer_live_tracking.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.32. Delivery/TaskCard

- **Purpose:** Present permitted task data and actions; design deferred.
- **Variants:** Offer, assigned task based on different authorized data.
- **States:** Child I + L + E; delivery domain state.
- **Required properties/interface:** taskId, store, coarseDropoffArea for offer, permittedDetails after assignment, paymentMethod, total, allowedActions.
- **Accessibility:** Actions clearly named; do not rely on map alone.
- **Responsive behavior:** Task details stack; thumb-reachable48/56 actions.
- **Localization:** Plain pickup/dropoff instructions; customer private data excluded from offers.
- **Existing web location:** [web/app/delivery/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/delivery/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/role_workspaces.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/role_workspaces.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.33. Delivery/ProofOfDelivery

- **Purpose:** Complete controlled delivery proof; design deferred.
- **Variants:** Challenge, submit, confirmed outcome.
- **States:** I + L + E; expired challenge.
- **Required properties/interface:** taskId, sixDigitOtp, evidenceUrl optional, recipientName optional, notes optional, expiry from response, onSubmit.
- **Accessibility:** Code label and error association; no success until server acceptance.
- **Responsive behavior:** Single-column proof form; camera/upload if existing supported behavior only.
- **Localization:** Explain code source and expiry; never expose proof code to unauthorized roles.
- **Existing web location:** [web/app/delivery/complete/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/delivery/complete/page.tsx>); [web/app/orders/proof/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/orders/proof/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/role_workspaces.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/role_workspaces.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

### 3.34. Delivery/Failure

- **Purpose:** Record controlled delivery failure; design deferred.
- **Variants:** Reason selection and optional detail; resolution role-limited.
- **States:** I + L + E + S.
- **Required properties/interface:** taskId, allowedReason, detail, onSubmit, permittedResolutionActions.
- **Accessibility:** Radio/select reason semantics; confirmation action states consequence.
- **Responsive behavior:** One column; full reason labels and retry guidance.
- **Localization:** Translate six existing reasons; preserve reason keys.
- **Existing web location:** [web/app/delivery/incidents/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/delivery/incidents/page.tsx>); [web/app/admin/delivery-recovery/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/admin/delivery-recovery/page.tsx>)
- **Existing Flutter location:** [mobile/lib/src/screens/role_workspaces.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/screens/role_workspaces.dart>)
- **Saved status:** Planned; not saved as a completed reusable Figma component.

Supporting behavior such as a single-store conflict confirmation must compose Button, Notice and existing dialog behavior when the customer flow reaches it. Icon actions reuse Button mechanics and accessible naming. This does not authorize an additional decorative component library or new routes. The inventory covers all requested categories: the four Notice tones explicitly cover Inline Notice, Error, Success and Warning; Button state variants explicitly cover Loading and Disabled.

## 4. Token mapping — existing variables only

The tables enumerate all 79 saved variables. CSS names preserve the saved web code syntax. A CSS name in this table is a future binding unless it already exists in `globals.css`; this document does not create it. Flutter names below are proposed adapter fields, not additional design tokens. Primitive values resolve semantic aliases; components consume semantics instead of choosing raw palette colors.

### 4.1 Primitives — 16 variables

Flutter `GaonPalette` below means a small internal constant namespace, not a new package. Public component styling uses ColorScheme/theme extensions below.

| Figma variable | Value | CSS custom property | Flutter adapter |
|---|---|---|---|

| `green/700` | `#145B33` | `--go-green-700` | `GaonPalette.green700` = `Color(0xFF145B33)` |

| `green/600` | `#1F7A45` | `--go-green-600` | `GaonPalette.green600` = `Color(0xFF1F7A45)` |

| `green/50` | `#EAF4ED` | `--go-green-50` | `GaonPalette.green50` = `Color(0xFFEAF4ED)` |

| `neutral/0` | `#FFFFFF` | `--go-neutral-0` | `GaonPalette.neutral0` = `Color(0xFFFFFFFF)` |

| `neutral/50` | `#F6F8F4` | `--go-neutral-50` | `GaonPalette.neutral50` = `Color(0xFFF6F8F4)` |

| `neutral/100` | `#E8ECE7` | `--go-neutral-100` | `GaonPalette.neutral100` = `Color(0xFFE8ECE7)` |

| `neutral/200` | `#DFE7DF` | `--go-neutral-200` | `GaonPalette.neutral200` = `Color(0xFFDFE7DF)` |

| `neutral/500` | `#7C877F` | `--go-neutral-500` | `GaonPalette.neutral500` = `Color(0xFF7C877F)` |

| `neutral/600` | `#667069` | `--go-neutral-600` | `GaonPalette.neutral600` = `Color(0xFF667069)` |

| `neutral/900` | `#17221A` | `--go-neutral-900` | `GaonPalette.neutral900` = `Color(0xFF17221A)` |

| `red/700` | `#B42318` | `--go-red-700` | `GaonPalette.red700` = `Color(0xFFB42318)` |

| `red/50` | `#FFF0EE` | `--go-red-50` | `GaonPalette.red50` = `Color(0xFFFFF0EE)` |

| `amber/700` | `#765000` | `--go-amber-700` | `GaonPalette.amber700` = `Color(0xFF765000)` |

| `amber/50` | `#FFF8DB` | `--go-amber-50` | `GaonPalette.amber50` = `Color(0xFFFFF8DB)` |

| `blue/700` | `#3456A3` | `--go-blue-700` | `GaonPalette.blue700` = `Color(0xFF3456A3)` |

| `blue/50` | `#EEF4FF` | `--go-blue-50` | `GaonPalette.blue50` = `Color(0xFFEEF4FF)` |

### 4.2 Semantic color aliases — 25 variables

| Figma variable | Alias → resolved value | CSS custom property | Flutter mapping |
|---|---|---|---|

| `surface/canvas` | `neutral/50` → `#F6F8F4` | `--bg` | `ThemeData.scaffoldBackgroundColor` |

| `surface/card` | `neutral/0` → `#FFFFFF` | `--surface` | `ColorScheme.surface` |

| `surface/subtle` | `green/50` → `#EAF4ED` | `--soft` | `GaonColors.surfaceSubtle` |

| `surface/disabled` | `neutral/100` → `#E8ECE7` | `--go-surface-disabled` | `GaonColors.surfaceDisabled` |

| `text/primary` | `neutral/900` → `#17221A` | `--ink` | `ColorScheme.onSurface` |

| `text/secondary` | `neutral/600` → `#667069` | `--muted` | `ColorScheme.onSurfaceVariant` |

| `text/inverse` | `neutral/0` → `#FFFFFF` | `--go-text-inverse` | `ColorScheme.onPrimary; onError` |

| `text/brand` | `green/700` → `#145B33` | `--brand2` | `GaonColors.textBrand` |

| `text/disabled` | `neutral/600` → `#667069` | `--go-text-disabled` | `GaonColors.textDisabled` |

| `action/primary` | `green/600` → `#1F7A45` | `--brand` | `ColorScheme.primary` |

| `action/pressed` | `green/700` → `#145B33` | `--go-action-pressed` | `GaonColors.actionPressed` |

| `action/secondary` | `green/50` → `#EAF4ED` | `--go-action-secondary` | `GaonColors.actionSecondary` |

| `action/destructive` | `red/700` → `#B42318` | `--go-action-destructive` | `ColorScheme.error` |

| `border/default` | `neutral/200` → `#DFE7DF` | `--line` | `ColorScheme.outlineVariant` |

| `border/input` | `neutral/500` → `#7C877F` | `--go-border-input` | `ColorScheme.outline` |

| `border/selected` | `green/600` → `#1F7A45` | `--go-border-selected` | `GaonColors.borderSelected` |

| `focus/ring` | `green/700` → `#145B33` | `--go-focus-ring` | `GaonColors.focusRing` |

| `status/success/bg` | `green/50` → `#EAF4ED` | `--go-status-success-bg` | `GaonColors.successBackground` |

| `status/success/text` | `green/700` → `#145B33` | `--go-status-success-text` | `GaonColors.successText` |

| `status/warning/bg` | `amber/50` → `#FFF8DB` | `--go-status-warning-bg` | `GaonColors.warningBackground` |

| `status/warning/text` | `amber/700` → `#765000` | `--go-status-warning-text` | `GaonColors.warningText` |

| `status/error/bg` | `red/50` → `#FFF0EE` | `--go-status-error-bg` | `ColorScheme.errorContainer` |

| `status/error/text` | `red/700` → `#B42318` | `--danger` | `ColorScheme.onErrorContainer` |

| `status/info/bg` | `blue/50` → `#EEF4FF` | `--go-status-info-bg` | `GaonColors.infoBackground` |

| `status/info/text` | `blue/700` → `#3456A3` | `--go-status-info-text` | `GaonColors.infoText` |

Existing CSS variables reused unchanged: `--bg`, `--surface`, `--ink`, `--muted`, `--brand`, `--brand2`, `--line`, `--soft`, `--danger`. Existing `--warn` is **#9A6700**, whereas saved Figma `status/warning/text` is **#765000**. Do not silently alias those unequal colors or overwrite the legacy token. Use the saved `--go-status-warning-text` in approved new components; legacy migration needs explicit review. Existing `.codNotice` already uses #765000.

Where semantics share a primitive, retain alias relationships rather than introduce slightly different colors. For example pressed action and brand text share green/700, but remain distinct semantic references. No dark mode or extra palette is specified. Flutter must explicitly override mapped ColorScheme fields; a generated seed scheme alone does not reproduce the Figma values. `GaonColors` is a proposed ThemeExtension for semantics Material does not express directly. Unmapped Material roles retain existing behavior until a real component requires a reviewed mapping.

### 4.3 Metrics — 26 variables

| Figma variable | Value/unit | CSS custom property | Flutter theme extension field |
|---|---|---|---|

| `spacing/4` | 4px | `--go-spacing-4` | `GaonMetrics.spacing4` (logical pixels) |

| `spacing/8` | 8px | `--go-spacing-8` | `GaonMetrics.spacing8` (logical pixels) |

| `spacing/12` | 12px | `--go-spacing-12` | `GaonMetrics.spacing12` (logical pixels) |

| `spacing/16` | 16px | `--go-spacing-16` | `GaonMetrics.spacing16` (logical pixels) |

| `spacing/24` | 24px | `--go-spacing-24` | `GaonMetrics.spacing24` (logical pixels) |

| `spacing/32` | 32px | `--go-spacing-32` | `GaonMetrics.spacing32` (logical pixels) |

| `spacing/48` | 48px | `--go-spacing-48` | `GaonMetrics.spacing48` (logical pixels) |

| `radius/8` | 8px | `--go-radius-8` | `GaonMetrics.radius8` (logical pixels) |

| `radius/12` | 12px | `--go-radius-12` | `GaonMetrics.radius12` (logical pixels) |

| `radius/16` | 16px | `--go-radius-16` | `GaonMetrics.radius16` (logical pixels) |

| `radius/24` | 24px | `--go-radius-24` | `GaonMetrics.radius24` (logical pixels) |

| `target/min` | 48px | `--go-target-min` | `GaonMetrics.targetMin` (logical pixels) |

| `target/primary` | 56px | `--go-target-primary` | `GaonMetrics.targetPrimary` (logical pixels) |

| `layout/gutter/mobile` | 16px | `--go-layout-gutter-mobile` | `GaonMetrics.layoutGutterMobile` (logical pixels) |

| `layout/gutter/tablet` | 24px | `--go-layout-gutter-tablet` | `GaonMetrics.layoutGutterTablet` (logical pixels) |

| `layout/gutter/desktop` | 32px | `--go-layout-gutter-desktop` | `GaonMetrics.layoutGutterDesktop` (logical pixels) |

| `layout/content/max` | 1180px | `--go-layout-content-max` | `GaonMetrics.layoutContentMax` (logical pixels) |

| `layout/viewport/320` | 320px | `--go-layout-viewport-320` | `GaonMetrics.layoutViewport320` (logical pixels) |

| `layout/viewport/360` | 360px | `--go-layout-viewport-360` | `GaonMetrics.layoutViewport360` (logical pixels) |

| `layout/viewport/390` | 390px | `--go-layout-viewport-390` | `GaonMetrics.layoutViewport390` (logical pixels) |

| `layout/viewport/tablet` | 768px | `--go-layout-viewport-tablet` | `GaonMetrics.layoutViewportTablet` (logical pixels) |

| `layout/viewport/desktop` | 1440px | `--go-layout-viewport-desktop` | `GaonMetrics.layoutViewportDesktop` (logical pixels) |

| `stroke/default` | 1px | `--go-stroke-default` | `GaonMetrics.strokeDefault` (logical pixels) |

| `stroke/focus` | 2px | `--go-stroke-focus` | `GaonMetrics.strokeFocus` (logical pixels) |

| `motion/duration/standard` | 150ms | `--go-motion-duration-standard` | `GaonMetrics.motionDurationStandard` (Duration) |

| `motion/duration/reduced` | 0ms | `--go-motion-duration-reduced` | `GaonMetrics.motionDurationReduced` (Duration) |

Viewport variables are QA reference widths, **not saved breakpoint modes**. Mobile/tablet/desktop gutters must be applied through responsive rules; the single saved metric mode does not switch them automatically. A proposed future layout policy is mobile below768, tablet768–1199, desktop1200+, with desktop content capped1180. Existing CSS breakpoints must be reviewed against each approved layout before replacement; this document does not change them. At1440, center the1180 content region while retaining at least32 side clearance.

Use rem equivalents for web text/minimum control sizes where text scaling requires them (16px base); min-height can grow. Flutter dimensions are logical pixels, and text respects system scaling. Motion duration150ms is only for brief state feedback; reduced motion0ms removes nonessential animation. Show a static loading label under reduced motion. Neither token controls network deadlines or payment retry timing.

### 4.4 Typography — 12 variables

| Figma variable | Value | CSS custom property | Flutter mapping |
|---|---|---|---|

| `body/size` | 16px | `--go-body-size` | `TextTheme.bodyLarge.fontSize = 16` |

| `body/line` | 24px | `--go-body-line` | `TextTheme.bodyLarge.height = 24/16` |

| `supporting/size` | 14px | `--go-supporting-size` | `TextTheme.bodyMedium.fontSize = 14` |

| `supporting/line` | 20px | `--go-supporting-line` | `TextTheme.bodyMedium.height = 20/14` |

| `label/size` | 16px | `--go-label-size` | `TextTheme.labelLarge.fontSize = 16` |

| `label/line` | 24px | `--go-label-line` | `TextTheme.labelLarge.height = 24/16` |

| `title/small/size` | 20px | `--go-title-small-size` | `TextTheme.titleMedium.fontSize = 20` |

| `title/small/line` | 28px | `--go-title-small-line` | `TextTheme.titleMedium.height = 28/20` |

| `title/large/size` | 24px | `--go-title-large-size` | `TextTheme.titleLarge.fontSize = 24` |

| `title/large/line` | 32px | `--go-title-large-line` | `TextTheme.titleLarge.height = 32/24` |

| `family/latin` | Inter | `--go-family-latin` | `GaonTypography.latinFamily; TextTheme fontFamily for en` |

| `family/devanagari` | Noto Sans Devanagari | `--go-family-devanagari` | `GaonTypography.devanagariFamily; hi/mr and fallback` |

Saved text styles are `GaonOne/{EN,HI,MR}/{Body,Supporting,Label,Title Small,Title Large}`: 15 styles. Body/supporting are regular; labels/titles use the saved semibold treatment. Weight comes from text styles, not an invented weight variable. Validate actual font availability and weight resolution before implementation; no remote font dependency is authorized here. Avoid artificial letter spacing in Devanagari. Mixed-language content must fall back per glyph without changing semantic labels.

The saved effect style `GaonOne/Focus Ring` is not an additional variable. Expected rendering is a 2px white separation plus a 2px outer green/700 ring, using existing `stroke/focus`, `surface/card` and `focus/ring`. Web may express this as 2px outline with2px offset plus a white separation shadow; Flutter should draw equivalent outer decoration without reducing hit area. It must remain visible in platform high-contrast behavior.

## 5. Button and Field QA specification

### 5.1 Button loading-label override — confirmed issue

The shared `Label` property defaulted to “Continue” and overwrote intended loading/destructive text in saved variants. A setter returning successfully is not proof of a correct rendered component.

Future correction: retain existing set and instances. Keep `Label` bound to the normal action text and introduce a distinct `Loading label` text property/node for the busy state. Visibility changes with state; no state switch mutates the normal property. An instance labeled “Place order” must show its configured loading phrase, then restore “Place order”; a destructive instance must retain its explicit destructive verb. Loading text must not be inferred by appending English punctuation. Do not rename or recreate the set to fix this.

### 5.2 Focus ring correction — confirmed visual failure, cause unverified

The effect style was bound but did not visibly render on the inspected Button. Once allowance returns, inspect the actual effect values/bindings, visibility, clipping on the control and every ancestor, and whether strokes/shadows are outside the bounds. Root cause is not yet established. Correct and visually inspect before marking complete. Expected ring: white2px gap, dark-green2px outer indicator, visible on both canvas and card surfaces, including error and selected controls. Leave4px outer clearance. Ring must not change layout, be clipped by a card or be substituted with only a subtle color shift.

### 5.3 Exact state behavior

| State | Button | Field/choice control |
|---|---|---|
| Default | Primary green600/white; Secondary green50/green700; Tertiary transparent/green700; Destructive red700/white. | Card surface; primary value; secondary help; input border neutral500; persistent label. |
| Hover | Primary green700; Secondary retains green50 and gains selected border; Tertiary green50 background; Destructive retains red700 and adds a visible boundary treatment. No new colors. | Same value and label; selected-color border. Pointer devices only. |
| Pressed | Primary green700; Secondary/Tertiary green50 with2px selected boundary; Destructive red700 with2px primary-text boundary. No scaling or label movement. |2px selected boundary while activated; no value reset or layout jump. |
| Focused | Default/active colors plus corrected outer focus ring; visible alongside pressed/busy when focused. | Corrected outer ring; error border stays visible independently. |
| Disabled | Disabled surface/text; no activation or hover effect; normal label retained, reason nearby if required. Tertiary may retain transparent surface with disabled text. | Preserve readable value; prevent edits; explain dependency. Do not erase content. Read-only is a separate behavior, not automatically disabled. |
| Loading | Dedicated loading label plus indicator; repeated activation suppressed; keep focus and stable minimum width while allowing wrapping. Announce busy once. | Preserve typed value; non-obscuring indicator and separate loading message. Disable only conflicting interactions. Do not replace value with “Searching…”. |
| Error | Keep action recognizable; show related Error notice; allow safe retry after failure. Error is not a new Button intent. | Error border/text with explicit message; invalid semantics; keep label/value. Focus first invalid field after failed submit and provide summary for multiple errors. |
| Selected | Not applicable to ordinary submit buttons; use choice semantics for toggles. | Check/radio indicator plus text/shape or border; selected appearance persists under hover/focus and disabled. |

Proposed hover/pressed corrections above reuse existing tokens but are not claimed to be saved in Figma. Validate non-color cues and contrast during Component QA. For Field, potential `Value`/`Help` override collisions are **unverified**. Test explicit properties `Value`, `Placeholder`, `Help`, `Error message`, `Loading message` so loading/error never overwrite entered text or permanently replace help. Placeholder must disappear only when value exists.

Button regression cases: set a custom English/Hindi/Marathi Label and Loading label; switch through every intent/state; return to Default; verify both strings survive instance swaps. Repeat for a destructive verb and two-line label. Focus regression: canvas/card/nested frame, keyboard-only, error+focus, selected+focus, busy+focus, and large text. Field regression: type a long localized value, trigger validation/search, resolve it, and verify original value and helper text remain intact.

## 6. Component QA matrix

No cases below are marked passed; they are acceptance specifications. Figma previews validate layout only. Keyboard, assistive technology, network behavior and API mutation guarantees require later running web/Flutter verification after implementation is approved.

### 6.1 Viewport × language coverage

Run every customer/shared component in en, hi and mr at each width below (15 baseline combinations). For noninteractive feedback, record interaction states as not applicable with a reason. Deferred role components receive the same matrix only after their design gate opens.

| Width | Expected layout | Required checks |
|---|---|---|
|320 |16px gutters;288px content; single-column forms/cards when needed | No horizontal scroll;48 targets; wrapped actions, prices and addresses; keyboard does not obscure primary action. |
|360 |16px gutters;328px content | Typical Android baseline; complete cart line and payment explanations; bottom safe area. |
|390 |16px gutters;358px content | No arbitrary increase in density; same reading order and semantics. |
|768 tablet |24px gutters;720px content | Optional columns only if reading/focus order preserved; field width remains usable. |
|1440 desktop |32px minimum gutters;1180px max content | Pointer hover, visible keyboard focus, sensible line length, no stretched forms or hidden actions. |

### 6.2 State and resilience cases

| Case | Coverage | Pass criterion |
|---|---|---|
| Normal | Every component × five widths × three languages | Correct token bindings, native glyphs, meaningful text, no clipping or fabricated data. |
| Large text | All controls/cards at320/360/390; sample tablet/desktop; all languages |200% text scaling; browser400% zoom/reflow check separately; minimum targets retained; content grows, no essential ellipsis. |
| Keyboard focus | Every interactive control and nested action | Tab/Shift+Tab predictable; Enter/Space/arrow behavior matches control; ring visible; no trap; focus restored after overlays. |
| Loading | Each async control at320 and desktop; all languages | Custom loading label survives; one operation per activation; existing data/value retained; no false completion. |
| Error | Each field and mutation/read failure | Error understandable and associated; safe recovery; submitted data retained; focused error ring visible. |
| Offline | Before initial load, after known data, during checkout/payment | Explain unknown vs stale; preserve draft where existing behavior allows; no false paid/placed state; no new queue. |
| Slow network | Throttled low bandwidth/high latency; delayed and dropped responses | Usable feedback without layout jump; duplicate submissions suppressed; retry follows idempotency/contract; no invented progress. |
| Disabled | Each control plus disabled-selected choices | Cannot activate; value/label remains readable; reason provided for critical unavailable action. |
| Selected | Radio, checkbox, address/payment choice, navigation | Selection announced; not color-only; focus independent; only permitted selection count. |
| Reduced motion | Loading and state transitions | Nonessential motion removed; static status still communicates work. |
| Missing image/data | Store/product and tracking | Text-first fallback; no broken-image layout; unknown status not mislabeled empty or successful. |
| Low-end Android | Actual supported Android device/emulator with constrained resources | Responsive taps/typing/scrolling; no animation dependency; usable manual locality path when map/GPS unavailable. |
| Assistive technology | Screen reader web and TalkBack | Correct names/roles/values; one useful status announcement; no duplicate semantics; meaningful money/address reading. |

Long-text fixtures (working QA copy, not final approved translation):

- Hindi action: “इस पते पर डिलीवरी की उपलब्धता जाँचें और आगे बढ़ें”
- Marathi action: “या पत्त्यावर वितरण उपलब्ध आहे का ते तपासा आणि पुढे जा”
- Hindi address: “ग्राम पंचायत कार्यालय के पीछे, जिला परिषद प्राथमिक विद्यालय के मुख्य द्वार के पास, पुरानी पानी की टंकी के सामने”
- Marathi address: “ग्रामपंचायत कार्यालयाच्या मागे, जिल्हा परिषद प्राथमिक शाळेच्या मुख्य प्रवेशद्वाराजवळ, जुन्या पाण्याच्या टाकीसमोर”
- Hindi offline: “इंटरनेट कनेक्शन उपलब्ध नहीं है। आपका भुगतान पूरा हुआ है या नहीं, इसकी पुष्टि अभी नहीं हुई है।”
- Marathi offline: “इंटरनेट जोडणी उपलब्ध नाही. तुमचे पेमेंट पूर्ण झाले आहे की नाही, याची अद्याप पुष्टी झालेली नाही.”

Also use mixed-script shop/product names, long district/taluka combinations, ₹1,23,456.78, empty optional fields, maximum allowed landmark text, and proof-code validation. Native Hindi/Marathi review is required before approval. Test pseudo-expanded text in addition to these examples.

Figma QA frames should be instances, named `QA/{Component}/{Width}/{Language}/{Case}`. Begin with Button and Field; then compose a compact320/360/390 specimen containing payment choice, address, price, error/offline/loading and long text. This is a component test board, not Home or checkout screen design. Record observed result, node, language/font, viewport, defect and approval owner.

## 7. Design-to-code rules

| Area | Rule |
|---|---|
| Figma components | Keep existing `Action/Button` and `Form/Field`. Use semantic families from inventory. Properties `Intent`, `State`, `Label`, `Loading label`; variants in Title Case. Use content properties/nested instances instead of decorative copies. |
| CSS | Retain existing plain-CSS architecture. Proposed reusable classes use `go-button`, `go-field`, `go-store-card`; parts such as `go-field__error`. State via native selectors/ARIA and restrained `data-state`; no new Tailwind dependency. |
| Web names | Proposed React exports `GaonButton`, `GaonField`, `StoreCard`, etc. UI props camelCase. Extract shared primitives into an approved `web/components/ui/` location later; domain components into existing or approved semantic subfolders. These directories are proposals. |
| Flutter names | Proposed widgets `GaonButton`, `GaonField`, `StoreCard`; files snake_case under approved `mobile/lib/src/widgets/` subfolders. Use existing Material state mechanisms, not a second state-management library. |
| Token names | Preserve saved slash names and exact CSS mappings above. Flutter camelCase adapter fields point to the same values/aliases. No token named after a screen or backend fee. |
| State names | Figma Default/Hover/Pressed/Focused/Disabled/Loading/Error/Selected; code lowercase semantic states. Keep domain enums unchanged; map them only to localized display labels. |
| Accessibility | Visible labels and accessible names agree; ids connect label/help/error. Web `aria-current`, `aria-invalid`, `aria-busy`, selected/checked semantics only where appropriate. Flutter Semantics mirrors the same control meaning without duplicating child text. |
| Responsive | Min sizes plus flexible content; no device-name forks; safe areas and keyboard insets respected. QA widths are not breakpoints. Approve adaptive navigation before coding it. |
| Text | Central localized message keys such as `checkout.placeOrder` and `checkout.placingOrder`; no sentence concatenation or fixed text-height assumptions. Font family choice follows locale and fallback. |
| Mapping/handoff | Record Figma node/set, props, states, token references, existing source, proposed extraction and contract source in Developer Handoff. No Code Connect files or plugins are required or created now. |
| Dependencies | Reuse React/CSS and Flutter/Material plus current dependencies. No new font/network/UI/state package without a demonstrated need and separate approval. |

## 8. Customer-flow design and later implementation order

Figma allowance returning is permission to resume the approved foundation work, not permission to implement application code. Preserve the three-page structure. Each later customer stage uses approved components and is reviewed before its implementation.

| Order | Exact design task | Required exit evidence |
|---|---|---|
| A | Complete foundations | Fix saved Button/Field; finish customer/shared inventory; all bindings valid; role-specific design deferred per latest instruction. |
| B | Component QA |320/360/390, EN/HI/MR, large text, focus, error, offline/loading specimens reviewed; defects resolved. |
| C | Customer navigation | Existing destinations and auth transitions mapped; back/selected/bottom-nav behavior approved. |
| D | Locality/location | Manual locality and permission-denied paths; village ids and serviceability mapped. |
| E | Home/discovery | Existing discovery data and truthful availability; loading/empty/retry; no invented trust claims. |
| F | Store/product | Product units, availability, add action and single-store conflict recovery. |
| G | Cart | Quantity/removal, unavailable inventory, persistent single-store constraint. |
| H | Address | Village/landmark form, saved address selection, optional coordinates and validation. |
| I | Checkout | Existing quote/blockers, server total, COD/UPI, duplicate suppression and pending payment. |
| J | Order confirmation | Confirmed server order identity and payment state; never infer paid from provider callback. |
| K | Tracking | Current lifecycle and delivery state; stale/offline/map fallback; no fabricated ETA. |
| L | Recovery/error states | Cross-flow timeout, auth expiry, quote change, inventory conflict, payment ambiguity and retry audit. |

Recovery states are considered within each stage; L is the final cross-flow completeness pass. Do not postpone a necessary error path until after its screen is approved. No Merchant/Rider/Admin screens or role-specific component design before customer critical-path approval. Documented N-section requirements remain reserved, and any already saved work stays untouched.

## 9. Implementation boundaries and contract evidence

The current checkout has changed since the original audit. It already offers `GET /cart/quote` and `POST /orders/checkout`; use the registered authoritative routes. Do not create a new pricing service, order model, gateway, queue, role system or navigation API.

- **Single-store basket:** retain server enforcement. When adding another store conflicts, preserve the current basket and use the existing permitted replacement/clear interaction only after an explicit user action; never silently merge baskets.
- **Server totals:** quote supplies `subtotal`, `delivery_fee`, `total`, `serviceable`, `inventory_valid`, `store_open`, `checkout_ready` and `blockers`. Checkout action reflects readiness but server remains final authority. Flutter may later adapt to this existing quote endpoint; that is client integration, not a new backend contract.
- **₹20 delivery:** preserve existing default `DEFAULT_DELIVERY_FEE=20.00`. Current pricing resolves a configured service-area fee first and falls back to₹20. Display the returned fee; never hardcode₹20 as an authoritative computed total. Whether the business wants a universal₹20 despite existing overrides needs clarification before any policy change.
- **COD and UPI/Razorpay:** keep method values `cod`/`upi`, existing provider flow and server verification. Provider success callbacks, timeouts, offline state and pending status are not proof of payment. Preserve idempotency for retries and server-side financial calculations. Do not add card/wallet methods or pay-later promises.
- **Locality/address:** retain village id and village/taluka/district/state/pincode context. Landmark is required; house details, directions and coordinates follow the existing optional fields. Village coordinate fallback is approximate, not a verified doorstep pin. Retain historical order address snapshots.
- **Order lifecycle:** `placed → accepted/cancelled`; `accepted → preparing/cancelled`; `preparing → ready`; `ready → out_for_delivery`; `out_for_delivery → delivered/returned`. Returned is controlled operations recovery, not a customer/merchant button. Do not infer that every graph edge is available to every role.
- **Delivery lifecycle:** unassigned→assigned; assigned→unassigned/picked_up/failed; picked_up→delivered/failed; failed→unassigned only through allowed recovery rules. Generic delivery status updates cannot bypass controlled delivered/failed endpoints.
- **Payment lifecycle labels:** pending, paid, failed, refund_pending, refunded. These enum values are not an authorization or transition graph. Provider/refund services remain authoritative. Refund workflow separately has requested, processing, succeeded, failed; requested/processing must not be called refunded.
- **Proof:** preserve six-digit OTP, challenge expiry and controlled submission. Existing optional evidence URL max500, recipient name max160, notes max500; optional evidence must not become mandatory through design. No bypass when offline or code expired.
- **Delivery failure:** reasons remain customer_unavailable, address_not_found, vehicle_issue, merchant_issue, unsafe_condition, other. Preserve pre-custody reassignment versus post-pickup return-to-store resolution and associated authorized financial handling.
- **Authorization:** retain customer ownership, merchant store ownership, rider assignment and operations permissions. Unassigned offers expose coarse dropoff area rather than customer identifying details; only assigned/authorized contexts receive permitted address information. UI visibility is not access control.
- **Recovery:** reconcile an uncertain mutation with existing read/status endpoints before retrying; retain established idempotency keys for the same logical operation. Never automatically submit a second payment or invent offline persistence guarantees.

### 9.1 Source index

Current source locations supporting the mappings and boundaries:

- [web/app/globals.css](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/globals.css>)

- [web/lib/api.ts](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/lib/api.ts>)

- [web/app/checkout/page.tsx](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/web/app/checkout/page.tsx>)

- [mobile/lib/main.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/main.dart>)

- [mobile/lib/src/api/gaon_api.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/api/gaon_api.dart>)

- [mobile/lib/src/models/models.dart](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/mobile/lib/src/models/models.dart>)

- [backend/app/api/v1/router.py](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/backend/app/api/v1/router.py>)

- [backend/app/api/v1/routes/checkout.py](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/backend/app/api/v1/routes/checkout.py>)

- [backend/app/services/pricing.py](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/backend/app/services/pricing.py>)

- [backend/app/core/config.py](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/backend/app/core/config.py>)

- [backend/app/services/order_transitions.py](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/backend/app/services/order_transitions.py>)

- [backend/app/models/orders.py](</Users/rishiraj/Documents/Personal_Projects/AI-Powered_Market/AI-Powered_Market/backend/app/models/orders.py>)

## 10. Remaining clarification and Figma limits

- **Delivery pricing:** confirm whether₹20 is intended as the existing default or a universal policy. This document preserves current server behavior, including configured overrides.
- **Language ownership:** nominate Hindi/Marathi reviewers and confirm launch locales, preferred product terms and numeral conventions. Fixture strings are provisional.
- **Font delivery:** confirm permitted local font assets or system fallbacks before code work; avoid adding a runtime font service solely to match screenshots.
- **Navigation:** approve actual customer destinations during C using existing routes; no new destination count is assumed here.
- **Trust content:** ratings, delivery estimates, availability promises and service expansion claims require existing data and approved business meaning before appearing in design.

The saved session was blocked by the Figma MCP usage allowance. No live inspection was attempted for this specification. The approved Starter structure remains three pages; no eleven-page file, upgrade, account change or quota workaround is proposed. Variables currently use one mode per collection; responsive and locale specimens must be explicit instances, not claims of new modes. Library publishing, Code Connect availability and additional plan capabilities have not been verified and are not prerequisites for the next task.

## READY FOR NEXT FIGMA SESSION

- [ ] Allowance available; open the existing file and preserve its three pages and saved instances.
- [ ] Verify the saved inventory against this snapshot before editing; do not recreate existing tokens/components.
- [ ] Fix Button loading-label overrides and visually verify the focus ring.
- [ ] Verify Field value/help/error/loading properties without overwriting typed content.
- [ ] Complete customer/shared foundation components using the79 saved variables.
- [ ] Build and review Component QA at320/360/390 with EN/HI/MR, large text, focus, error, offline and loading.
- [ ] Record remaining defects and foundation/QA approval; keep application code unchanged.
- [ ] Next after A/B approval: **C. Customer navigation**, then D–L in the specified order. Keep Merchant/Rider/Admin design deferred.
