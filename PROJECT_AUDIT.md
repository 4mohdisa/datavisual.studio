# datavisual.studio — Project Audit & Handoff

**Purpose of this doc:** a complete, self-contained snapshot so another developer or
agent can continue the work. Companion docs: `CLAUDE.md` (technical notes/gotchas),
`DEPLOYMENT.md` (hosting), `README.md` (public overview). This one is the map + state
+ feature catalog + known debt + next steps.

_Last updated: 2026-07-07. Repo: `git@github.com:4mohdisa/datavisual.studio.git`, branch `main`._

---

## 1. What this product is

A **data-visualisation-first analytics platform** — think "Power BI + a research
assistant", positioned as a **living monitor**: dashboards that track a situation and
tell you *what changed*.

- **Core artifact = the dashboard**: a persistent widget spec (metrics, charts,
  insights, comparison, table, text) that users edit *in place* by chatting or by hand.
- **Data in** via upload (CSV/Excel/JSON) or a Power BI-style connector (SQL DB / REST API).
- **AI research pipeline** (data analysis → live web research → 3-stage LLM "council" →
  cited report) *feeds* the dashboard: every run pins its charts + findings + synthesis.
- **Living monitor**: one "Update" re-pulls connector data **and** re-runs pinned research,
  then shows a plain-English "what changed" feed (value deltas + new sources).
- **Free product, BYO keys**: users bring their own OpenRouter (+ optional Gemini) keys.
- **Prediction engine** (ELO/Poisson/XGBoost) stays dormant unless data looks like ratings.

---

## 2. Current status (READ FIRST)

- **Builds green**: `cd frontend && npm run build` ✓ ; `uv run python -c "import backend.main"` ✓.
- **⚠️ Large uncommitted change set in the working tree** (this session's work — NOT yet
  committed). It includes the **share feature, the animated/SEO landing, all SEO files,
  and two CRITICAL security fixes**. Committing this is the first thing the next agent
  should do (see §12). Files touched:
  - Modified: `backend/main.py`, `backend/storage.py`, `frontend/middleware.js`,
    `frontend/lib/api.js`, `frontend/app/api/backend/[...path]/route.js`,
    `frontend/components/{Dashboard,Report}.jsx`, `frontend/components/landing/Landing.jsx`,
    `frontend/app/{layout,page,studio/page,privacy/page,terms/page,admin/page,globals.css}`,
    `frontend/.env.local.example`.
  - New: `frontend/app/{icon,manifest,opengraph-image,robots,sitemap}.js`,
    `frontend/app/share/[shareId]/page.js`,
    `frontend/components/{DashboardWidgets,ShareModal,SharedView}.jsx`,
    `frontend/components/landing/{FeatureDemos,Reveal}.jsx`.
- **Last commit**: `ef08fdf docs: drop upstream fork credit from README`.
- **Runtime data present** (gitignored): 16 conversations, 3 users in `data/`.

---

## 3. Architecture

```
Browser
  │  (Clerk session cookie)
  ▼
Next.js 16 App Router  (port 3000)
  • marketing/legal pages, the app shell, dashboards, public share views
  • middleware.js  → Clerk route protection (when keys set)
  • /api/backend/[...path]  → THIN AUTH PROXY: verify Clerk → forward with identity
    headers (x-clerk-user-id / x-user-email / x-user-name) + x-proxy-secret → stream back
  ▼  (server-to-server)
FastAPI engine  (port 8001)   ← the ONLY thing that owns data
  • all business logic, LLM calls, pipeline, exports
  • ALL state on local disk under data/   (NO external database)
```

Key invariants:
- The browser **never** talks to FastAPI directly — always through the Next proxy.
- FastAPI maps the external Clerk id → **its own internal `u_<hex>` id** (`backend/users.py`);
  nothing downstream references the Clerk id, so the auth provider is swappable at one lookup.
- **No external DB, no Supabase** (removed). Back up `data/` and you have everything.

