# GaonOne Production Deployment

This runbook is for the first pilot deployment on a single Linux server. Development continues to use `docker-compose.yml`; production uses `docker-compose.prod.yml`.

## 1. Server requirements

- Ubuntu 24.04 LTS or equivalent Linux host
- Docker Engine + Docker Compose plugin
- A public IPv4 address
- DNS A/AAAA record pointing the production domain to the server
- TCP ports 80 and 443 open; UDP 443 open for HTTP/3
- Git access to this repository

For the pilot, PostgreSQL/PostGIS and Redis run as private Docker services with persistent volumes. They are not exposed publicly. A later migration to managed database/Redis can be done by changing `DATABASE_URL` and `REDIS_URL`.

## 2. First server setup

```bash
git clone https://github.com/rishi-raj-AI/AI-Powered_Market.git
cd AI-Powered_Market
cp .env.production.example .env.production
```

Generate secrets on the server; do not commit them:

```bash
openssl rand -hex 32
openssl rand -base64 36
```

Set at minimum in `.env.production`:

- `DOMAIN`
- `ACME_EMAIL`
- `PUBLIC_BASE_URL=https://<domain>`
- `CORS_ORIGINS=https://<domain>`
- `TRUSTED_HOSTS=<domain>`
- `POSTGRES_PASSWORD`
- matching password inside `DATABASE_URL`
- `SECRET_KEY` with at least 32 random bytes

Keep `APP_ENV=production` and `APP_DEBUG=false`.

## 3. Validate before starting

```bash
make prod-check
make prod-build
```

## 4. Database migration

Run migrations before bringing up a new application version:

```bash
make prod-migrate
```

The migration container exits after applying Alembic migrations.

## 5. Start production

```bash
make prod-up
make prod-status
```

Caddy is the only public service. It terminates HTTPS automatically and routes:

- `/api/*`, `/docs`, `/redoc`, `/openapi.json` -> FastAPI
- `/media/*` -> FastAPI media serving
- everything else -> Next.js

Check:

```bash
curl -fsS https://$DOMAIN/api/v1/health
curl -fsS https://$DOMAIN/api/v1/health/ready
```

Expected readiness includes `database: ok` and `redis: ok`.

## 6. Deploy an update

```bash
git pull --ff-only origin main
make prod-build
make prod-migrate
make prod-up
make prod-status
```

Then run production smoke checks for login, store browsing, cart, checkout, merchant fulfilment, and delivery lifecycle.

## 7. Logs

```bash
make prod-logs
```

Caddy access logs are JSON on stdout. Application logs are available through Docker Compose.

## 8. Database backup

Create a timestamped logical backup:

```bash
mkdir -p backups
set -a; source .env.production; set +a
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "backups/gaonone-$(date +%Y%m%d-%H%M%S).dump"
```

Backups must be copied off-server to durable storage before the pilot contains real customer data.

## 9. Database restore

Restoring overwrites data. Stop application traffic first and verify the backup file.

```bash
set -a; source .env.production; set +a
cat backups/FILE.dump | docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists
```

## 10. Media backup

The `media_data` Docker volume contains uploaded product/store images. Until object storage is enabled, back this volume up separately and off-server.

## 11. Production provider activation

The application is provider-ready, but real credentials are intentionally absent from Git.

- SMS: configure the selected Indian SMS provider and disable development OTP behavior.
- Razorpay: set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`; use test mode first.
- Firebase: set project/service credentials once push transport is activated.
- Maps: GPS/radius discovery works now; map rendering/geocoding can be enabled later.

## 12. Release rules

- Never commit `.env.production`, signing keys, Firebase service credentials, or payment secrets.
- Never expose PostgreSQL or Redis ports publicly.
- Apply migrations before starting code that depends on them.
- Take a database backup before destructive migrations or major releases.
- Verify `/api/v1/health/ready` after every deployment.
- Do not seed development users/data in production.
