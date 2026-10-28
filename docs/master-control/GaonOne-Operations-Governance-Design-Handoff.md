# GaonOne — Operations & Governance 2.0
## Design information architecture and implementation handoff

Status: written design preparation under Master Control execution authorization. No Figma access attempted, visual QA performed, repository files edited or Git operations performed. This artifact lives outside both application checkouts. Figma remains the future visual source of truth; this is not engineering approval for new screens.

Authority: Master_planner architecture and subsequent execution approval, retrieved 10 September 2026. Source request: attachment `8b5f9202-bc5e-4624-9a0a-a75cfbaf51bb/pasted-text.txt`. Repository observations below are attributed to Master Control's reconnaissance of foundations commit `ae36c3013e9fd0da40dc2c09e053ea5f721a210a`; they are not a fresh code audit. Engineering owns canonical capabilities and API contracts. Proposed names below describe UI concepts, not established endpoints.

## 1. Scope, gates and classification

Classification: PD product decision; VD visual design; API contract; ARCH architecture; ENG implementation; QA validation; SEC security; REL release; BLOCKER dependency; PA material approval outstanding.

| Work | Classification | Gate |
|---|---|---|
| Separate operational and governance IA | VD, PD | Written proposal ready for review; visual implementation pending |
| Capability-aware navigation | API, SEC, VD, ENG | Engineering's canonical matrix and effective-capability response |
| Unified ticket conversation/assignment/escalation | ARCH, API, VD, SEC | Existing support extension; no duplicate ticket domain |
| Private evidence | API, SEC, ARCH, BLOCKER | Shared managed private media; no public uploader reuse unchanged |
| Administrator lifecycle | API, SEC, PD, PA | Suspension, recovery, step-up and scope decisions |
| Metric summaries and freshness | API, VD, QA | Authoritative aggregate sources and definitions |
| Visual frames and interactive prototypes | VD, QA, BLOCKER | Restored Figma access, foundation QA and IA acceptance |
| Release | REL, QA, SEC | Exact-candidate engineering gates under Master Control |

Backend authorization and transactional audit work can proceed under the approved engineering scope without waiting for redesigned dashboards. New visual interfaces do not bypass foundation QA. This governance initiative does not silently approve unrelated Merchant/Rider commerce screens or customer Home. Banner design remains secondary to governance/media controls.

## 2. Known reusable architecture and gaps

Master Control found one identity model with marketplace roles and a separate Super Admin flag; multiple administrators already exist. Existing user activity checks, role dependencies and resource ownership must remain authoritative. The current admin dashboard changes title/controls but does not provide distinct operational/governance IA.

Reuse existing dispatch, delivery recovery, support, performance, notification, refund and settlement domains. Do not create financial actions merely to populate a dashboard. Existing support tickets have description/category/priority/status, order/delivery references and resolution/triage fields. Conversations, assignment, internal notes, private attachments and controlled escalation need extensions. Existing requester/admin serializers are not evidence that current notes are private: historical content needs explicit visibility review.

Existing public image upload is not a safe private-ticket evidence service. Existing order/delivery history is not equivalent to a comprehensive administrative audit trail. Screens must not claim either capability until its contract exists.

## 3. Navigation and authority

### Normal Admin workspace — operational work

Proposed destinations: Overview; Tickets; Orders & Deliveries; Merchants; Riders; Customers. Catalogue/Media appears only when an implemented capability and operational need support it. Each destination may group existing routes; no new route is asserted here.

Overview answers “What needs attention now?” in this order: actionable unassigned tickets; eligible delivery incidents; onboarding reviews; waiting-internal work; my assigned workload. “Overdue” appears only after response-target policy and clock semantics are approved. Before that use oldest waiting with an authoritative timestamp, never an invented overdue badge.

No normal-admin financial mutation controls. Scoped financial summaries can appear within an authorized ticket/order only when the server explicitly permits them. Do not expose platform-wide settlement/ledger summaries by assuming all admins may read them.

### Super Admin workspace — governance work

Proposed destinations: Governance Overview; Administrators; Roles & Access; Restricted Escalations; Audit Activity. Financial Visibility and System/Integration Health are conditional on implemented source contracts and explicit permission. A separate “Open operations workspace” action avoids a cluttered superset dashboard.

Overview order: critical restricted escalations; administrator/invitation issues; failed obligations or integration issues with actual sources; recent high-risk audit events; links into operations. Do not call audit events “anomalies” without an authoritative detection signal.

