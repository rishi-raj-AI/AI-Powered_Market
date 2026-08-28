#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env.production ]]; then
  echo "Missing .env.production" >&2
  exit 1
fi
if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
  echo "Refusing restore. Set CONFIRM_RESTORE=YES and provide DB_BACKUP=/path/to/file.dump" >&2
  exit 1
fi

DB_BACKUP="${DB_BACKUP:-}"
MEDIA_BACKUP="${MEDIA_BACKUP:-}"
if [[ -z "$DB_BACKUP" || ! -f "$DB_BACKUP" ]]; then
  echo "DB_BACKUP must point to an existing .dump file" >&2
  exit 1
fi

compose() {
  if docker info >/dev/null 2>&1; then
    docker compose --env-file .env.production -f docker-compose.prod.yml "$@"
  else
    sudo docker compose --env-file .env.production -f docker-compose.prod.yml "$@"
  fi
}

POSTGRES_USER="$(compose exec -T db printenv POSTGRES_USER | tr -d '\r')"
POSTGRES_DB="$(compose exec -T db printenv POSTGRES_DB | tr -d '\r')"
if [[ -z "$POSTGRES_USER" || -z "$POSTGRES_DB" ]]; then
  echo "Could not read PostgreSQL configuration from the production database container" >&2
  exit 1
fi

echo "Restoring database from $DB_BACKUP"
compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < "$DB_BACKUP"

if [[ -n "$MEDIA_BACKUP" ]]; then
  if [[ ! -f "$MEDIA_BACKUP" ]]; then
    echo "MEDIA_BACKUP does not exist: $MEDIA_BACKUP" >&2
    exit 1
  fi
  echo "Restoring uploaded media from $MEDIA_BACKUP"
  compose exec -T api sh -c 'rm -rf /app/data/uploads && mkdir -p /app/data/uploads && tar -xzf - -C /app/data' < "$MEDIA_BACKUP"
fi

echo "Restore completed. Run make prod-smoke immediately."