---

## 4. Tech stack

**Backend** (Python ≥3.12, run with `uv`): FastAPI, uvicorn, pandas, plotly, kaleido
(chart PNGs via Chrome), weasyprint (PDF, optional), scipy, xgboost, scikit-learn,
sqlalchemy + psycopg2-binary + pymysql (connectors), httpx, markdown, openpyxl.

**Frontend** (Next.js 16 App Router, React 19, JSX not TS): `@clerk/nextjs`, `lucide-react`,
`plotly.js` + `react-plotly.js` (only via `LazyPlot.jsx`), `react-markdown`,
Tailwind CSS 3.4. `output: 'standalone'` for Docker.

---

## 5. Repository layout

```
backend/
  main.py            (1823) FastAPI app: all endpoints, middleware, ownership, analytics, SSE pipeline
  dashboard.py        (976) dashboard engine: spec, chart builder, ops protocol, sync/living-monitor
  prediction_engine.py(1545) deterministic ELO/Poisson/Dixon-Coles/XGBoost (dormant unless ratings)
  report_builder.py   (592) enriched council prompt + structured report dict + follow-ups
  data_analysis.py    (580) profiling, quality notes, auto-charts, data excerpt, anomalies
  pdf_export.py       (501) HTML/PDF export (WeasyPrint → headless Chrome → HTML fallback)
  research.py         (453) topic-generic web research (Perplexity Sonar) + plan_searches()
  council.py          (374) 3-stage council (answer → anonymous peer review → chairman)
  storage.py          (219) JSON conversation store, is_valid_id guard, share index
  config.py           (125) static constants + dynamic settings getters (BYO-key aware)
  users.py            (104) local user registry (Clerk id → u_<hex>), current_user_ctx ContextVar
  openrouter.py       (103) async LLM client (max_tokens cap + 402 retry)
  gemini.py            (91) direct Google Gemini routing (bypasses OpenRouter when key present)

frontend/app/          (thin server pages + route handlers + SEO file-conventions)
  page.js              → marketing Landing (+ SoftwareApplication JSON-LD)
  studio/page.js       → AppShell (the workspace)         chat/[id]/page.js → AppShell
  dashboard/[id]/page.js → Dashboard (editor)             share/[shareId]/page.js → SharedView (public RO)
  admin/page.js        → AdminPanel (password-gated)       privacy|terms/page.js → LegalPage
  api/backend/[...path]/route.js → the auth proxy
  layout.js            → root metadata + Clerk provider    template.js → page-transition wrapper
  sign-in|sign-up/...  → Clerk auth pages
  robots.js sitemap.js manifest.js opengraph-image.js icon.js → SEO (OG + favicon generated via next/og)
  globals.css          → oklch dark theme tokens + all keyframes/animations

frontend/components/
  AppShell.jsx (627)   conversation state, SSE handling, routing (usePathname-derived id)
  Dashboard.jsx (534)  the dashboard EDITOR (header, toolbar, sync, assistant, share)
  DashboardWidgets.jsx (411)  the SHARED widget renderer (editor + public read-only, handler-gated)
  ChatInterface.jsx (480) research-run view (progress → report → follow-ups)
  Home.jsx (333)       workspace hub (build-dashboard + deep-research flow cards)
  Report.jsx (247)     research report sections + export + share + "open as dashboard"
  Sidebar.jsx (259)    dashboards-first + dated research; AccountPanel footer
  SharedView.jsx       public read-only render (reuses DashboardWidgets, no handlers)
  ShareModal.jsx       create/copy/revoke a public link
  AdminPanel.jsx       /admin dashboard (password prompt → stats + users + 14-day activity)
  AccountPanel.jsx     sidebar footer: AI-keys row + Clerk UserButton + sign-out
  ApiKeysModal.jsx     per-user OpenRouter/Gemini key entry + live validate
  WidgetEditor.jsx     form-based add/edit chart+metric
  ConnectSource.jsx    DB/API connector modal
  ExportButton.jsx     PDF/HTML export trigger
  ActivityPanel.jsx    live research activity + sources (chat pages only)
  ...plus report/prediction sub-components (AIAnalysis, ChairmanSynthesis, CouncilOpinions,
     PredictionSuite, CombinedPrediction, CustomWeights, PredictionCharts, InternetFindings,
     Charts, ComparisonTable, DataFilters, Stage3, AnalysisProgress, CommandPalette, ...)
  ui/    Button Field Input Modal Skeleton   (the custom kit — build new UI from these)
  landing/  Landing Blocks FeatureDemos Reveal   (marketing page + animated CSS demos)
  legal/    LegalPage   (shared shell for /privacy and /terms)
  lib/api.js (382)     the ONLY fetch layer; API_BASE='/api/backend'
  lib/constants.js     shared constants

data/  (GITIGNORED runtime state)  conversations/  uploads/  exports/  users.json
       settings.json  sources.json  shares.json  analytics.jsonl  error.log
```

