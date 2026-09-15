# GaonOne — Merchant Banner MVP Design Specification

Written delivery,11 September2026. Based on Master Control's banner dispatch and supplied feature brief (`45b8276d-73cb-45a0-bbe4-158444432100/pasted-text.txt`). No Figma/app/Git changes. This is a Figma-ready template/source/version specification, not a provider choice, price commitment, implemented API or visual approval. Any prior architecture detail not present in the supplied brief/dispatch is not assumed approved.

## 1. MVP boundary and composition

Use one controlled GaonOne composition with optional category-appropriate imagery; generated/selected visual assets are separate from actual UI-rendered text. Store name, category and locality remain deterministic, accessible text. Optional description may supply reviewed descriptive content only; absence never blocks a banner. No text generated inside raster images, embedded raster CTA, fabricated products, prices, discounts, popularity, delivery times, ratings or superlatives. No competitor branding or unlicensed logo imitation.

Reuse the saved design specification: action green #1F7A45, canvas #F6F8F4, existing card/text/status/focus semantics; spacing4/8/12/16/24/32/48; radii8/12/16/24 only where relevant. Use body16/24, supporting14/20, labels16/24, titles20/28 or24/32; EN Inter and HI/MR Noto Sans Devanagari with fallbacks. These are saved-spec values, not newly verified Figma bindings or current-main component claims.

The initial template is text-first: store name → actual category → locality context → optional reviewed description. Optional imagery occupies a separate area and must not reduce text contrast. Merchant custom image fits the same accessible shell; essential store information remains UI text even if the uploaded image contains text. Do not automatically extract or trust its visual claims.

Phone layout stacks text/image as necessary; desktop may place imagery beside text. No fixed-height text container. Image crop/ratio and final typography hierarchy require visual approval; this written spec does not invent pixel-perfect frames. Safe text padding uses existing16px mobile and24/32px larger-layout gutter tokens. Image focal point may crop; essential identity cannot exist solely in cropped media. Missing imagery uses the same text template, not a broken-image icon or loading wall.

## 2. Independence from registration

Successful store creation is presented immediately, regardless of generation/provider/storage/moderation outcome. Banner work has its own status and retry. Onboarding never waits for image generation or acceptance. When no accepted banner exists, customer storefront uses deterministic name/category/locality presentation. Do not assert that a banner job was queued unless server confirms that state.

Suggested merchant explanation: “Your store is created. You can review your banner when it is ready.” Use only when store success and pending banner status are known. Otherwise show store success separately from an honest banner-unavailable notice.

## 3. Separate source, candidate and active version

Three independent concepts:

- Editing choice: GaonOne-generated or merchant custom. Switching the editor's choice does not change the public banner.
- Candidate: a new generated/uploaded version awaiting review/acceptance and any required moderation.
- Active presentation: last accepted eligible version, or deterministic fallback when none is eligible.

Regeneration creates a candidate; it never deletes/replaces the active accepted banner. Accepting a ready approved candidate changes the active reference only after server confirmation. Maintain a clear “Currently used” indicator and a separate “Preview” heading. Source/version labels belong in merchant management, not customer storefront unless product policy later requires disclosure.

No exact API names, enum spellings or version-number format are prescribed. Engineering must provide immutable version identity and active-reference semantics. Display friendly version/time only from actual metadata; never imply v2 is active merely because its generation finished last.

## 4. Action/state matrix

| Situation | Merchant sees/actions | Active storefront invariant |
|---|---|---|
| No candidate/no active asset | Deterministic preview; Generate if server permits; custom option | Text template available |
| Queued | Queued message; current banner visible | Existing active version unchanged |
| Generating | In-progress message without invented percentage/ETA | Existing active version unchanged |
| Retrying | Retry status from server; no duplicate generate request | Existing active version unchanged |
| Ready candidate | Preview; Use this banner; regenerate/keep current if permitted | Candidate is not public merely because ready |
| Generation failed/timeout/provider unavailable | Plain failure; explicit retry if permitted; custom/fallback route | Active retained, or deterministic fallback |
| Storage/moderation failure | Distinguish failure/review outcome as server allows; no misleading ready state | Unapproved/unavailable media never activated |
| Regeneration pending while v1 active | Label v1 currently used; new candidate pending | v1 preserved |
| Accept in progress | Disable duplicate accept; show pending | No premature source switch |
| Accept succeeds | Returned version marked currently used | Server-selected active version displayed |
| Accept uncertain/fails | Preserve previous active preview; reconcile before another accept | Do not assume success from optimistic UI |
| Custom upload pending | File-specific progress only when measured; accessible status | Current active retained |
| Custom rejected | Explain allowed type/size/content from server; choose another file | Current active retained |
| Replace custom | New candidate preview before confirmed use | Existing custom retained until replacement accepted |
| Switch back to generated | Show existing eligible generated version or generate new candidate | No silent activation merely by toggling source |
| Remove active custom | Review consequence; submit supported remove/fallback action | Deterministic fallback if server confirms; do not silently resurrect rejected media |
| Moderation disables active banner | Explain safe merchant-facing reason and next step | Safe fallback; previous unsafe media not restored automatically |
| Quota/rate limit | Show server-provided eligibility/retry availability | No invented regeneration allowance, currency cost or countdown |
| Offline/stale | Known active preview labeled appropriately; mutations unavailable/uncertain | Store page never waits for new generation |
| Ownership revoked/store inaccessible | Stop editing and remove sensitive management data | Backend independently denies changes |

Discarding a draft is not deleting an active banner. If discard/reject/history actions are not in the MVP API, omit their controls. Do not add cancellation of a generation job without contract support.