### Shared rules

Navigation reflects server-resolved capabilities plus scope; role labels alone are insufficient. Until capabilities load, show a loading state without briefly exposing privileged actions. On revocation, remove unavailable destinations, explain loss of access and clear protected data from display. Distinguish expired session, authenticated-but-forbidden, unavailable service and missing resource. Do not reveal sensitive resource existence to unauthorized users.

A disabled action needs a useful explanation only where revealing the action is authorized. Hide irrelevant privileged destinations; an authorized user encountering a business-rule block sees the reason. Direct-link denial must match backend enforcement. Cached permissions never authorize writes. There is no “act as merchant/rider” shortcut around financial restrictions.

## 4. Shared component map — proposed, not created

Reuse established Button, FormField, Notice, Loading, Empty, Retry and connectivity patterns; do not duplicate saved Figma foundations. Extend only after their QA.

| Proposed component | Purpose / essential properties | State coverage |
|---|---|---|
| AdminWorkspaceNavigation | authorized destinations, current destination, scope, session | loading, active, focus, forbidden, revoked |
| AdminContextHeader | workspace name, authorized scope, session identity | long name, expired session, compact |
| OperationalQueueSummary | source-backed count, definition, timestamp, destination | ready-zero, ready-positive, unknown, stale, loading, error |
| GovernanceAttentionItem | actual event, severity, authorized action, provenance | acknowledged only if supported, unavailable, restricted |
| TicketInbox / TicketRow | reference, requester type, safe subject, state, assignment, timestamp | filters, empty, partial, stale, error, selected |
| TicketContext | allowed order/store/delivery links; minimal requester data | unavailable reference, forbidden reference, redacted |
| TicketConversation / TicketMessage | public/internal visibility, actor, timestamp, attachment access | pending, sent, failed, redacted, long text |
| TicketComposer | explicit communication mode, draft, send callback | public, internal, submitting, failure, revoked |
| TicketAssignment | eligible admin/queue, current owner, expected version | unassigned, search, saving, conflict, no eligible owner |
| TicketEscalation | reason, eligible destination, ownership outcome | submitting, escalated, failure, destination unavailable |
| TicketResolution | permitted transition, public summary, related-workflow status | validation, pending, conflict, confirmed |
| PrivateEvidence | attachment metadata, authorized access, processing state | processing, available, rejected, expired, denied |
| AdministratorList / AdministratorDetail | lifecycle, assigned role, safe activity metadata | invited, active, suspended, revoked, unavailable |
| AdministratorActionReview | target, exact effect, reason, step-up requirement | review, challenge required, pending, denied, conflict |
| RoleCapabilitySummary | canonical capability groups, scope, protected flags | read-only, authorized editing only if implemented |
| AuditActivity / AuditEventDetail | actor, action, safe change, reason, time, correlation | loading, empty, filtered, redacted, error |

These are architectural names. Use existing Figma names for reused primitives; do not rename existing sets solely for consistency. Selected/error/loading are semantic states, not decorative variants. No arbitrary new token palette, radii or motion is authorized.

## 5. Unified ticket inbox and detail

One inbox serves CUSTOMER, MERCHANT and RIDER contexts. Filters: requester type, implemented status, queue, assignee, supported priority and category. Filter values must come from canonical enums/eligible data. Show active filters and a clear reset. Page counts are not total counts unless a total is supplied. A hidden count due to authorization is not zero.

Desktop detail: readable conversation as the primary region, contextual references and assignment alongside it where space permits. Mobile: summary, conversation, reply, then contextual panels in reading order; one page scroll; no mandatory split pane. Tablet adaptation depends on actual content width. Avoid dense tables that require horizontal page scrolling; use labeled stacked rows.

Default detail exposes ticket reference, requester type, safe subject, status, assignee/queue, created/updated times and authorized linked resources. Do not display full addresses, phones, payment details or proof evidence just because the ticket is assigned. Related-resource access is independently authorized.

### Public replies versus internal notes

Use explicitly labeled “Reply to requester” and “Internal note” modes, with persistent audience text adjacent to Send. Icon and color reinforce text; they never replace it. Internal message rendering states “Internal — staff only.” Requester views do not contain internal content hidden by CSS; it must be absent from their payloads.