---

## 6. Backend API (27 endpoints, all under the proxy)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/analyse` | owner | **Core pipeline** (SSE): data analysis → research → council → report → auto-dashboard |
| POST | `/api/reanalyse` | owner | Re-run analysis on a filtered dataset (in-memory) |
| POST | `/api/upload` | user | Upload CSV/Excel/JSON (50MB cap, sanitised name) |
| POST | `/api/connect` | user | Import from SQL DB (SELECT-only) or REST API → materialise as CSV; persist connector cfg |
| GET | `/api/conversations` | owner-scoped | List conversations (owner-filtered) |
| POST | `/api/conversations/create` | user | Create with client-generated id |
| GET | `/api/conversations/{id}` | owner | Full record |
| GET | `/api/conversations/{id}/status` | owner | Poll pipeline stage/progress |
| GET | `/api/dataset/{id}` | owner | Raw dataset rows (capped) for the table |
| POST | `/api/dashboard` | owner/user | Standalone dashboard from a file, OR (re)build spec on a record |
| POST | `/api/dashboard/{id}/chat` | owner | **The editor**: NL message → LLM ops → in-place mutation; or direct `ops` |
| GET | `/api/dashboard/{id}/suggestions` | owner | Prebuilt one-click components from the dataset |
| POST | `/api/dashboard/{id}/sync` | owner | **Living monitor**: re-pull data + re-run pinned research → `changes` feed |
| POST | `/api/conversations/{id}/share` | owner | Mint/return a public share token |
| DELETE | `/api/conversations/{id}/share` | owner | Revoke |
| GET | `/api/public/{share_id}` | **none** | Read-only allowlist view (no auth; token is the capability) |
| GET | `/api/export/{id}` | owner | Export report/dashboard as PDF or HTML (`?format=`, `?mode=dashboard`) |
| GET | `/api/export-format` | any | Which format the server can produce |
| GET/POST | `/api/account/settings` | user | Per-user BYO AI keys (masked) |
| POST | `/api/account/validate` | user | Live-check an OpenRouter key |
| GET | `/api/admin/overview` | **ADMIN_PASSWORD** | Users + analytics (X-Admin-Password header) |
| GET/POST | `/api/settings*` | **blocked at proxy** | Global dev-mode settings (never reachable from browser) |
| POST | `/api/error-log` | any | Best-effort client error logging |

**Dashboard ops protocol** (LLM emits specs, engine draws deterministically):
`add_chart, update_chart, remove_widget, add_metric, update_metric, move_widget,
add_table, add_comparison, add_analysis, add_key_findings, add_text, update_text,
add_insight` (→ live research, stores `query`+`as_of`), `rename_dashboard`.
**Chart types**: line, bar, scatter, histogram, pie, box, heatmap, area, treemap
(with `group_by` + `agg`). **Templates**: minimal / overview / full / kpi / visual + a `focus` column.