## 5. Figma-ready component specification

| Proposed component | Required content/props | Reason |
|---|---|---|
| StoreBannerPresentation | store name/category/locality, optional reviewed description, optional eligible image, safe alt | Same deterministic shell across sources/fallback |
| BannerManagementSummary | confirmed active version/source, last known status | Avoid draft/live confusion |
| BannerSourceChoice | editor choice, permitted sources, accessible group label | Generated/custom choice without unintended publish |
| BannerCandidatePreview | candidate identity, review state, content, comparison to current | Explicit preview before use |
| BannerGenerationStatus | actual queued/generating/retrying/failed state, safe message | Async work independent of registration |
| BannerVersionAction | accept/regenerate eligibility and operation state | Small action family composed from approved Button |
| CustomBannerUpload | allowed file rules, selected file, progress if measured, error | Safe custom route using shared media contract |
| BannerFallback | actual store name/category/locality | Deterministic variant of presentation, not duplicate visual system |

These are proposed components, not created assets. Existing Button/Field/Notice/Loading/Retry are reused only after recovery and foundation QA. No dozens of decorative variants or category-specific brand systems.

## 6. Required source/version contract semantics

Engineering owns exact data/API design. The UI requires: store ownership/context; active eligible presentation; candidate identity and source; immutable input snapshot/version association; generation and moderation states kept distinct; supported action eligibility; safe failure reason; timestamps; confirmed acceptance result; custom media validation limits; rate-limit/retry state when applicable. A late job result may create a candidate but cannot overwrite newer acceptance automatically.

Store details supplied to generation are allowlisted data. Merchant description is untrusted content, never instructions. Do not send customer/payment/contact/secrets to generation merely because present in a store object. Do not expose raw prompts, provider errors, costs or infrastructure details in merchant copy. Store ownership, role, pricing, inventory, fulfilment, serviceability, approval and financial state are outside banner authority.

Managed public storefront media and private ticket evidence share infrastructure only where appropriate; they retain distinct visibility policies. Existing public upload alone does not establish versioning/moderation/ownership guarantees. Provider choice, cost limits, retry ceilings, storage lifecycle, maximum dimensions and legal terms remain engineer/product/security-owned; this design makes no numeric commitments.

## 7. QA acceptance matrix

All visual results NOT RUN/BLOCKED. Required future cases:

-320/360/390/768/1440px: no horizontal page scrolling,48px targets,56px primary where appropriate, no fixed-height localized text, image crop never hides identity.
- EN/HI/MR with30–50% expansion and200% text: long store/category/locality; no description; multiline description; missing glyphs checked with actual fonts.
- Keyboard: source radio semantics, visible token ring, preview/action reading order, upload accessible label, error association; selected state includes text/indicator.
- Screen reader: store identity remains text; decorative image empty alt; informative image concise accurate description; no duplicate identity announcements; pending status restrained.
- Generation/storage/provider/moderation failure: registration success remains successful; deterministic fallback remains usable.
- v1 accepted, v2 pending/failed/ready: v1 remains active until confirmed acceptance. Out-of-order jobs, multi-tab acceptance and retry cannot silently change active source.
- Custom→generated and generated→custom: editor choice is distinct from publication; failed accept leaves current unchanged.
- No-network/slow network: cached eligible asset where supported, lightweight text fallback, no customer wait for job; no unnecessary image request blocking text.
- Safety: prompt-injection description treated as data; no unsupported claims/products, competitor identity, unapproved logos or sensitive metadata. Legal compliance is not claimed without provider/media rights review.
- Moderation disables active media: safe fallback, audited action and no unauthorized resurrection.

## 8. Dependencies and next-window delivery

| Dependency | Classification | Effect |
|---|---|---|
| One deterministic composition, actual UI text | VD, QA | Written direction ready; visual template pending |
| Active/candidate/source semantics and safe acceptance | ARCH, API, ENG, SEC | Must be contracted before management implementation |
| Async jobs and failure isolation | ARCH, ENG, QA | Registration independence is mandatory |
| Managed media/ownership/moderation | SEC, API, BLOCKER | Required for safe custom/generated activation |
| Provider/cost/retention/legal decisions | PD, SEC, PA | Not chosen by design; do not block deterministic fallback planning |
| Foundation recovery and Figma allowance | VD, QA, BLOCKER | Visual implementation/approval must wait |
| Candidate validation and rollout | REL, QA | Master Control/Git gate; not authorized by this document |

Window1: freeze minimum banner source/version/active reference and action eligibility contract; preserve registration and domain-state independence; coordinate shared media, moderation and worker guarantees. Do not implement a provider/cost choice from this document.

Window2: after legitimate access restoration, inspect existing file, complete foundation QA, then create one shared banner presentation and merchant source/candidate states as instances. Preserve three pages; reserve banner work within Future Work→Merchant. No customer Home redesign implied.

Written delivery complete. Figma visual QA BLOCKED. No claim of implemented APIs, generation performance, provider approval, legal compliance or engineering-screen approval.

## Delivery checkpoint — 12 September 2026

Written template/source/version specification is complete and preserved. It defines management and customer presentation behavior without selecting a provider, setting numeric cost/quota limits, rendering text into raster media or inventing commercial claims. Remaining policy decisions are generation allowance/provider terms, media rights/moderation and storage/retention; remaining engineering dependencies are managed media, async/version acceptance contracts and authoritative action eligibility. Remaining visual dependencies are recovered/approved foundations, restored Figma access, final image crop/composition and actual responsive/language/accessibility inspection. None of those decisions is silently resolved by this document.