Keep drafts separate when switching modes. Never silently move an internal draft into the public composer. Public send uses an explicit public-action label and shows its audience; internal save uses a distinct label. Preserve failed drafts in the current authorized session, but do not promise persistent/offline storage unless implemented. Permission revocation prevents send and removes sensitive content according to session policy.

Pending send remains pending until server confirmation. Retry must use the agreed duplicate-suppression contract; do not append a second message after an uncertain response without reconciliation. Keyboard shortcuts must never send accidentally. No public reply, note, assignment or resolution performs a money mutation.

### Assignment and escalation

Assignment offers only eligible, in-scope active staff/queues. Show current owner and intended destination; submit with the concurrency contract engineering supplies. On conflict, show the new server state and require review; do not overwrite another admin's assignment automatically.

Escalation is a separate property/event, not a replacement primary status. Capture reason and destination, identify current owner and explicitly state whether ownership changes. Do not assume it does. No eligible specialist produces a restricted escalation path under approved routing, not a promise of instant Super Admin attention. Priority comes from authorized triage; requester wording does not grant urgent entitlement.

### Lifecycle display

Proposed canonical primary states from the architecture: OPEN, IN_PROGRESS, WAITING_FOR_REQUESTER, WAITING_FOR_INTERNAL_TEAM, RESOLVED, CLOSED. Reopen is an authorized event returning to OPEN/IN_PROGRESS, not an extra independent permanent state. Assignment, triage and escalation remain orthogonal. Legacy waiting_customer requires engineering compatibility mapping; do not change serialized values in UI alone.

Show only server-allowed transitions. Resolve requires an appropriate public explanation; close/reopen timing remains policy-dependent. A resolved support ticket must not imply its payment/refund has completed. Display related financial state separately using its authoritative source.

## 6. Requester entry points

Customer: order/account help with owned references. Merchant: owned store, onboarding, catalogue or settlement query. Rider: authorized assignment/delivery, proof or COD discrepancy. Use eligible reference selectors; do not ask users to paste unrestricted internal IDs.

All three share public ticket history, reply, permitted attachments and status explanation. They do not see administrator internals, security routing or other actors' unnecessary information. Merchant settlement query and rider COD discrepancy create support records only, never financial authority. Historical rider access needs a contract specifying retained scope before design promises continued address/evidence visibility.

## 7. Administrator lifecycle and access views

Lifecycle proposal: invited → activated/active → suspended or revoked. Display invitation expiry only from the server. Existing identity authentication does not itself activate administrator access. Do not introduce password or MFA setup screens around mechanisms that do not exist.

Create/invite review displays verified identity destination, approved role, authorized scope, expiry if supported, and a clear effect statement. Invite resend/revoke appear only when backed by implemented actions. Suspension and revocation are distinct and require exact policy semantics; neither deletes audit history.

High-risk review identifies target, safe before/after change, required reason and server-required step-up. If step-up is not implemented, mark action unavailable rather than drawing a fictitious security guarantee. Final-Super-Admin protections are server-enforced across concurrent demotion, suspension and revocation. Present a returned protection reason; never provide a UI bypass.

MVP role view is a readable capability summary for ADMIN and SUPER_ADMIN. An arbitrary permission builder, per-user exceptions, specialist-role presets and promotion to Super Admin remain outside MVP until explicitly contracted and reviewed.

## 8. Audit activity

List timestamp, attributable actor, action, resource and outcome only when recorded. Detail can show capability, reason, safe before/after differences, session/source metadata and correlation ID according to access policy. Raw credentials, access tokens, full private notes and unneeded personal data never appear.

Audit is read-only in UI. Do not include delete/edit controls. Do not label it tamper-proof. Domain transition history and administrative audit are labeled separately. Exports and evidence-access logging require explicit contracts and permission; no export button is assumed.

A required audit write failure must leave the mutation unconfirmed/failed and preserve prior state. Do not show success merely because the client submitted a request. Denied-attempt events appear only if actually recorded by the backend.

## 9. Metrics and authoritative sources

