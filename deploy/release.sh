#!/bin/bash
set -euo pipefail

# sudo's env_reset retains PATH unless the host also configures secure_path.
# This privileged entry point must never resolve Git, Docker, or its helpers
# from the invoking user's PATH.
PATH="/usr/sbin:/usr/bin:/sbin:/bin"
export PATH

# This script is installed as a root-owned entry point at
# /usr/local/sbin/gaonone-release. Do not make either value caller-configurable:
# the self-hosted runner must not select code that will run as root.
ROOT_DIR="/srv/gaonone"
BRANCH="main"
EXPECTED_SHA="${GAONONE_EXPECTED_SHA:-}"
ENVIRONMENT="${GAONONE_ENVIRONMENT:-}"

if [[ -z "$ENVIRONMENT" ]]; then
  echo "GAONONE_ENVIRONMENT must be explicitly set to staging or production." >&2
  exit 1
fi
case "$ENVIRONMENT" in
  staging|production) ;;
  *)
    echo "GAONONE_ENVIRONMENT must be staging or production, got: $ENVIRONMENT" >&2
    exit 1
    ;;
esac
if [[ -z "$EXPECTED_SHA" ]]; then
  echo "GAONONE_EXPECTED_SHA must be set to the approved origin/$BRANCH commit SHA." >&2
  exit 1
fi

RUNTIME_SERVICES=(api web worker proxy)

