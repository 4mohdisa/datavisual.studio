# datavisual.studio — monorepo task runner.
# Backend (FastAPI, Python/uv) lives in backend/; frontend (Next.js) in frontend/.
# Run `make help` for the list.

.DEFAULT_GOAL := help
.PHONY: help install dev backend frontend build test test-backend test-frontend \
        smoke e2e e2e-install clean

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install backend (uv) + frontend (npm) dependencies
	uv sync --group dev
	cd frontend && npm install

dev: ## Run backend + frontend together (Ctrl-C stops both)
	@echo "Backend :8001  ·  Frontend :3000"
	@trap 'kill 0' INT TERM EXIT; \
	 uv run python -m backend.main & \
	 (cd frontend && npm run dev) & \
	 wait

backend: ## Run only the FastAPI backend (port 8001)
	uv run python -m backend.main

frontend: ## Run only the Next.js dev server (port 3000)
	cd frontend && npm run dev

build: ## Production build check (frontend build + backend import)
	uv run python -c "import backend.main; print('backend imports OK')"
	cd frontend && npm run build

test: test-backend test-frontend ## Run all tests

test-backend: ## Backend unit + integration tests (pytest, hermetic)
	uv run pytest

test-frontend: ## Frontend production build (catches SSR/type breakage)
	cd frontend && npm run build

smoke: ## Full-stack HTTP smoke test (needs the stack running: make dev)
	node scripts/smoke.mjs

e2e: ## Browser e2e (Playwright; auto-starts servers, reuses if running)
	cd frontend && npm run test:e2e

e2e-install: ## One-time: install the Playwright chromium browser
	cd frontend && npm run test:e2e:install

clean: ## Remove build artifacts and caches
	rm -rf frontend/.next frontend/test-results frontend/playwright-report
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