| Candidate information | Authority needed | Unsupported/unknown handling |
|---|---|---|
| Unassigned / my tickets | Permission-filtered support aggregate; assignment capability first | Unknown if aggregate unavailable; never count one result page as all tickets |
| Oldest waiting / overdue | Ticket timestamps; approved clock/SLA policy for overdue | Show age only until SLA approved |
| Delivery incidents / failed deliveries | Existing incident/recovery domain; action eligibility | Distinguish open incident from eligible reassignment |
| Merchant onboarding | Existing review state/queue | Omit if no onboarding contract in scope |
| Pending invitations / suspended admins | New administrator lifecycle source | Mark planned until available |
| Failed financial obligations | Authorized existing refund/settlement service state | Restricted access; no retry for normal admin |
| Integration/system health | Actual observations with observed time and scope | Unknown on missing data; stale on expired observation |
| High-risk access changes | Administrative audit events | No invented anomaly score |

Every displayed metric carries a definition, scope, observation time/freshness rule and drill-down that agrees with its filters. Zero is a successful authoritative observation. Unknown, not permitted, stale, partial and failed are different states. No fabricated percentage trends, live badges, response-time promises or vanity totals. Staleness thresholds are contract/product decisions, not guessed timer constants.

## 10. API coordination contract needs

No endpoints are invented in this artifact. Engineering must provide:

1. Effective capabilities and scope, plus unavailable/revoked/session-expired distinctions; no wildcard inference from role name.
2. Allowed actions on each protected resource, including side-effect restrictions for cancellation, return, COD and completion; server denial remains final.
3. Separate requester and staff ticket response schemas and explicit message visibility; historical note policy.
4. Eligible references, assignees and queues; assignment/escalation effect on ownership; canonical enum mapping and conflict response/version semantics.
5. Mutation confirmation and uncertain-result reconciliation behavior for replies, assignments, transitions and access changes.
6. Private evidence size/type limits, processing states, authorized access lifetime and retention.
7. Permission-filtered aggregates with definitions, freshness and partial/unavailable semantics.
8. Lifecycle, revocation, invitation expiry, last-Super-Admin and step-up outcomes.
9. Safe audit fields, pagination/filtering and export authorization if any.

Capability examples in the architecture (`refund.retry`, `delivery.reassign`, `account.suspend`) are coordination references until the engineering registry is delivered. UI labels need not expose capability strings. Ordinary admins cannot invoke financial-effect workflows via a ticket, a generic status editor or another role's interface.

## 11. Responsive, localization and accessibility QA specification

Widths: 320, 360, 390, 768 and1440. Reuse established mobile16/tablet24/desktop32 gutters and1180 max content width. At320, preserve48×48 targets, stack field/control groups, and keep primary action reachable above the keyboard. No fixed-height messages or truncated essential addresses, permissions, errors or audience text. Desktop can increase useful queue density, not shrink interaction targets.

Run EN/HI/MR fixtures with30–50% expansion, mixed-script names, long ticket subjects, full reasons, timestamps and large amounts. Use200% text tests and web zoom. Translations require native review; these proposed navigation terms are not final approved translations.

Keyboard: navigation current state, row links, filters, composer audience controls, eligible-assignee selection, dialog focus trapping/restoration and visible ring. Selected state uses text/icon/shape in addition to color. A disabled privileged action cannot be re-enabled by keyboard or stale selection.

Screen reader: ticket/message heading hierarchy, audience included in message/composer semantics, associated field errors, current status independent of color, restrained live announcements. Do not announce every queue polling refresh. Loading preserves known content and focus. Public/internal mode switches explicitly announce audience.

Resilience: independent queue loading, partial summaries, no results versus no permission, offline read-only data only where actually cached, stale timestamps, failed sends, concurrent edits, revoked session, attachment rejection/expired link, no eligible assignee and failed audit-backed mutation. No automatic offline financial writes or replay promises.

QA result today: all Figma visual/state/responsive/localization checks **NOT VERIFIED / BLOCKED**. Prior foundation implementation tests are narrower evidence and do not approve these proposed governance screens.

## 12. Figma-ready organization and exact design sequence

Preserve exactly Readme, Foundations, Future Work. No new file/pages or duplicate variables. In Readme add governance decisions/authority notes only after editing is allowed. In Future Work → Operations, use nested frames/sections for Operational Admin, Governance, Tickets, Administrator Access, Audit and QA. Customer/Merchant/Rider support entry specimens can be referenced from their existing reserved sections without duplicating shared patterns.

Sequence:

1. Restore access through legitimate allowance restoration; read-only inventory first. Do not retry while the STOP remains in effect.
2. Fix/verify saved Button and Field; QA Notice/Loading/Empty/Retry/connectivity and required IconButton before composition.
3. Confirm canonical capability/action/source mapping with engineering; obtain IA acceptance for remaining material decisions.
4. Shared workspace navigation and context header permission states.
5. Ticket row/inbox/detail and public/internal composer primitives.
6. Assignment/escalation/resolution and conflict states.
7. Private evidence states after media contract; requester context specimens.
8. Administrator lifecycle/access review and audit components.
9. Compose operational dashboard from authoritative queues; then governance overview from restricted attention items.
10. Execute full width/language/keyboard/large-text/permission/resilience matrix and record actual results per frame.

Suggested frame naming: `Operations/{Workspace}/{Surface}/{Width}/{Language}/{State}`. Use instances of approved components. No high-risk confirmation screen is claimed secure solely because it has a confirmation button.

## 13. Material decisions remaining

- Account suspension/restoration policy and exact authority.
- Scope of operational financial visibility; financial-effect writes remain denied to normal admins by default.
- MFA/step-up, recovery/succession and any dual-approval requirement.
- Regional/queue scope, restricted-queue staffing and escalation ownership changes.
- Response targets, close/reopen rules and priority definitions.
- Retention/anonymization for ticket history, internal notes and evidence; historical note visibility.

Routine design preparation can continue. These decisions block only dependent detailed workflows; they do not block documenting empty/error/permission states or enforcing approved backend denials.

## 14. Window 1 handoff and acceptance

Immediate engineering slice: capability enforcement, financial-effect denial and attributable transactional audit. No new dashboard is a prerequisite. Preserve customer/merchant/rider ownership/business flows and duplicate-route precedence protections.

Design acceptance for later interfaces: every action maps to a canonical capability and resource rule; all displayed fields have an authoritative contract; normal admins have no financial-effect execution path; internal content never reaches requester payloads; unknown never appears healthy/zero; pending never appears successful; cancellation/return does not bypass financial authorization; all controls use approved foundations.

Security/API tests remain engineering-owned. Visual approvals remain design-owned. Exact-SHA CI, review, integration and deployment gates remain Master Control/Git-owned. This artifact neither authorizes a merge nor claims visual completion.

**HANDOFF STATUS: written IA/specification ready for review. FIGMA VISUAL QA: BLOCKED. ENGINEERING SCREEN APPROVAL: NOT GRANTED.**

## 15. Coordination checkpoint — 11 September 2026

Read-only checkout inspection now identifies `gaonone-governance-security`, branch `feat/governance-capability-enforcement`, at `8b230b5e61046f35c813a8ed82aaf5e4166038c9`, with a clean working tree at inspection. This supersedes the old foundations checkout as the engineering coordination baseline, not as evidence that governance features have shipped. No capability/permission/governance-named application source file or effective-capability field was found in the narrow paths searched. This is a bounded observation, not an exhaustive absence claim.

IMPLEMENTATION is active again; no canonical capability response has yet been received by this design task. Consequently all proposed capability names and new ticket/lifecycle response requirements remain pending. Do not implement UI against illustrative names from this document.

### Contract acceptance ledger

| ID | Engineering confirmation needed | Design consumer | Current status |
|---|---|---|---|
| GOV-01 | Effective capabilities, scope and revocation response | Both workspace navigations | PENDING |
| GOV-02 | Explicit action eligibility and financial side effects | Order/ticket contextual actions | PENDING |
| GOV-03 | Staff/requester schemas and historical visibility policy | Conversation and internal notes | PENDING |
| GOV-04 | Eligible assignment/escalation targets and conflict semantics | Assignment/escalation review | PENDING |
| GOV-05 | Canonical ticket transitions and public resolution requirements | Status controls | PENDING |
| GOV-06 | Invitation, suspension, revocation, step-up and final-admin protection | Administrator lifecycle | PENDING |
| GOV-07 | Private attachment lifecycle and authorized download | Evidence component | PENDING |
| GOV-08 | Safe audit schema and query scope | Audit views | PENDING |
| GOV-09 | Metric definitions, scoped totals and freshness | Dashboard summaries | PENDING |

Design may continue refining written state coverage using these explicit dependencies. Visual composition remains blocked until legitimate Figma access restoration and foundation QA. No Figma request was attempted at this checkpoint.

## 16. API-to-UI traceability — accepted IA, contracts still gated

Master Control has accepted this information architecture direction with unresolved policy boundaries; this is not visual acceptance. The following route/schema observations were read directly from the governance checkout on11 September2026 at baseline `8b230b5e61046f35c813a8ed82aaf5e4166038c9`. Engineering is active; future candidate changes supersede these observations only after its explicit handoff. Paths below are relative to the configured API v1 base.

