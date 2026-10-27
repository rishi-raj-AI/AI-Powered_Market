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

## 6. Deploy an approved update

Use the guarded release entry point rather than a manual `git pull`/`make`
sequence. It verifies the exact approved SHA, preserves database and media
backups before migrations, records the prior deployed SHA, starts Caddy with
the application services, and rolls application code back if verification
fails.

After explicit release approval, run the following on the production host. Do
not source `.env.production`; it can contain values that are not shell-safe.

Before the first release after installing this revision, an administrator must
refresh the narrowly scoped sudo rule once:

```bash
sudo bash /home/ubuntu/gaonone/deploy/install_deploy_runner.sh
```

That rule preserves only the non-secret SHA and release-label selectors for the
direct release script; it does not grant a shell, Docker, arbitrary environment
variables, or a caller-selected checkout path.

```bash
GAONONE_EXPECTED_SHA=<full-approved-main-sha> \
GAONONE_ENVIRONMENT=production \
sudo /home/ubuntu/gaonone/deploy/release.sh
```

`GAONONE_ENVIRONMENT` is the deployment lock/log label and must be explicit:
use `production` for a production host and `staging` for the separate staging
workflow. It does not replace `APP_ENV=production` in `.env.production`, which
remains a required runtime safety setting. `GAONONE_EXPECTED_SHA` must be the
full green `origin/main` commit SHA; do not use the workflow-local `DEPLOY_SHA`
name outside GitHub Actions. `GAONONE_ROOT` and `GAONONE_DEPLOY_BRANCH` retain
their guarded defaults (`/home/ubuntu/gaonone` and `main`) in this privileged
path. The install script allows `sudo` to preserve only the SHA and environment
label through its narrow `env_keep` list; do not wrap the release script in
`sudo /usr/bin/env` or source
`.env.production`.

Then run the required production acceptance checks for login, store browsing,
cart, checkout, merchant fulfilment, and delivery lifecycle.

## 7. Logs

```bash
make prod-logs
```

Caddy access logs are JSON on stdout. Application logs are available through Docker Compose.

## 8. Database backup

The guarded release command already creates and verifies a timestamped database
and media backup before migrations. To create one manually without sourcing the
Compose environment file, run:

```bash
bash deploy/backup.sh
```

Backups must be copied off-server to durable storage before the pilot contains real customer data.

## 9. Database restore

Restoring overwrites data. Stop application traffic first, verify the backup
file, and use the guarded restore script with its explicit confirmation.

```bash
CONFIRM_RESTORE=YES \
  DB_BACKUP=/absolute/path/to/FILE.dump \
  bash deploy/restore.sh
```

## 10. Media backup

The `media_data` Docker volume contains uploaded product/store images. Until object storage is enabled, back this volume up separately and off-server.

## 11. Production provider activation

The application is provider-ready, but real credentials are intentionally absent from Git.

- SMS OTP: use `AUTH_PROVIDER=local_otp`, `SMS_AUTH_ENABLED=true`,
  `SMS_PROVIDER=msg91`, and `NEXT_PUBLIC_DIRECT_OTP_ENABLED=true` so the web
  image exposes the same backend-owned verification flow as the mobile build.
  Keep `DEV_OTP` empty. The production validator rejects a visible web OTP
  form unless that exact server gate is enabled, and the public flag alone
  never enables an API route.
  Obtain `MSG91_AUTH_KEY` from the MSG91 account and `MSG91_TEMPLATE_ID` from
  an approved transactional OTP template; enter both only in the server's
  `.env.production`. Confirm the account has balance, the Indian DLT
  entity/sender/template registrations are approved where required, and the
  template's OTP placeholder and validity are configured in MSG91. Run
  `python3 deploy/validate_env.py` without printing the environment. The legacy
  `msg91_widget` exchange endpoint remains compatible, but is not the shared
  web/mobile login mode. Real-device SMS receipt, wrong/expired code, resend,
  returning user and disabled-user checks remain mandatory staging evidence.
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
