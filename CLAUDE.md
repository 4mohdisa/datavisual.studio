# CLAUDE.md - Technical Notes for Datavisual.studio

Technical details and implementation notes for future development sessions.

## Project Overview

Datavisual.studio is a data-visualisation-first analytics platform (think
Power BI + research assistant). The CORE ARTIFACT is the **dashboard** — a
persistent widget spec that users edit in place through a chat assistant.
Data arrives via upload or DB/API connectors. The AI research pipeline
(data analysis → internet research → 3-stage LLM council → report) is a
feature that FEEDS the dashboard: every run pins its charts + research
findings + synthesis onto one. The prediction engine (ELO/Poisson/XGBoost)
stays dormant unless the data looks like ratings.

## Ports

- Backend: **8001** (NOT 8000 — user has another app there). `uv run python -m backend.main`
- Frontend: 3000 (Next.js dev). `npm run dev` in `frontend/`
- Update `backend/main.py` CORS + `NEXT_PUBLIC_API_BASE` together if changing.

## API keys — BYO per user (critical policy)

- **Users bring their own AI keys** (OpenRouter required, Gemini optional),
  saved per-account from the sidebar "AI keys" row (`ApiKeysModal.jsx` →
  `GET/POST /api/account/settings`, `POST /api/account/validate`). Keys live
  on the user's record in `data/users.json`.
- `config.get_api_key()` / `get_gemini_api_key()` check the request-scoped
  user (`current_user_ctx` ContextVar, bound in main.py middleware) FIRST:
  identity present → ONLY that user's keys (None → pipeline hard-stops with
  guidance). **The owner's keys are never spent on users' requests.**
- Global `data/settings.json` / `.env` keys apply only in open dev mode (no
  Clerk configured). `backend/config.py` exposes getters — always call these;
  never cache their values at import time.
- Keys are returned to the frontend masked only. Signed-in users with no key
  get the modal auto-opened once per session (AccountPanel `autoPrompt`).

## Backend Structure (`backend/`)

- **config.py** — static constants + dynamic settings (see above). `DEBUG`
  gates all diagnostic prints (`DATAVISUAL_DEBUG=true`).
- **openrouter.py** — `query_model()` async client. Caps `max_tokens` (OpenRouter
  reserves credit for max output; uncapped requests 402 on low balances) and
  retries once at a smaller cap on 402. Returns None on failure — callers degrade
  gracefully; one model must never sink the council.
- **council.py** — 3-stage council. Stage 2 anonymizes responses as
  "Response A/B/…" with a strict "FINAL RANKING:" format; `parse_ranking_from_text`
  falls back to any "Response X" pattern, then to a default equal ranking.
- **research.py** — 3 topic-GENERIC searches via the research model (Perplexity
  Sonar by default): current facts → established research → forecasts/consensus.
  `plan_searches()` asks the fast model to write the 3 query strings per
  question (static `build_search_plan` is the untouched fallback).
  Do not re-specialise the queries to one domain. Extracts confirmed facts +
  live scores from titles/content by regex (sports-aware but harmless
  elsewhere).
- **data_analysis.py** — `analyse_file(path)` = `analyse_df(_load(path))`.
  `analyse_df` is shared with `/api/reanalyse`, which filters in memory
  (no temp files). Profiling, quality notes, auto-charts, data excerpt for the
  council prompt.
- **prediction_engine.py** — deterministic math, no LLM calls. Model A = ELO
  Monte Carlo bracket sim, Model B = ELO-Poisson/Dixon-Coles (rho fitted from
  scorelines when present), Model C = XGBoost (only with a match-history CSV +
  libomp installed). Ensemble → combined with internet (35%) and council (25%)
  probabilities; dataset ensemble is 40% and the guaranteed fallback.
- **report_builder.py** — enriched council prompt (confirmed facts first,
  dataset excerpt, algorithmic baseline, event status, research blocks) +
  structured report dict. Keep the prompt under ~16k chars.
- **storage.py** — JSON files in `data/conversations/`. `is_valid_id()` is the
  trust-boundary check for ids used in file paths — every endpoint routes
  through it (get_conversation returns None on bad ids; create endpoint 400s).
- **pdf_export.py** — `export_report(conversation, base, fmt=None, mode=None)`:
  ONE dark structured layout for reports and dashboards; PDF chain WeasyPrint →
  headless Chrome `--print-to-pdf` → HTML fallback. `fmt='html'|'pdf'` forces a
  format; `?mode=dashboard` for the visual export. `BROWSER_PATH` env overrides
  Chrome discovery (the Docker image sets it to /usr/bin/chromium).
