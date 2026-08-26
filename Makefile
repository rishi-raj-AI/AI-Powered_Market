SHELL := /bin/bash

.PHONY: dev-up dev-down seed test-backend web mobile-ios mobile-check

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
