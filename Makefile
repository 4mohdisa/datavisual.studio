# datavisual.studio — monorepo task runner.
# Backend (FastAPI, Python/uv) lives in backend/; frontend (Next.js) in frontend/.
# Run `make help` for the list.

.DEFAULT_GOAL := help
.PHONY: help install dev backend frontend build test test-backend test-frontend \
        smoke smoke-split e2e e2e-install ui-audit gc backup restore-test clean

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

smoke-split: ## Smoke the split host config (polling default + >5MB upload). Needs the stack running.
	@echo "Proving the Vercel-split config: polling pipeline transport + large upload."
	@echo "For a TRUE two-origin test, run the frontend with BACKEND_URL/NEXT_PUBLIC_BACKEND_ORIGIN"
	@echo "pointed at a separate backend host, then: SPLIT=1 make smoke-split"
	SPLIT=1 node scripts/smoke.mjs

verify-deploy: ## Pre-deploy checklist, pass/fail per line (needs the stack running; set BASE=<url>)
	@echo "== verify-deploy — full-stack checklist against $${BASE:-http://localhost:3000} =="
	SPLIT=1 node scripts/smoke.mjs
	@echo ""
	@echo "== SECRET_KEY drill A: a backup restores AND encrypted keys decrypt with the SAME key =="
	./scripts/restore-test.sh
	@echo ""
	@echo "== Owner-run — need prod credentials, can't run headless =="
	@echo "  [ ] Clerk two-account walk: user B gets 404 on A's dashboard/dataset/export/status/share."
	@echo "      Proven deterministically in backend/tests/test_api.py; run once live with prod Clerk keys."
	@echo "  [ ] SECRET_KEY drill B: a FRESH key against an existing data/ must REFUSE to boot with the"
	@echo "      explicit error (guard: backend/tests/test_boot_guards.py). Confirm on the real host."
	@echo "  [ ] Pin replica/worker = 1 in the deploy config — locks, rate limiter and upload nonces are in-process."
	@echo "  [ ] Backup cron installed BEFORE announcing — data/ is the only copy (make backup)."

e2e: ## Browser e2e (Playwright; auto-starts servers, reuses if running)
	cd frontend && npm run test:e2e

e2e-install: ## One-time: install the Playwright chromium browser
	cd frontend && npm run test:e2e:install

ui-audit: ## Sweep every route × 390/768/1440 for overflow/tap-targets → UI_AUDIT.md (needs stack running)
	cd frontend && node scripts/ui-audit.mjs

gc: ## Sweep orphaned uploads/exports (never touches conversations). Cron this nightly.
	uv run python -m backend.gc

backup: ## Back up data/ (the whole database) to ./backups. Cron this nightly.
	./scripts/backup.sh

restore-test: ## Prove a backup restores: conversations load AND encrypted keys decrypt.
	./scripts/restore-test.sh

clean: ## Remove build artifacts and caches
	rm -rf frontend/.next frontend/test-results frontend/playwright-report
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