- **main.py** — FastAPI endpoints; the core is `POST /api/analyse` (SSE stream)
  emitting stage events + granular `activity` events consumed by the Activity
  Panel. Uploads: sanitised basename, 50 MB cap, CSV/Excel/JSON only.
  - `POST /api/connect` — Power BI-style import from a SQL database
    (SQLAlchemy URL + SELECT-only query; Postgres/MySQL/SQLite drivers
    installed) or a REST API (JSON records). Materialises the result as a CSV
    in data/uploads, so downstream it IS a file upload. The connector config is
    persisted in data/sources.json (local, gitignored) so dashboards can
    Refresh from it. Declared sync (`def`) so blocking IO runs in the
    threadpool.
  - `POST /api/dashboard/{id}/refresh` — re-runs the saved connector import,
    overwrites the dataset CSV, and rebuilds every widget that carries a spec
    (ids preserved; insights/layout untouched).
  - `POST /api/dashboard` — with `file_id`: standalone dashboard from an
    upload (no AI run). With `conversation_id`: (re)build the widget spec on
    an existing record in place (migration path for pre-spec records).
  - `POST /api/dashboard/{id}/chat` — THE dashboard editor. Natural-language
    `message` → LLM emits structured ops → deterministic engine applies them
    to the EXISTING spec (never rebuilds). Direct `ops` bypass the LLM (the
    ✕ remove buttons). Edits + chat history persist on the record.
- **The living monitor** (`sync_dashboard` in dashboard.py + POST
  /api/dashboard/{id}/sync): the core differentiator. One "Update" re-pulls
  connector data (rebuilds spec'd charts/metrics, records value DELTAS) AND
  re-runs every pinned research insight's stored `query` (records new sources),
  then returns a human-readable `changes` list and appends a `watch_log`
  snapshot + `last_synced` on the dashboard. Research insights created via
  add_insight now persist `query` + `as_of` so they're refreshable. The old
  data-only /refresh endpoint + api.refreshDashboard were REMOVED (sync
  supersedes them). Frontend: header "Update" button (shown when a source or
  pinned research exists) + a "What changed" banner + per-insight "as of"
  freshness + metric delta chips (via widget.sub).
- **dashboard.py** — the dashboard engine. `build_dashboard_spec(...,
  template="overview", focus=None)` — TEMPLATES {minimal, overview, full,
  kpi, visual} control max_charts/comparison/table/extra_metrics; `focus`
  picks which numeric column leads the headline metric and first charts
  (initial widgets: metrics/charts/insights/comparison/table; with a df it
  uses `default_chart_specs` for a rich, fully-rebuildable chart set),
  `build_chart_from_spec` (structured spec → Plotly JSON;
  line/bar/scatter/histogram/pie/box/heatmap/area/treemap with group_by + agg), the editor ops protocol (add_chart, update_chart,
  remove_widget, add_metric, add_insight→live research, rename_dashboard),
  `apply_ops` (in-place mutation, per-op error notes), and
  `insights_from_pipeline`. The LLM only emits specs — charts are always
  drawn deterministically. Pipeline runs call build_dashboard_spec in
  `_save_enriched_conversation` ONLY when no dashboard exists yet, so user
  edits are never clobbered by a re-run.

## Auth & multi-user (Clerk identity, LOCAL data — free product)

- **Free product, no billing.** Clerk is used for IDENTITY ONLY (sign in/up,
  session, sign-out). Supabase was fully removed — there is NO external DB.
- **All user data lives on the backend's local disk** (the owner hosts FastAPI
  on AWS): conversations/dashboards in data/conversations/, uploads, sources,
  settings — and the user registry in **data/users.json**.
- **Internal user ids, not Clerk ids**: backend/users.py maps the Clerk id
  (forwarded by the proxy as X-Clerk-User-Id + email/name headers) to OUR OWN
  generated `u_<hex>` id via `get_or_create_user`. Everything downstream
  (conversation `owner_id`) uses the internal id, so the auth provider is
  swappable at one lookup.
- **Ownership scoping in main.py**: `_owned(conversation_id, http_request)`
  loads + enforces owner (404 for other users AND for ownerless legacy
  records when an identity is present); `_stamp_owner` at the three create
  sites; the conversation list filters by owner. No identity headers (local
  dev without Clerk keys) = open mode, everything visible.
- **Proxy** (app/api/backend/[...path]/route.js) is thin: verify Clerk session
  → forward with identity headers (+ X-Proxy-Secret) → stream response.
  api/settings* stays blocked from clients.
- **PROXY_SHARED_SECRET** (same value in backend .env and frontend .env.local):
  when set, the backend 403s any /api request without the header — required
  when the AWS backend is publicly reachable.
- AccountPanel = "AI keys" row (ApiKeysModal) + Clerk UserButton + name/email
  + explicit sign-out. Sign-in/up pages redirect to /studio. Auth-optional dev
  mode unchanged.
