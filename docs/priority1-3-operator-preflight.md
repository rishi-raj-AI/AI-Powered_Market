# GaonOne V1 production operator preflight (read-only until approved)

This runbook targets the existing Ubuntu checkout at `/home/ubuntu/gaonone`
and `docker-compose.prod.yml`. It is **not** a deployment authorization.
Use a staging environment first. Never paste the contents of
`.env.production`, a signing keystore, database backups or provider tokens
into chat, CI logs or pull requests.

## 1. Identify the deployed state without printing secrets

Run on the host with authorized access:

```bash
set -euo pipefail
cd /home/ubuntu/gaonone
test -f .env.production
test "$(stat -c %a .env.production)" = 600
git status --short
git rev-parse HEAD
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T api alembic current
curl -fsS -o /dev/null -w 'API health HTTP %{http_code}\n' https://gaonone.in/api/v1/health
```

Record the Git SHA, current migration revision, container health and HTTP
status in the release evidence ledger. A clean `git status` and HTTP 200
are necessary but do not prove that the deployed image matches the checkout.

## 2. Check safety switches by name and boolean only

Never print the full environment or run `docker compose config` without
`--quiet`. Check only the two rollout switches:

```bash
python3 - <<'PY'
from pathlib import Path
import re
lines = Path(".env.production").read_text().splitlines()
for key in ("AUTO_DISPATCH_ENABLED", "PRODUCT_MEDIA_ENABLED"):
    values = [line.split("=", 1)[1].strip().strip("'\"")
              for line in lines if re.match(rf"^{key}=", line)]
    if len(values) != 1 or values[0].lower() not in {"false", "0", "off", "no"}:
        raise SystemExit(f"FAIL: {key} is missing, duplicated or not disabled")
    print(f"PASS: {key} is disabled")
PY
```

This file check is not a substitute for inspecting the running worker's
effective configuration. Keep both features off until their live acceptance
gates are signed off.

## 3. Back up before any approved migration or deployment

Create an encrypted, access-controlled backup destination according to the
operator's storage policy. A local backup is only an initial safeguard;
verify a restore into a separate test database before release.

```bash
umask 077
mkdir -p /home/ubuntu/gaonone-db-backups
backup="/home/ubuntu/gaonone-db-backups/gaonone-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db \
  sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup"
test -s "$backup"
chmod 600 "$backup"
printf 'Backup created (restricted permissions); verify off-host copy and restore before rollout.\n'
```

Do not upload the backup to public GitHub or share its path as a public URL.

## 4. Deployment and migration (requires separate approval)

Do **not** execute the following during an unapproved preflight. After the
reviewed release SHA is selected, the DB backup is restorable, and a rollback
window is agreed:

- Pin the intended Git SHA and verify the four CI workflows on that exact
  SHA, not merely on an ancestor or another branch.
- Apply migrations using the existing `migrate` compose profile only after
  checking backward compatibility and the DB rollback plan.
- Build and roll out API, worker, web and proxy in the approved order, keeping
  `AUTO_DISPATCH_ENABLED=false` and `PRODUCT_MEDIA_ENABLED=false`.
- Verify migration head, `/api/v1/health`, worker heartbeat, Next.js route
  health, TLS and the exact deployed image digest.
- Perform real-device sign-in, Google Maps, FCM receipt, COD order and rider
  acceptance against the deployed environment before enabling features.
- On failure, stop the rollout and use the documented image/database recovery
  procedure; **never** assume a down migration can safely undo live writes.

## 5. Signing and mobile release

The most recently verified signed QA APK before the latest dispatch and
logout hardening was built at Priority 1 commit
`ddcb0171d37cc48b2510a21da6da01565bf02e20` in
[workflow 41256448299](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256448299),
[artifact 13063123563](https://github.com/rishi-raj-AI/AI-Powered_Market/actions/runs/41256448299/artifacts/13063123563).
It is **not** the newest source revision: before distributing an APK, confirm
a successful signed build for the selected release SHA and record its artifact
ID, expiry and signer fingerprint in the evidence ledger.
It was signed with the existing pinned certificate; do not regenerate a key.
Install that exact artifact on a real low-end Android device and record
Google login, FCM token/receipt, Maps/GPS, COD, Hindi/Marathi, offline
recovery and rider alerts. APK build success is not device acceptance.

The definitive release checklist and dated evidence ledger are:
[acceptance](priority1-3-release-acceptance.md) and
[evidence](priority1-3-release-evidence-2026-11-01.md).
