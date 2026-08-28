#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env.production ]]; then
  echo "Missing .env.production" >&2
  exit 1
fi

compose() {
  if docker info >/dev/null 2>&1; then
    docker compose --env-file .env.production -f docker-compose.prod.yml "$@"
  else
    sudo docker compose --env-file .env.production -f docker-compose.prod.yml "$@"
  fi
}

# .env.production is a Docker Compose env file, not a shell script. Read database
# credentials from the running container so values containing spaces stay safe.
POSTGRES_USER="$(compose exec -T db printenv POSTGRES_USER | tr -d '\r')"
POSTGRES_DB="$(compose exec -T db printenv POSTGRES_DB | tr -d '\r')"
if [[ -z "$POSTGRES_USER" || -z "$POSTGRES_DB" ]]; then
  echo "Could not read PostgreSQL configuration from the production database container" >&2
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%SZ)"
DB_OUT="${BACKUP_DIR}/gaonone-db-${STAMP}.dump"
MEDIA_OUT="${BACKUP_DIR}/gaonone-media-${STAMP}.tar.gz"
MANIFEST="${BACKUP_DIR}/gaonone-${STAMP}.sha256"

echo "Creating PostgreSQL backup..."
compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$DB_OUT"
test -s "$DB_OUT" || { echo "Database backup is empty" >&2; exit 1; }

echo "Creating uploaded-media backup..."
compose exec -T api sh -c 'cd /app/data && tar -czf - uploads' > "$MEDIA_OUT"
test -s "$MEDIA_OUT" || { echo "Media backup is empty" >&2; exit 1; }

sha256sum "$DB_OUT" "$MEDIA_OUT" > "$MANIFEST"
find "$BACKUP_DIR" -type f \( -name 'gaonone-db-*.dump' -o -name 'gaonone-media-*.tar.gz' -o -name 'gaonone-*.sha256' \) -mtime "+${RETENTION_DAYS}" -delete
printf 'Backup complete:\n  %s\n  %s\n  %s\n' "$DB_OUT" "$MEDIA_OUT" "$MANIFEST"
