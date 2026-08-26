SHELL := /bin/bash

.PHONY: dev-up dev-down seed test-backend web mobile-ios mobile-check prod-check prod-build prod-migrate prod-up prod-down prod-logs prod-status prod-smoke prod-backup

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

prod-up: prod-check
	docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build

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