---

## 7. Feature catalog

1. **Instant dashboards** — one click from any dataset (no AI): metrics, 9 chart types,
   entity comparison (radar), searchable/sortable/paginated data table + CSV, text notes.
2. **Chat + manual editing** — the assistant applies structured ops in place; forgiving
   NL parsing (infers typos). Component gallery, form editors, reorder arrows, inline rename.
3. **Deep research (AI council)** — `plan_searches()` writes 3 topic-generic queries;
   Perplexity Sonar gathers facts; N models answer independently → anonymous peer review →
   chairman synthesis → cited report + follow-up questions; findings auto-pinned to a dashboard.
4. **Living monitor / sync** — "Update" re-pulls connector data (metric deltas via `_delta_str`)
   AND re-runs each pinned research insight's stored `query` (new-source diff) → `changes`
   feed + `watch_log` + `last_synced`.
5. **Connectors** — SQL (Postgres/MySQL/SQLite, SELECT-only guard) or REST API; config in
   `data/sources.json`; dashboards Refresh from source.
6. **Prediction engine** — ELO Monte-Carlo, ELO-Poisson/Dixon-Coles, XGBoost (needs match-history
   CSV + libomp); ensembled with internet (35%) + council (25%); dataset ensemble 40% fallback.
7. **Exports** — ONE dark structured layout for reports + dashboards; PDF chain
   WeasyPrint → headless Chrome `--print-to-pdf` → HTML fallback (`BROWSER_PATH` overrides).
8. **Public share links** (NEW) — read-only `/share/<token>`; allowlist payload; dataset only
   when a table/comparison widget exists; revocable. Share button on dashboard + report.
9. **Super admin** (`/admin`) — password-gated (ADMIN_PASSWORD); users, per-user
   research/dashboards/events, 14-day activity from `data/analytics.jsonl`.
10. **Marketing landing** (NEW) — animated CSS feature demos, use-cases, FAQ; full SEO
    (metadata, OG image, robots, sitemap, manifest, SoftwareApplication + FAQPage JSON-LD).

---

## 8. Auth, ownership & security model

- **Clerk = identity only** (sign in/up/session/out). Auth-OPTIONAL: with empty
  `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` the app runs in **open dev mode** (no login, global
  keys, all data visible). Set the keys → route protection + per-user scoping turn on.
- **Ownership** (`backend/main.py`): `_owned(id, req)` 404s non-owners AND ownerless legacy
  records when an identity is present; `_stamp_owner` at create sites; list filtered by owner.
- **`PROXY_SHARED_SECRET`** (both sides): when set, the backend 403s any `/api` request
  lacking `x-proxy-secret` — so a publicly reachable backend only accepts the Next proxy.
- **BYO keys**: `config.get_api_key()/get_gemini_api_key()` read the request-scoped user
  (`current_user_ctx` ContextVar bound in middleware) FIRST — identity present → only that
  user's keys (None → pipeline hard-stops). Owner's keys are never spent on users.
- **Admin**: `/admin` gated by `ADMIN_PASSWORD` (X-Admin-Password header, `secrets.compare_digest`),
  independent of Clerk; proxy + middleware exempt `api/admin` from the sign-in requirement.
- **Share security**: token = `secrets.token_urlsafe(9)` (~72 bits); `is_valid_id` gates the
  share_id before any lookup; the public payload is an explicit ALLOWLIST (never owner_id,
  file paths, `file.source` connector creds, or chat history).

