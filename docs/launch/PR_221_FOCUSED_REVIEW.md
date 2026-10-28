# PR #221 focused review — 2026-10-28 20:35 UTC

Status: **changes required; not approved for merge or deployment**.

## Exact-head CI evidence

- PR #221: `c1deb71566bb2feb661f43d5139d580aaa070588`.
- PR #222: `c0ee58c068f892c76c5c6b6c9fc794a61fc73f81` before this documentation update.
- All four required gates completed successfully on both heads: `backend-check`, `build-and-ui`, `analyze-and-build-android`, and `production-compose-and-images`.
- No submitted GitHub reviews were present when inspected. Green CI is not owner approval, host validation, or deployment evidence. This documentation update needs fresh checks on its resulting head.

## P1: protected-parent failures do not fail closed

In `deploy/release.sh`, `assert_secure_release_checkout` is invoked as an `if !` condition. Bash disables implicit errexit within that function context. Its calls to `assert_root_owned_path /srv` and `assert_root_owned_path "$ROOT_DIR"` lack explicit failure propagation. The subsequent `find` assignment also lacks an explicit error check.

A failing parent assertion can therefore print an error and continue to a successful recursive scan, returning success overall. The recursive scan of the checkout does not validate its parent. If the parent becomes writable after installation, a caller can replace the protected child path; the intended privilege boundary must not rely on the install-time check alone.

Reproduction used the exact assertion function bodies from the inspected head, changing only the fixed path to a disposable fixture. A fake `stat` reported a root-owned, mode-777 parent and mode-755 checkout; a fake `find` returned a clean scan. The same `if ! assert_secure_release_checkout` call printed the parent rejection but accepted the checkout (test exit 42). No actual root-owned paths or permissions were changed.

Required remediation: explicitly propagate every parent/root assertion and scan failure, including at initial, post-sync, and rollback validation. Add regressions for insecure parent/root paths and failed filesystem inspection. Existing tests always report root/755 from their stat fixture and do not cover this failure.

## P1: two labels bypass mutual exclusion for one checkout

Both valid labels operate on fixed `/srv/gaonone`, the same Compose project, and the same persistent resources. However, the lock pathname contains `${ENVIRONMENT}`. The documented production invocation and the staging workflow can acquire different locks concurrently and interleave reset, backup, build, migration, startup, and rollback.

Required remediation: use one protected lock for the shared release target, independent of its logging label. Preserve explicit staging/production labels and the workflow's existing staging designation. Add a real two-process lock contention regression across labels; the current fixture replaces flock with unconditional success.

A disposable two-process advisory-lock check confirmed the distinction: while the production lock was held, a child acquired the staging lock (exit 0), whereas a child requesting the same production lock was rejected (exit 1). This checks distinct-file mutual exclusion, not a live deployment.

## Safeguards retained in the reviewed source

- Manual shell assignments and workflow step environment target the same direct no-argument sudo entry point; command-specific env_keep names only the two non-secret selectors, with NOSETENV and no shell/env/Docker grant.
- Expected SHA and explicit staging/production labels are mandatory, and mismatched SHA aborts before migrations or runtime startup.
- Normal and rollback service lists include proxy; runtime startup checks proxy before HTTPS smoke checks.
- Database/media backup remains before migrations; the cold-media path uses a transient no-dependency API container.
- No PostgreSQL volume deletion, pruning, recreation, or automatic schema rollback was introduced.
- Smoke and monitor still depend on the public HTTPS proxy; they prove availability, not an exact deployed SHA.

The sudo tests simulate the environment boundary and parse policy syntax; they do not demonstrate the installed policy on a real server. The backup test simulates Docker and does not prove archive restoreability. Server policy installation and real restore/acceptance evidence remain unverified external actions.

## Next action and boundaries

Resolve the two implementation findings narrowly in `fix/release-proxy-rollback`, then rerun the focused tests and all required gates on the new head before another review. This heartbeat recorded review findings only; it did not change release code. Owner merge and deployment approvals remain separate and mandatory. No server, secrets, production configuration, protected main checkout, or persistent volumes were touched.