assert_root_owned_path() {
  local path="$1" owner mode
  if [[ -L "$path" || ! -e "$path" ]]; then
    echo "Protected release path is missing or symlinked: $path" >&2
    return 1
  fi
  owner="$(stat -c '%U' "$path")"
  mode="$(stat -c '%a' "$path")"
  if [[ "$owner" != "root" || $((8#$mode & 022)) -ne 0 ]]; then
    echo "Protected release path must be root-owned and not group/world writable: $path" >&2
    return 1
  fi
}

assert_secure_release_checkout() {
  local insecure_path
  assert_root_owned_path /srv
  assert_root_owned_path "$ROOT_DIR"
  if [[ ! -d "$ROOT_DIR/.git" ]]; then
    echo "Protected release checkout is missing .git: $ROOT_DIR" >&2
    return 1
  fi
  insecure_path="$(find "$ROOT_DIR" -xdev \( -type l -o ! -user root -o -perm /022 \) -print -quit)"
  if [[ -n "$insecure_path" ]]; then
    echo "Protected release checkout contains a non-root-owned or writable path: $insecure_path" >&2
    return 1
  fi
}

if ! assert_secure_release_checkout; then
  exit 1
fi

LOCK_FILE="$ROOT_DIR/.gaonone-${ENVIRONMENT}-deploy.lock"
cd "$ROOT_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Another GaonOne ${ENVIRONMENT} deployment is already running." >&2
  exit 1
fi

# Keep the production-grade Compose/env contract. The explicit deployment label
# above controls release locking/logging; renaming these files is a separate
# infrastructure migration and is intentionally deferred.
if [[ ! -f .env.production ]]; then
  echo "Missing $ROOT_DIR/.env.production" >&2
  exit 1
fi

git config core.filemode false
if ! git diff --quiet --ignore-submodules -- || ! git diff --cached --quiet --ignore-submodules --; then
  echo "Tracked ${ENVIRONMENT} checkout has local content changes; refusing automated deployment." >&2
  git status --short --untracked-files=no
  exit 1
fi

PREVIOUS_SHA=""
if [[ -f .deployed-sha ]]; then
  PREVIOUS_SHA="$(tr -d '[:space:]' < .deployed-sha)"
fi
printf '%s\n' "$PREVIOUS_SHA" > .previous-deployed-sha

echo "=== Pre-deploy backup (${ENVIRONMENT}) ==="
bash deploy/backup.sh

echo "=== Sync $BRANCH ==="
git fetch --prune origin "$BRANCH"
TARGET_SHA="$(git rev-parse "origin/$BRANCH")"
if [[ "$TARGET_SHA" != "$EXPECTED_SHA" ]]; then
  echo "Expected $EXPECTED_SHA but origin/$BRANCH is $TARGET_SHA; refusing stale deployment." >&2
  exit 1
fi

git checkout "$BRANCH"
git reset --hard "$TARGET_SHA"
if ! assert_secure_release_checkout; then
  echo "Synced checkout failed the protected release integrity check; refusing deployment." >&2
  exit 1
fi
echo "Deploying $(git log -1 --oneline) to ${ENVIRONMENT}"

make prod-check

compose() {
  if docker info >/dev/null 2>&1; then
    docker compose --env-file .env.production -f docker-compose.prod.yml "$@"
  else
    sudo docker compose --env-file .env.production -f docker-compose.prod.yml "$@"
  fi
}

# Caddy is the only public listener. Verify it was started before the HTTPS
# smoke checks so an application-only rollout cannot leave the site offline.
ensure_proxy_running() {
  local running_services
  running_services="$(compose ps --status running --services 2>/dev/null || true)"
  if grep -Fxq "proxy" <<<"$running_services"; then
    return 0
  fi

  echo "Caddy proxy is not running after the deployment settle period." >&2
  return 1
}

start_runtime_services() {
  if ! compose up -d --no-build --force-recreate "${RUNTIME_SERVICES[@]}"; then
    echo "Could not start the runtime services." >&2
    return 1
  fi
  if ! sleep 15; then
    echo "Deployment settle delay failed." >&2
    return 1
  fi
  ensure_proxy_running
}

# Roll the running deployment back to the last known-good SHA.
#
# Migrations are forward-only and additive by contract, so the previous
# application code runs against the migrated schema. The rollback therefore
# restores code, not schema — and says so, rather than pretending the database
# went back too.
rollback() {
  local reason="$1"
  echo "=== DEPLOY FAILED: ${reason} ===" >&2

  if [[ -z "$PREVIOUS_SHA" ]]; then
    echo "No previous deployed SHA recorded; cannot roll back automatically." >&2
    echo "The new code is live and failing verification. Restore manually from the" >&2
    echo "pre-deploy backup in ./backups and redeploy a known-good commit." >&2
    return 1
  fi

  echo "Rolling back to ${PREVIOUS_SHA}" >&2
  if ! git cat-file -e "${PREVIOUS_SHA}^{commit}" 2>/dev/null; then
    echo "Previous SHA ${PREVIOUS_SHA} is not present locally; cannot roll back." >&2
    return 1
  fi

  git reset --hard "$PREVIOUS_SHA"
  if ! assert_secure_release_checkout; then
    echo "Rollback checkout failed the protected release integrity check; refusing rollback startup." >&2
    return 1
  fi
  compose build api web worker
  if start_runtime_services && bash deploy/smoke.sh && bash deploy/monitor.sh; then
    printf '%s\n' "$PREVIOUS_SHA" > .deployed-sha
    echo "=== ROLLBACK SUCCEEDED: ${ENVIRONMENT} is serving ${PREVIOUS_SHA} ===" >&2
    echo "Schema is still at the newer migration head, which is safe for" >&2
    echo "additive migrations. Review before redeploying." >&2
    return 0
  fi

  echo "=== ROLLBACK FAILED: ${ENVIRONMENT} needs manual recovery ===" >&2
  echo "Pre-deploy backup is in ./backups; restore with deploy/restore.sh." >&2
  return 1
}

compose build api web worker migrate
compose --profile ops run --rm migrate
if ! start_runtime_services; then
  rollback "Caddy proxy did not start"
  exit 1
fi
compose ps

# Everything past this point is verification. A failure here means the new code
# is live and broken, so it must not simply exit — it rolls back.
if ! bash deploy/smoke.sh; then
  rollback "smoke checks failed"
  exit 1
fi
if ! bash deploy/monitor.sh; then
  rollback "post-deploy monitor failed"
  exit 1
fi

printf '%s\n' "$TARGET_SHA" > .deployed-sha
printf 'GaonOne %s deployment passed: %s\n' "$ENVIRONMENT" "$TARGET_SHA"
printf 'Rollback target if needed: %s\n' "${PREVIOUS_SHA:-none recorded}"
