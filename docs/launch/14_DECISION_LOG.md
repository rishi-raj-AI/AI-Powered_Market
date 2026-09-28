# Decision log

| ID | Date | Decision | Reason / alternatives | Consequence | Reversible / revisit |
|---|---|---|---|---|---|
| AUTH-001 | 2026-09-28 | Firebase Google Sign-In is MVP auth for web and Flutter | DLT blocks convenient SMS; retain SMS as future option | Firebase integration is launch-critical | Yes; revisit after compliant SMS activation |
| AUTH-002 | 2026-09-28 | Firebase proves external identity; GaonOne owns accounts, roles, ownership and business state | Do not move domain authorization to Firebase | Server-side authorization remains unchanged | No without architecture decision |
| AUTH-003 | 2026-09-28 | Issue/use GaonOne backend sessions after Firebase ID-token verification | Fits existing route/session architecture | Domain routes do not depend on client Firebase state | Yes; revisit with measured need |
| AUTH-004 | 2026-09-28 | Disable SMS auth for MVP; preserve provider/module boundary | DLT deferred; avoid destructive removal | SMS reactivation remains possible | Yes after compliance |
| AUTH-005 | 2026-09-28 | Require MSG91 config only when SMS auth + MSG91 are selected | Correct conditional configuration | Validation and CI must change | Yes |
| AUTH-006 | 2026-09-28 | SMS routes cannot remain callable when SMS requirements are disabled | Prevent authentication bypass | Explicit route gating/removal required | No while SMS disabled |
| AUTH-007 | 2026-09-28 | Development OTP must be impossible in production | Fail closed | Production tests required | No |
| RELEASE-001 | 2026-09-28 | Deployment must be separate from merge; automatic staging-on-main is a P0 discrepancy | Explicit release authorization policy | Remediate workflow before normal launch merges | Yes after verified replacement |
| MEDIA-001 | 2026-09-28 | Defer Product-media B2+ during launch sprint | Not proven launch-blocking | Preserve isolated worktree | Yes |
| MEDIA-002 | 2026-09-28 | Do not extend legacy `/media/images` merchant UI for StoreProduct media | Conflicts with listing-owned media design | Keep legacy surface out of B2 scope | No without superseding media decision |
| UX-001 | 2026-09-28 | Audit/improve functional surfaces; no wholesale redesign | Protect delivery schedule and working paths | Shared patterns first | Yes |
| UX-002 | 2026-09-28 | No launch-polished claim without visual QA | Static inspection is insufficient | Evidence is a release gate | No |
