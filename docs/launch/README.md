# GaonOne launch control plane

This directory is the durable operating record for the launch-critical MVP. Read these files before changing launch work:

1. `LAUNCH_STATUS.md` — current dashboard and safe resume point.
2. `15_SESSION_HANDOFF.md` — exact last-session state.
3. `14_DECISION_LOG.md` and `12_RISK_REGISTER.md` — decisions and unresolved risks.
4. The relevant plan, journey, or acceptance-matrix document.

States: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `READY_FOR_REVIEW`, `DONE`, and `DEFERRED`. `DONE` requires applicable evidence, not merely code.

Scope: documentation/control-plane work only in this PR. It neither authorizes deployment nor changes authentication, UI, media, or release automation.