### A. Current endpoints affected by the security slice

| Existing API | Confirmed current contract or effect | UI consumer and required behavior | Security-slice dependency |
|---|---|---|---|
| GET /users/me | UserResponse has id, phone, full_name, role, is_super_admin, is_active, is_verified, created_at, updated_at; no effective-capability field in inspected schema | Session context can show known identity. Do not build capability-aware navigation by treating role as a complete permission list | Backend guards can ship independently; capability discovery response requires explicit later confirmation |
| GET /admin/users; PATCH /admin/users/{user_id}/role | Existing user administration route family | Existing interface must handle denial; not an invitation/session lifecycle contract | Canonical admin-change capability and restrictions from engineering |
| GET /admin/deliveries/active and /failed; POST /admin/deliveries/{delivery_id}/assign and /unassign | Existing delivery queues/actions | Operational queue links; preserve actual assignment rules and denied-action recovery | Engineering confirms non-financial action scopes and guarded duplicate paths |
| POST /admin/refunds/{refund_id}/retry | Existing refund-dispatch mutation | No ordinary-admin retry action; denied requests must not look successful | Financial-effect denial; exact registry capability pending |
| PATCH /merchant/orders/{order_id}/status | Existing merchant/admin status mutation, potentially refund-triggering cancellation | No admin role-switch bypass; no generic status dropdown granting unsupported authority | Classify actual downstream effect; preserve legitimate merchant workflow |
| POST /admin/deliveries/{delivery_id}/recover and /resolve-failure | Existing controlled failure handling; return resolution can affect finance | Reassignment eligibility differs from restricted return resolution; escalation request does not execute return | Engineer-owned side-effect authorization and transactional audit |
| POST /delivery/{delivery_id}/cod-collection and /complete | Existing COD evidence/completion flow; completion has hardened and legacy definitions | Ordinary admin cannot obtain execution authority via ticket context; legitimate assigned-rider workflow remains intact | Guard all registered/bypass paths, preserve proof/COD/business checks |
| GET /orders/{order_id}/events | Existing domain transition history | Label as order/delivery history, not comprehensive governance audit | New admin audit persistence does not imply a new audit-query API |

This table identifies existing surfaces for coordination; it is not evidence that the new enforcement is implemented or tested. No new financial action or frontend redesign is needed to enforce denials. Canonical capability strings remain engineering-owned and intentionally unspecified here.

### B. Current support/overview APIs versus future UX

| Existing source | Confirmed fields/limits | Supported interpretation | Future dependency / must not infer |
|---|---|---|---|
| POST /support/tickets | subject3–180, description5–5000; optional order_id and delivery_id | Existing ticket creation with current ownership rules | Store reference, requester type, attachment and merchant/rider-linked authorization need extensions |
| GET /support/tickets/me | Most recent up to200 requester records | List returned tickets; show permitted existing content | No total count/pagination guarantee; no conversation or private-message contract |
| GET /admin/support/tickets | Most recent up to500 records | Existing staff queue | Do not label returned length total platform backlog; no assignment/queue/SLA fields |
| Ticket serializer | id, user_id, order_id, delivery_id, subject, description, category, priority, status, triage_summary, suggested_action, resolution_notes, created_at, updated_at, resolved_at | Existing ticket data; triage is a suggestion | resolution_notes/triage are currently shared, not private internal notes |
| PATCH /admin/support/tickets/{ticket_id} | status: open/in_progress/waiting_customer/resolved/closed; optional resolution_notes max1000 | Existing update contract only | No version field, explicit transition policy, assignment, messaging or escalation API inferred |
| GET /admin/overview | users, villages, active_stores; merchants.pending/approved/suspended; orders.total/by_status; operations.low_stock_listings/ready_unassigned_deliveries/active_delivery_partners; paid_gmv/gross_order_value | Actual aggregate definitions available for review | No ticket aggregates, freshness timestamp, regional scope or health telemetry. Financial visibility policy must filter data server-side |

The client may record “Loaded at” using its receipt time, clearly distinguished from server observation time. It must not invent “Live,” “Healthy,” “Up to date,” overdue thresholds or an authoritative as-of timestamp. `paid_gmv` is a source aggregate, not a license to expose it to ordinary admins.