**Security incident this session (fixed, but LEARN FROM IT):** an adversarial multi-agent
review found **two proven criticals** introduced by the share feature. Root cause:
**Next.js 16 decodes `%2f` inside a route/`[...path]` segment into a real slash**, and
`fetch()`/`new URL()` then collapse `..`. So `/share/..%2f..%2fapi%2fconversations` (and the
same via the proxy) retargeted OTHER backend endpoints through a request that carried the
proxy secret but **no identity** → backend open-mode → cross-tenant leak of connector
credentials + chat history, no valid token needed. Fixes applied (all in the working tree):
(1) `encodeURIComponent(shareId)` in the share page's server fetch; (2) the proxy rejects any
`..`/`.` path segment before the prefix checks; (3) middleware only grants the public/admin
auth exemption for CLEAN paths (no `%`, no `..`); (4) exemption bounded to `api/public/`.
**Rule going forward: never interpolate a decoded route param into a URL; string-prefix auth
exemptions on un-normalized paths are an auth-bypass class.**

---

## 9. Data & persistence (all in `data/`, gitignored)

`conversations/<id>.json` (records; carry `owner_id`, optional `dashboard` spec, `share_id`),
`uploads/` (datasets + connector-materialised CSVs), `exports/`, `users.json` (registry +
per-user AI keys), `settings.json` (global dev-mode keys), `sources.json` (connector configs),
`shares.json` (share-token → conversation-id index; lives in `data/`, the PARENT of the
conversations dir, so `list_conversations` never iterates it), `analytics.jsonl` (event log).

---

## 10. Running locally

```bash
# Backend (ALWAYS from project root — relative imports)
uv run python -m backend.main            # port 8001

# Frontend
cd frontend && npm install && npm run dev # port 3000
```
Open dev mode needs no keys. To exercise BYO keys / auth, set Clerk keys in
`frontend/.env.local`. To exercise the pipeline, set an OpenRouter key (per-user via the
"AI keys" modal, or global via backend `.env` in open mode).

---

## 11. Known issues / tech debt (for the next agent)

- ~~JSON store is racy~~ **FIXED (v1.0.0-launch, Phase 1).** All state writes go through
  `backend/atomic.py` (tmp-file + fsync + `os.replace`), and conversation read-modify-write goes
  through `storage.conversation_lock` / `update_conversation` (re-read under lock). The lock is
  in-process → **single backend replica assumed** (see `DECISIONS.md`).
- **`_dataset_payload` re-reads the file from disk on every public view** — fine at current
  scale; cache if share traffic grows.
- **`prediction_engine.py` is large (1545 lines) and mostly dormant** — only activates on
  ratings-like data. Deliberate; leave unless the product pivots.
- **PDF export** depends on Chrome/Chromium on the host (WeasyPrint native libs are optional).
  Locally WeasyPrint libs are absent → the Chrome path is used (verified working).

---

## 12. Immediate next steps (recommended order)

1. **Commit the working tree** (share + landing + SEO + tests + the critical security fixes).
   The user commits/pushes on request only — confirm before pushing.
2. Consider the storage atomicity/locking fix (§11) — it's the most real correctness gap.
3. Pick from the feature roadmap (§15).

---

## 13a. Testing (added — the project now has real test suites)

Run everything from the project root via the **Makefile** (`make help` lists all targets):

| Command | What it runs |
|---|---|
| `make test-backend` | **71 pytest** tests — hermetic (temp data dir, no network): `is_valid_id`/share lifecycle, dashboard chart builder + every op, templates, BYO-key resolution, data profiling, and FastAPI TestClient integration (upload→dashboard→edit→share→public allowlist→revoke, ownership 404s, admin gate). |
| `make e2e` | **Playwright** browser e2e — landing/SEO + the deterministic upload→dashboard→share→public journey. `make e2e-install` first (one-time chromium download). Auto-starts/reuses both servers. |
| `make smoke` | **15-check** full-stack HTTP smoke (`scripts/smoke.mjs`) over a running stack — marketing/SEO routes, the `%2f` traversal guards, and the golden API path. |
| `make test` | backend pytest + frontend production build. |
| `make build` | backend import check + `next build`. |

Test files: `backend/tests/` (pytest), `frontend/e2e/` (Playwright), `scripts/smoke.mjs`.
CI ordering: `make install && make test && make e2e-install && make e2e`.