- **Admin panel**: `/admin` (components/AdminPanel.jsx) → `GET
  /api/admin/overview` — user registry, per-user research/dashboards/events,
  14-day activity from `data/analytics.jsonl` (`_track()` appends at analyse/
  create-dashboard/dashboard-chat/sync/connect). NOT Clerk-protected — gated
  by `ADMIN_PASSWORD` env via the `X-Admin-Password` header (the page shows a
  password prompt, keeps it in sessionStorage; the proxy + middleware exempt
  api/admin from the sign-in requirement). Unset password = open dev mode
  only.

## Frontend Structure (`frontend/`) — Next.js 16, App Router, JSX

- **app/** — thin server pages only: `/` renders the marketing `Landing`
  (components/landing/ — Landing.jsx + Blocks.jsx, dependency-free SVG chart
  blocks), `/studio` and `/chat/[id]` render `AppShell`, `/dashboard/[id]`
  renders `Dashboard`. In-app "home" navigation targets `/studio`, NOT `/`.
  `layout.js` wraps everything in the client `ErrorBoundary` and imports
  `globals.css`.
- **components/AppShell.jsx** ('use client') — conversation state, SSE event
  handling, reload/poll recovery, localStorage titles + soft-delete. It derives
  the active conversation id from `usePathname()`, NOT route params: the
  first-send flow updates the URL with `window.history.pushState` (shallow) so
  a full `router.push` doesn't remount the page and drop mid-stream state.
  Normal navigation (sidebar, palette, delete) uses `router.push`.
- **components/ui/** — the custom UI kit: Button (variants: primary/secondary/
  outline/ghost/danger), Input (`as="textarea"`), Field, Modal, Skeleton.
  Build new UI from these primitives rather than one-off Tailwind blobs.
- **components/LazyPlot.jsx** — the ONLY way to render Plotly. It wraps
  react-plotly.js in `next/dynamic` with `ssr: false`; importing plotly.js
  directly breaks SSR (touches `window` at module scope).
- **components/Home.jsx** — the workspace hub rendered at `/` (AppShell shows
  it whenever no conversation id is active). Two flow cards — Build a
  dashboard (upload/connect + Create-dashboard inline) and Deep research
  (question composer inside the card) — plus grids of existing dashboards and
  research reports. The root route is NOT a chat surface.
- **components/** — Sidebar (Dashboards section first, then dated research;
  Settings gear), ChatInterface (the research-run view: progress with a
  "dashboard is generated automatically" hint, completed reports get a
  DashboardReadyBanner linking to /dashboard/[id], follow-up chat input),
  ConnectSource (DB/API import modal), Report (report sections),
  PredictionSuite, Dashboard, ActivityPanel, Settings (modal),
  CommandPalette (Cmd+K).
- **lib/api.js** — the only fetch layer; `API_BASE = '/api/backend'` (the
  authenticated proxy), never the FastAPI port directly.
  **lib/constants.js** — shared constants.
- Dark theme via CSS variables in `app/globals.css`.
- ReactMarkdown output is wrapped in `<div className="markdown-content">`.

## Deployment

See **DEPLOYMENT.md**. `docker-compose.yml` runs both parts (backend image
installs Chromium for charts + PDF; frontend uses `output: 'standalone'`).
Required prod env: `PROXY_SHARED_SECRET` (both sides), Clerk keys (frontend),
`ADMIN_PASSWORD`, `FRONTEND_ORIGIN` (appended to CORS origins). All backend
state = the `data/` directory; back that up and you have everything.

## Gotchas

1. Run the backend as `python -m backend.main` from the project root (relative imports).
2. Verify any new model id against https://openrouter.ai/api/v1/models before
   adding — invalid ids 404 silently and drop out of the council.
3. `data/` is gitignored: conversations, uploads, exports, settings.json, model cache.
4. Charts carry a non-serialisable `dataframe` key in memory — strip before persisting.
5. Metadata (label_to_model, aggregate_rankings) persists inside the report/pipeline,
   not as top-level conversation fields.

## Testing

Run from the project root via the **Makefile** (`make help`):
- `make test-backend` — **pytest** (`backend/tests/`, hermetic temp data dir, no network):
  trust boundaries (`is_valid_id`, share lifecycle), dashboard chart builder + every op,
  templates, BYO-key resolution, data profiling, and FastAPI TestClient integration
  (upload→dashboard→edit→share→public allowlist→revoke, ownership 404s, admin gate).
- `make e2e` — **Playwright** (`frontend/e2e/`): landing/SEO + the deterministic
  upload→dashboard→share→public journey. `make e2e-install` once (chromium). Reuses running servers.
- `make smoke` — full-stack HTTP smoke (`scripts/smoke.mjs`) over a running stack.
- `make test` = pytest + `next build`; `make build` = backend import + `next build`.
- Quick manual checks: `uv run python -c "import backend.main"`, `cd frontend && npm run build`.
