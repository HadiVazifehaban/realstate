# AVG CRM & MLS Core — developer shortcuts
.DEFAULT_GOAL := help
PY := .venv/bin/python
PIP_INDEX ?= https://pypi.org/simple

.PHONY: help setup venv install db migrate run test lint license-fingerprint clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Full local-node bootstrap (venv + db + migrate + keys)
	PIP_INDEX_URL=$(PIP_INDEX) ./scripts/setup_local.sh

venv: ## Create the virtualenv
	python3 -m venv .venv

install: venv ## Install Python dependencies
	$(PY) -m pip install -U pip
	.venv/bin/pip install -i $(PIP_INDEX) -r requirements.txt

db: ## Start PostgreSQL + PostGIS + Redis
	docker compose up -d db redis

migrate: ## Apply Alembic migrations
	.venv/bin/alembic upgrade head

run: ## Run the API (LAN workspace)
	./scripts/dev.sh

test: ## Run the test suite
	$(PY) -m pytest -q

lint: ## Lint with ruff (if installed)
	.venv/bin/ruff check app tests || true

license-fingerprint: ## Print this machine's license fingerprint
	$(PY) -m app.cli.license_tool fingerprint

clean: ## Remove caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache
