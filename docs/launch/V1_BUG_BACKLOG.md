# V1 launch-readiness bug backlog

Updated: 2026-10-28  
Baseline: `ebe389de31d1d473f43a65cbaa41efa53ba0ccea`. The priority labels below distinguish source defects from owner/provider evidence gaps; they do not imply a deployment authorization.

| ID | Priority | Area | Finding | Classification | Safe disposition |
|---|---|---|---|---|---|
| V1-001 | P1 | Release backup | `deploy/backup.sh` previously needed a running API container to archive media while `release.sh` runs backup before building/starting services. | Remediation in review | PR #221 head `c1deb71566bb2feb661f43d5139d580aaa070588` uses a one-shot `--no-deps` API-image container and regression test. Fresh CI/review is required; retain backup-before-migration, forward-only migration/rollback, and named-volume safety. No deployment. |
| V1-002 | P1 | Release control | Proxy startup and mandatory non-secret SHA/environment selectors are available only in open PR #221, not current `main`. | Open reviewed PR / owner approval | Keep #221 unmerged until explicit normal review/approval. Never install it or deploy from this audit. |
| V1-003 | P1 | Environment control | Source wording calls the live host staging while runtime filenames and validation say production; workflow label is staging. | Owner decision | Designate the environment and approval policy before operating it. |
| V1-004 | P0 | Firebase identity | Required Firebase server config, Google provider, exact OAuth origins, and real provider acceptance evidence are absent. | Owner/provider dependency | Secure owner setup and real-domain exchange tests; no secrets in source. |
| V1-005 | P0 | Android release | Release build uses debug signing, so a trustworthy signed distribution/Firebase SHA acceptance path is not evidenced. | Owner signing/distribution dependency | Choose keystore/Play path and test signed internal build. |
| V1-006 | P0 | iOS identity | Xcode uses `in.gaonone.gaononeMobile` while Flutter Firebase options use `in.gaonone.gaonone_mobile`; no Google URL scheme was found. | Owner decision/configuration defect | Choose canonical ID then configure Firebase/Apple/callback and test physical device. |
| V1-007 | P1 | Deployment provenance | Public health is good but reports version `0.4.0`; the source default is `0.5.0`, and no authorized host SHA inspection was available. | Owner/server evidence gap | Inspect actual checkout HEAD and `.deployed-sha` without exposing secrets. |
| V1-008 | P1 | Backup/observability | No off-host backup retention, restore drill, alerting, or log-retention evidence was supplied. | Owner operations dependency | Select owner/provider and prove restore/alert paths. |
| V1-009 | P1 | Maps | Google Maps configuration and restrictions are absent; exact map feature scope is undecided. | Owner product/provider decision | Decide feature criticality; configure/restrict keys only if enabled. |
| V1-010 | P2 | FCM push | Server outbox supports FCM but web/Flutter clients have no device registration/messaging integration. | Deferred engineering scope | Keep unconfigured; plan client + APNs/push lifecycle separately. |
| V1-011 | P2 | Merchant media | Upload UI is not evidenced as attaching a catalogue image to customer-visible content. | Product/engineering scope gap | Defer/clarify UI or build reviewed attachment flow. |
| V1-012 | P2 | SMS | MSG91 code exists but Firebase V1 correctly disables it; DLT/template/account/billing evidence is absent. | Optional provider dependency | Do not enable without an approved future scope. |
| V1-013 | P2 | Payments | Razorpay code is available but provider account/KYC/test acceptance/webhook evidence is absent. | Optional provider dependency | COD remains V1 default; enable only through a separate tested decision. |
| V1-014 | P2 | Third-party telemetry | No analytics/crash-reporting provider is configured. | Optional product/operations decision | Treat as future privacy-reviewed work, not a release blocker by itself. |

## Triage rules

- A P0 blocks a release candidate. A P1 blocks release unless explicitly risk-accepted by the owner. A P2 is deferred only when the related surface is removed, disabled, or accurately scoped.
- Do not close a provider/deployment issue based only on static code or a CI build.
- Keep remediation changes isolated from provider secrets, production configuration, and unrelated product work.
- Link any future PR, owner evidence, and exact candidate SHA here before marking an item mitigated.