### C. Future contracts — outside the current boundary-enforcement slice unless engineering explicitly adds them

| Future contract | Proposed UI | Blocking decision/technical dependency |
|---|---|---|
| Effective capabilities and resource action eligibility | Capability-aware navigation/actions | Registry names, scope and revocation semantics; no permission decision inferred from UI |
| Separate staff/public ticket schemas and messages | Conversation, public reply/internal note composer | Historical visibility and retention; server-side audience separation |
| Assignment, escalation, optimistic concurrency | Owner/destination review and conflict recovery | Eligible queues, staffing, ownership-change policy and version behavior |
| Controlled ticket transitions | Resolve/close/reopen | Close/reopen policy, canonical enum compatibility and public-summary requirement |
| Private attachment lifecycle | Evidence preview/download | Shared private media, retention and access scope |
| Invitations, session revocation and step-up | Admin lifecycle/high-risk review | Authentication mechanism, recovery, final-admin protection and suspension policy |
| Scoped administrative audit query | Governance audit list/detail | Safe fields, read capability, retention/export policy |
| Permission-filtered dashboard summaries | Operational/governance overview | Metric definitions, financial read scope, freshness and partial-source behavior |

### D. Verified responsive token trace

Values were checked against `GaonOne-Design-System-Specification.md`, token table lines614–634, not freshly read from Figma:

| Figma token | Saved specification value | Application mapping |
|---|---|---|
| target/min |48px | --go-target-min |
| target/primary |56px | --go-target-primary |
| layout/gutter/mobile |16px | --go-layout-gutter-mobile |
| layout/gutter/tablet |24px | --go-layout-gutter-tablet |
| layout/gutter/desktop |32px | --go-layout-gutter-desktop |
| layout/content/max |1180px | --go-layout-content-max |
| layout/viewport/320, /360, /390 |320/360/390px | Corresponding --go-layout-viewport-* |
| layout/viewport/tablet, /desktop |768/1440px | Corresponding --go-layout-viewport-* |

These viewport values are QA specimens, not approved breakpoint modes. The earlier specification proposes a768/1200 breakpoint policy for review; this governance handoff does not promote that proposal into a confirmed token or implementation requirement. Layout must preserve48px targets and fluid localized content at every test width. Figma bindings/rendering remain NOT CHECKED.

### E. Decision routing without blocking security enforcement

Proceed independently with approved ordinary-admin financial-effect denial, ownership preservation and attributable transactional audit. Design makes no new policy prerequisite for those controls.

Hold only dependent UX: financial summaries await read-scope policy; account suspension screens await suspension rules; privileged challenges await step-up/recovery choice; escalation ownership and overdue badges await staffing/SLA policy; internal-note/evidence rollout awaits historical visibility/retention; new dashboards await confirmed response contracts and visual QA. No implicit normal-admin finance delegation is introduced while decisions remain open.

## 17. Baseline correction — Master Control verified Git investigation

Master Control confirms that main `8b230b5e61046f35c813a8ed82aaf5e4166038c9` contains documentation changes over `5528f86`; foundations commit `ae36c301` was **not integrated**. The former foundations worktree is reported empty except for a broken `.git` reference. Git Control is recovering its committed snapshot separately; prior uncommitted refinements are unavailable in that folder.

All references in this handoff to shared foundation implementation and its previous tests describe the historical candidate, not components verified present on current main. The external specification remains a written design reference. It does not establish recovered code, current-main availability, successful integration or visual acceptance. Reuse requires verification against Git Control's recovered candidate before implementation. No recovery or repository mutation was performed by this design task.

Written handoff is complete. Await canonical engineering contracts for a targeted matrix update; do not duplicate the deliverable or retry Figma while blocked.

## 18. Frozen engineering capability subset — CANDIDATE / UNMERGED

Source: Master Control's frozen engineering dispatch, corroborated by read-only inspection of `backend/app/core/capabilities.py`, `schemas/user.py` and the users/admin route files in `gaonone-governance-security`. IMPLEMENTATION's latest three turn records were accessible but returned no message items, so this update relies on the explicit dispatch and inspected source rather than inventing missing handoff text. No exact frozen candidate commit SHA was supplied here. This section supersedes pending/absence observations in sections15–16 for the subset below only. It does not establish merge, deployment, visual acceptance or runtime QA.

### Confirmed candidate API-to-UI mapping

