#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${GAONONE_ROOT:-/home/ubuntu/gaonone}"
BRANCH="${GAONONE_DEPLOY_BRANCH:-main}"
EXPECTED_SHA="${GAONONE_EXPECTED_SHA:-}"
LOCK_FILE="${GAONONE_DEPLOY_LOCK:-/tmp/gaonone-production-deploy.lock}"

cd "$ROOT_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Another GaonOne production deployment is already running." >&2
  exit 1
fi

if [[ ! -f .env.production ]]; then
  echo "Missing $ROOT_DIR/.env.production" >&2
  exit 1
fi
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "Tracked production checkout has local changes; refusing automated deployment." >&2
  git status --short
  exit 1
fi

echo "=== Pre-deploy backup ==="
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
echo "Deploying $(git log -1 --oneline)"

make prod-check

compose() {
  if docker info >/dev/null 2>&1; then
    docker compose --env-file .env.production -f docker-compose.prod.yml "$@"
  else
    sudo docker compose --env-file .env.production -f docker-compose.prod.yml "$@"
  fi
}

compose build api web migrate
compose --profile ops run --rm migrate
compose up -d --no-build --force-recreate api web
sleep "${GAONONE_DEPLOY_SETTLE_SECONDS:-15}"
compose ps

bash deploy/smoke.sh
bash deploy/monitor.sh

printf '%s\n' "$TARGET_SHA" > .deployed-sha
printf 'GaonOne production deployment passed: %s\n' "$TARGET_SHA"
