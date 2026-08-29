# GaonOne Automation Mode

## Goal

Run development as a controlled engineering pipeline where agents implement bounded tasks, CI validates them, review checks correctness, and only green `main` commits deploy to the current staging server.

## Branch and deployment model

- `main`: deployable integration branch; every accepted merge is a staging release candidate.
- Feature branches/worktrees: all implementation work.
- Pull requests: required review/CI boundary before integration.
- Current server: staging only.
- Existing `.env.production`, `docker-compose.prod.yml`, `backend/Dockerfile.prod`, and `web/Dockerfile.prod` remain in use because they provide production-grade build/runtime behavior; their legacy naming does not make the server production.

## Automated execution loop

1. Select the highest-priority unblocked item from `docs/AUTOMATION_BACKLOG.md`.
2. Inspect existing implementation, schema, tests and API contracts before changing code.
3. Implement one coherent vertical slice on a feature branch/worktree.
4. Add or update tests and migrations as required.
5. Run repository validation locally/agent-side when available.
6. Push the branch and let GitHub Actions run backend, web, mobile and release-image gates.
7. Perform a review pass focused on authorization, state machines, concurrency, data integrity, security and regression risk.
8. Merge only when required checks are green.
9. `main` triggers the staging deployment workflow.
10. Staging deployment verifies the exact `main` SHA, creates a database backup, builds production-grade images, applies migrations, recreates services, runs smoke checks and runs server monitoring.
11. Record the deployed SHA. If staging validation fails, the release is rejected and the next action is diagnosis/fix, not promotion.

## Parallel agent lanes

Parallel work is allowed only when files and domain ownership are sufficiently independent. Recommended lanes are backend commerce/order, delivery/dispatch/tracking, Flutter customer/merchant/delivery surfaces, web/admin, and QA/security. Cross-domain schema/state-machine changes should be serialized through the domain owner task to avoid conflicting assumptions.

## Human approval boundary

Normal application changes, tests, safe additive migrations, docs and staging deployments may flow through the automated pipeline. Explicit approval is required before destructive database operations, database restore, credential rotation, persistent-volume deletion, firewall/network changes, live payment credential changes, irreversible infrastructure changes, or declaring a real production environment live.

## Migration policy

Prefer expand/contract migrations. Staging releases must not depend on destructive backward-incompatible schema changes when an additive path exists. Automatic database rollback is intentionally disabled: restoring a database is a destructive operational action and may discard staging data. Code rollback can be prepared separately against the recorded previous deployed SHA when migration compatibility permits it.

## Definition of done

A task is not done because code was generated. It is done only when the implementation satisfies acceptance criteria, tests cover the critical behavior, migrations are valid, CI is green, review findings are resolved, and the resulting integrated build behaves correctly on staging when the change reaches `main`.
