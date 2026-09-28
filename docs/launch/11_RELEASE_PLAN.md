# Release plan

## Policy target

Merge validates source; it does not authorize staging or production deployment. A designated release action must select an exact green SHA after explicit owner authorization.

## Prior P0 discrepancy

The repository source previously contained a staging workflow triggered by `main` pushes. That contradicted the target manual/explicit-release policy. Phase 2A remediated it to manual dispatch only; PRs #182–#184 merged without deployment.

## Candidate release checklist

1. Verify candidate is current `origin/main` and all four required CI gates are green.
2. Verify protected local-main owner modifications are accounted for and untouched.
3. Confirm backend/web/mobile/security/accessibility/visual evidence and owner-dependent Firebase setup.
4. Record exact SHA, check URLs, deployment authorization, backup/smoke/monitor evidence, and deployed SHA.
5. Deploy only with explicit owner authorization; no automatic destructive rollback.

Current status: no candidate and no deployment authorization.
