#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env.production ]]; then
  echo "Missing .env.production" >&2
  exit 1
fi

set -a
source .env.production
set +a

compose() {
  if docker info >/dev/null 2>&1; then
    docker compose --env-file .env.production -f docker-compose.prod.yml "$@"
  else
    sudo docker compose --env-file .env.production -f docker-compose.prod.yml "$@"
  fi
}

BASE="https://${DOMAIN}"
FAIL=0

check_url(){
  local label="$1" url="$2"
  if curl --fail --silent --show-error --max-time 12 "$url" >/dev/null; then
    echo "OK  $label"
  else
    echo "FAIL $label" >&2
    FAIL=1
  fi
}

RUNNING_SERVICES="$(compose ps --status running --services 2>/dev/null || true)"
for service in db redis api web proxy; do
  if grep -qx "$service" <<<"$RUNNING_SERVICES"; then
    echo "OK  container:$service"
  else
    echo "FAIL container:$service not running" >&2
    FAIL=1
  fi
done

check_url "homepage" "${BASE}/"
check_url "api-health" "${BASE}/api/v1/health"
check_url "api-ready" "${BASE}/api/v1/health/ready"

DISK_USED="$(df -P . | awk 'NR==2 {gsub("%","",$5); print $5}')"
if (( DISK_USED >= 90 )); then
  echo "FAIL disk usage ${DISK_USED}%" >&2
  FAIL=1
elif (( DISK_USED >= 80 )); then
  echo "WARN disk usage ${DISK_USED}%"
else
  echo "OK  disk usage ${DISK_USED}%"
fi

MEM_AVAILABLE="$(free -m | awk '/^Mem:/ {print $7}')"
if [[ -n "$MEM_AVAILABLE" ]] && (( MEM_AVAILABLE < 100 )); then
  echo "WARN available memory ${MEM_AVAILABLE}MB"
else
  echo "OK  available memory ${MEM_AVAILABLE:-unknown}MB"
fi

LATEST_BACKUP="$(find backups -maxdepth 1 -type f -name 'gaonone-db-*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2- || true)"
if [[ -z "$LATEST_BACKUP" ]]; then
  echo "WARN no production database backup found"
else
  AGE_HOURS="$(( ($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")) / 3600 ))"
  if (( AGE_HOURS > 30 )); then
    echo "FAIL latest backup is ${AGE_HOURS}h old" >&2
    FAIL=1
  else
    echo "OK  latest backup ${AGE_HOURS}h old"
  fi
fi

if (( FAIL )); then
  echo "GaonOne production monitor detected failures." >&2
  exit 1
fi

echo "GaonOne production monitor passed."
