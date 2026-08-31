#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${GAONONE_ROOT:-/home/ubuntu/gaonone}"
BRANCH="${GAONONE_DEPLOY_BRANCH:-main}"
EXPECTED_SHA="${GAONONE_EXPECTED_SHA:-}"
ENVIRONMENT="${GAONONE_ENVIRONMENT:-staging}"
LOCK_FILE="${GAONONE_DEPLOY_LOCK:-/tmp/gaonone-${ENVIRONMENT}-deploy.lock}"

cd "$ROOT_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Another GaonOne ${ENVIRONMENT} deployment is already running." >&2
  exit 1
fi

# Keep the production-grade Compose/env contract on the current server while the
# server itself is used as staging. Renaming these files would require a separate
# server migration and is intentionally deferred.
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
if [[ -n "$EXPECTED_SHA" && "$TARGET_SHA" != "$EXPECTED_SHA" ]]; then
  echo "Expected $EXPECTED_SHA but origin/$BRANCH is $TARGET_SHA; refusing stale deployment." >&2
  exit 1
fi

git checkout "$BRANCH"
git reset --hard "$TARGET_SHA"
echo "Deploying $(git log -1 --oneline) to ${ENVIRONMENT}"

make prod-check

compose() {
  if docker info >/dev/null 2>&1; then
    docker compose --env-file .env.production -f docker-compose.prod.yml "$@"
  else
    sudo docker compose --env-file .env.production -f docker-compose.prod.yml "$@"
  fi
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
  compose build api web worker
  compose up -d --no-build --force-recreate api web worker
  sleep "${GAONONE_DEPLOY_SETTLE_SECONDS:-15}"

  if bash deploy/smoke.sh && bash deploy/monitor.sh; then
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
compose up -d --no-build --force-recreate api web worker
sleep "${GAONONE_DEPLOY_SETTLE_SECONDS:-15}"
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