| API / capability | Candidate contract | Design implication |
|---|---|---|
| GET /api/v1/users/me/capabilities | `{is_super_admin: boolean, capabilities: string[]}`; names sorted in response | Fetch this separate endpoint for navigation capability discovery. Existing GET /users/me remains unchanged. Loading/error must not transiently expose privileged actions. No region, queue, resource-level allowed-actions or session epoch field is provided. |
| GET /api/v1/admin/overview | Adds `financials_visible`; ordinary-admin `paid_gmv` and `gross_order_value` are null | Suppress financial summaries when false; null is restricted/unavailable, never ₹0. Do not offer case-linked financial inspection to normal admins in this slice. |
| GET /api/v1/admin/audit-events | Requires audit.read, currently Super Admin only; limit default100/max500 and offset≥0 | Governance audit list can be specified against this paginated list. No total count, search/filter/export or retention interface is implied. |
| PATCH /api/v1/admin/users/{user_id}/role | Requires admin.manage; user role/status mutation Super Admin only; verification preserved | Ordinary-admin account screens are read-only. No suspend/restore control pending a future explicit delegation. Existing is_verified must not be changed as a side effect or described as newly verified. |

### Exact current capability registry mapping

Normal ADMIN receives these12 capabilities:

- `user.read`: operational user inspection; does not authorize role/status edits.
- `merchant.read`, `merchant.manage`: existing merchant operations under server rules.
- `catalog.manage`: existing catalogue surface only.
- `geography.manage`: existing geography operations only.
- `order.read`, `order.operations`: order inspection/operations; financial-effect restrictions still apply.
- `rider.read`, `rider.operations`: rider/assignment operations; not financial completion authority.
- `support.manage`: existing ticket handling, not new messaging/assignment/escalation contracts.
- `media.moderate`: existing media authority, not a private evidence service.
- `notification.operations`: existing notification operations, not new ticket-event subscriptions.

SUPER_ADMIN adds8 explicitly mapped capabilities: `admin.manage`, `payment.read`, `refund.read`, `refund.write`, `settlement.read`, `settlement.write`, `delivery_financial.write`, `audit.read`.

`user.manage` is declared in the registry but granted to neither current administrative set. Do not create a UI action conditioned on its presumed availability. There is no wildcard or automatic entitlement to future capabilities. Marketplace customer/merchant/rider roles resolve no administrative capabilities through this endpoint; their existing ownership-based business workflows remain separate.

Illustrative earlier names such as `refund.retry`, `delivery.reassign`, `account.suspend` or granular ticket capabilities are **not canonical for this slice**. Use the registry above only after candidate integration and engineering confirmation for each action. Capability presence is not a substitute for server business rules, proof requirements, resource ownership or current authorization.

### Superseded design assumptions and precise deferrals

- Normal Admin has **no financial read or write capabilities**, including scoped case financial grants. Prior proposed ticket-scoped financial summaries remain deferred, not enabled by this handoff.
- Ordinary-admin user-role/status mutation is excluded. Suspension/restoration delegation is a future policy/API decision, not a prerequisite for current enforcement.
- Audit read now exists in the candidate, so GOV-08 moves from wholly pending to **candidate subset mapped**. Retention, export, search and scope extensions remain pending.
- GOV-01 moves to **candidate capability discovery mapped**; resource-level actions, scopes and session-epoch semantics remain pending.
- GOV-02 remains action-by-action engineering validation: the registry is supplied, but no generalized resource `allowed_actions` payload is present.
- GOV-03/04/05/06/07 remain future contracts: no new ticket workflows, private conversations, assignment/escalation, private attachments, invitations, MFA or session epoch are established here.
- GOV-09 moves to **candidate financial visibility mapped**; no new ticket aggregates or authoritative freshness/health observations are implied.

### Audit assurance wording

The candidate audit trigger protects UPDATE/DELETE. It does not protect against database-owner DDL or TRUNCATE. Describe the view as administrative audit history with protected application mutation paths, never tamper-proof or immune to infrastructure administrators. Super Admin UI must not offer edit/delete controls. Audit retention/export policy remains unresolved.

### Remaining gate

The current backend security slice can proceed through its engineering/release gates without visual implementation. The design ledger is now aligned to its frozen subset. Wait for an exact candidate/integration handoff before calling these contracts current-main or deployed. Foundation recovery and visual QA remain independent blockers for composed UI approval. Figma calls remain stopped.