## 13. Verification playbook

- **Backend import**: `uv run python -c "import backend.main"`.
- **Frontend build**: `cd frontend && npm run build` (catches SSR breakage).
- **Live smoke**: restart backend from project root; `curl localhost:8001/api/export-format`;
  upload → create dashboard → sync; `curl -H 'x-admin-password: …' localhost:8001/api/admin/overview`.
- **Share security regression**: `/api/backend/api/public/..%2f..%2fapi%2fconversations`
  must be **400** (not a data leak); `/share/..%2f..%2fapi%2fconversations` must render
  "unavailable"; a legit `/share/<token>` must render the read-only dashboard.
- **Model ids**: verify any new OpenRouter model id against the live API before adding —
  invalid ids 404 silently and drop from the council. (`anthropic/claude-opus-4.8` 402s on
  the owner's dev key.)

---

## 14. Sharpest gotchas (the ones that bite)

1. **Run the backend from the project root** (`python -m backend.main`) or you get
   `ModuleNotFoundError: backend` and a silent dead process.
2. **Restart the backend after editing backend code** — it caches modules; stale code looks
   like a frontend bug.
3. **Backend is port 8001** (8000 is taken by another of the owner's apps).
4. **Plotly only via `components/LazyPlot.jsx`** (`next/dynamic`, `ssr:false`) — importing
   plotly.js directly breaks SSR.
5. **Never put a non-conversation `.json` in `data/conversations/`** — `list_conversations`
   iterates it (now guarded to skip non-records, but keep indexes like `shares.json` in `data/`).
6. **Don't interpolate a decoded route param into a URL** (see §8 — the `%2f` traversal class).
7. Charts carry a non-serialisable `dataframe` key in memory — strip before persisting.

---

## 15. Feature roadmap (recommended, prioritised)

Ranked by leverage for a product whose promise is "living dashboards that tell you what changed."

**Tier 1 — lean into the differentiator**
1. **Scheduled auto-sync + "what changed" digest.** Cron the existing `sync_dashboard` per
   dashboard (daily/hourly) and email the changes feed. Turns the manual "Update" into a true
   monitor. Backend already produces the `changes` list + `watch_log`; needs a scheduler
   (APScheduler) + an email sender + a per-dashboard schedule setting.
2. **Threshold alerts.** "Notify me when revenue drops >10% or a metric crosses X." Evaluated
   during sync; reuses `_delta_str`. Pairs with #1.
3. **Storage durability** (from §11): atomic writes (`tmp + os.replace`) + a per-conversation
   lock in `save_conversation`. Not a feature, but a go-live reliability must once traffic is real.

**Tier 2 — dashboard power**
4. **Drag-to-rearrange + resizable widgets** (grid layout). Today: reorder arrows only.
   Persist an `{x,y,w,h}` per widget; render with CSS grid / a light grid lib.
5. **Cross-filtering.** Click a bar/segment → filter the whole dashboard (reuses `/api/reanalyse`).
6. **Per-share controls.** A "hide raw data table" toggle and an optional expiry/password on
   share links (backend already gates the dataset on a table/comparison widget).
7. **Embeddable dashboards.** An `/embed/<token>` iframe variant of the read-only share.

**Tier 3 — reach & collaboration**
8. **More connectors:** Google Sheets, BigQuery, Snowflake, Airtable (SQLAlchemy covers some).
9. **Team workspaces / share-with-edit.** Currently share is read-only + single-owner; add
   membership so a dashboard can have editors.
10. **AI-spend meter.** Since keys are BYO, show an estimated per-user token/cost tally
    (OpenRouter's `/key` usage endpoint is already called by `/api/account/validate`).
11. **Light theme + theme toggle** (currently dark-only; tokens are already CSS variables).

Quick wins: #3 (durability), #6 (per-share toggle), #10 (spend meter).
