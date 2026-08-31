SHELL := /bin/bash

.PHONY: dev-up dev-down seed test-backend test-web test-e2e test-a11y test-full web mobile-ios mobile-check prod-check prod-build prod-migrate prod-bootstrap prod-up prod-deploy prod-down prod-logs prod-status prod-smoke prod-backup prod-monitor prod-restore prod-cleanup prod-prune-tracking prod-worker-logs prod-worker-status

dev-up:
	docker compose up --build -d

dev-down:
	docker compose down

seed:
	docker compose exec api alembic upgrade head
	docker compose exec api python -m app.scripts.seed_dev

test-backend:
	docker compose exec api pip install ".[dev]"
	docker compose exec api pytest -q

test-web:
	cd web && npm ci && npm run build

test-e2e:
	cd web && npm ci && npx playwright install chromium && npm run test:e2e

test-a11y:
	cd web && npm ci && npx playwright install chromium && npm run test:a11y

test-full: test-backend test-web test-e2e

web:
	@echo "Open http://localhost:3000"

mobile-check:
	bash mobile/scripts/ios_preflight.sh

mobile-ios:
	bash mobile/scripts/run_ios.sh

prod-check:
	@test -f .env.production || (echo "Missing .env.production. Copy .env.production.example and fill real values." && exit 1)
	python3 deploy/validate_env.py
	docker compose --env-file .env.production -f docker-compose.prod.yml config >/dev/null
	@echo "Production compose configuration is valid."

prod-build: prod-check
	docker compose --env-file .env.production -f docker-compose.prod.yml build

prod-migrate: prod-check
	docker compose --env-file .env.production -f docker-compose.prod.yml --profile ops run --rm migrate

prod-bootstrap: prod-check
	@for key in PILOT_ADMIN_PHONE PILOT_ADMIN_NAME PILOT_VILLAGE_NAME PILOT_VILLAGE_DISTRICT PILOT_VILLAGE_STATE; do \
		grep -Eq "^$$key=.+" .env.production || (echo "Missing $$key in .env.production" && exit 1); \
	done
	docker compose --env-file .env.production -f docker-compose.prod.yml exec api python -m app.scripts.bootstrap_pilot

prod-up: prod-check
	docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build

prod-deploy: prod-check
	docker compose --env-file .env.production -f docker-compose.prod.yml build api web worker migrate
	docker compose --env-file .env.production -f docker-compose.prod.yml --profile ops run --rm migrate
	docker compose --env-file .env.production -f docker-compose.prod.yml up -d --no-build --force-recreate api web worker
	@sleep 15
	docker compose --env-file .env.production -f docker-compose.prod.yml ps
	bash deploy/monitor.sh

prod-down:
	docker compose --env-file .env.production -f docker-compose.prod.yml down

prod-logs:
	docker compose --env-file .env.production -f docker-compose.prod.yml logs -f --tail=200

prod-status:
	docker compose --env-file .env.production -f docker-compose.prod.yml ps

prod-smoke:
	bash deploy/smoke.sh

prod-backup:
	bash deploy/backup.sh

prod-monitor:
	bash deploy/monitor.sh

prod-restore:
	bash deploy/restore.sh

prod-cleanup:
	bash deploy/cleanup.sh

prod-worker-logs:
	docker compose --env-file .env.production -f docker-compose.prod.yml logs -f --tail=200 worker

prod-worker-status:
	docker compose --env-file .env.production -f docker-compose.prod.yml ps worker

prod-prune-tracking: prod-check
	docker compose --env-file .env.production -f docker-compose.prod.yml exec api python -m app.scripts.prune_delivery_locations
