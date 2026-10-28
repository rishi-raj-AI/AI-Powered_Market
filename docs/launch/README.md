# GaonOne launch control plane

This directory is the durable operating record for the launch-critical MVP. Read these files before changing launch work:

1. `LAUNCH_STATUS.md` — current dashboard and safe resume point.
2. `15_SESSION_HANDOFF.md` — exact last-session state.
3. `14_DECISION_LOG.md` and `12_RISK_REGISTER.md` — decisions and unresolved risks.
4. `V1_READINESS_AUDIT.md`, `EXTERNAL_DEPENDENCY_REGISTER.md`, and `OWNER_ACTIONS_REQUIRED.md` — current evidence boundary, provider/dependency inventory, and human-only actions.
5. `V1_MANUAL_TEST_PLAN.md`, `V1_BUG_BACKLOG.md`, and `V1_RELEASE_CHECKLIST.md` — acceptance evidence, triage, and candidate-release gates.
6. The relevant plan, journey, or acceptance-matrix document.

States: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `READY_FOR_REVIEW`, `DONE`, and `DEFERRED`. `DONE` requires applicable evidence, not merely code.

Scope: launch-control documentation does not itself authorize deployment, provider activation, paid services, secrets, or production changes. Source changes must remain in isolated, separately reviewed worktrees and preserve the documented authority boundaries.
