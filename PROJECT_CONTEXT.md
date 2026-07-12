# datavisual.studio — Context Primer

> **You (the reader) are an AI assistant being handed this project to continue work on it.**
> This document is self-contained: it tells you what the product is, how it's built, its
> data model, every feature, the current state, and how to run and test it. Read it fully
> before making changes. Companion files in the repo: `CLAUDE.md` (terse technical gotchas),
> `PROJECT_AUDIT.md` (deeper file-by-file audit), `DEPLOYMENT.md` (hosting), `README.md`.
>
> _Snapshot date: 2026-07-07 · Repo: `git@github.com:4mohdisa/datavisual.studio.git` · branch `main`._

---

## 1. What the product is (one paragraph)

**datavisual.studio** is a free, data-visualisation-first analytics platform — think
"**Power BI + an AI research assistant**", positioned as a **living monitor**: you connect
data, build a dashboard, pin the questions that matter, and one click keeps both your
numbers and the live web in sync while telling you *what changed since last time*. The
**core artifact is the dashboard** — a persistent, editable widget spec. An AI "council"
research pipeline feeds findings onto dashboards. It's **free**; users **bring their own AI
keys** (OpenRouter required, Google Gemini optional) and pay those providers directly.

---

## 2. Tech stack & architecture

**Monorepo, two apps** (each in its own folder):

```
Browser
  │  Clerk session cookie
  ▼
frontend/  — Next.js 16 App Router, React 19, JSX (not TS), Tailwind 3.4, port 3000
  • marketing/legal pages, app shell, dashboards, public share views
  • middleware.js       → Clerk route protection (only when Clerk keys are set)
  • app/api/backend/[...path]/route.js → THIN AUTH PROXY:
        verify Clerk → forward to FastAPI with identity headers
        (x-clerk-user-id / x-user-email / x-user-name) + x-proxy-secret → stream response back
  ▼  server-to-server
backend/  — FastAPI (Python ≥3.12, run with `uv`), port 8001  ← OWNS ALL DATA
  • all business logic, LLM calls, research pipeline, exports, prediction engine
  • ALL state on local disk under data/   (NO external database, NO Supabase)
```

**Hard invariants (do not break these):**
1. The browser **never** calls FastAPI directly — always through the Next proxy at `/api/backend/*`.
2. FastAPI maps the external Clerk id → **its own internal `u_<hex>` id** (`backend/users.py`).
   Nothing downstream references the Clerk id, so the auth provider is swappable at one lookup.
3. There is **no database**. Everything is JSON/files under `data/`. Back up `data/` = back up everything.
4. **Plotly is rendered ONLY via `frontend/components/LazyPlot.jsx`** (`next/dynamic`, `ssr:false`).
   Importing `plotly.js` directly breaks SSR.
5. **Run the backend from the project root**: `uv run python -m backend.main` (relative imports),
   and **restart it after backend edits** (it caches modules — stale code looks like a frontend bug).
6. Backend port is **8001** (8000 is taken by another of the owner's apps).

**Backend dependencies:** fastapi, uvicorn, pandas, plotly, kaleido (chart PNGs via Chrome),
weasyprint (PDF; optional — Chrome fallback exists), scipy, xgboost, scikit-learn,
sqlalchemy + psycopg2-binary + pymysql (DB connectors), httpx, markdown, openpyxl, pytest (dev).

**Frontend dependencies:** @clerk/nextjs, lucide-react, plotly.js + react-plotly.js,
react-markdown, tailwindcss; `@playwright/test` (dev). `next.config.mjs` uses `output: 'standalone'` for Docker.

---

## 3. Data model & persistence (this project's "database")

**There is no SQL/NoSQL database.** Persistence is JSON files on the backend's local disk under
`data/` (gitignored). Layout:

| Path | What |
|---|---|
| `data/conversations/<id>.json` | **The main record.** One per dashboard/research run. Holds the dashboard spec, pipeline output, `owner_id`, optional `share_id`. |
| `data/uploads/` | Uploaded datasets + connector-materialised CSVs. |
| `data/exports/` | Generated PDF/HTML exports. |
| `data/users.json` | User registry: Clerk id → `{ id: "u_<hex>", email, name, settings: { openrouter_api_key, gemini_api_key } }`. **Per-user AI keys live here.** |
| `data/settings.json` | Global dev-mode AI keys (only used in open mode, no Clerk). |
| `data/sources.json` | Saved connector configs (SQL URL / REST endpoint) so dashboards can Refresh. |
| `data/shares.json` | Share-token → conversation-id index. **Lives in `data/`, the PARENT of the conversations dir**, so `list_conversations()` never iterates it. |
| `data/analytics.jsonl` | Append-only event log (feeds the `/admin` panel). |

**Conversation record shape** (the important fields):
```jsonc
{
  "id": "uuid",
  "created_at": "ISO-8601",
  "title": "…",
  "mode": "dashboard" | "chat",        // "dashboard" = standalone build; "chat" = research run
  "owner_id": "u_<hex>" | null,          // null = created in open dev mode
  "share_id": "<token>" | absent,        // present iff a public link exists
  "file": { "path": "data/uploads/…", "source": {…connector cfg…} },  // NEVER exposed publicly
  "pipeline": { … research output: data_summary, internet_findings, council, report … },
  "messages": [ … research run messages, incl. the full_report … ],
  "dashboard": {                          // THE core artifact — the widget spec
    "title": "…",
    "widgets": [ Widget, … ],
    "history": [ {role, content}, … ],    // dashboard-assistant chat (NEVER exposed publicly)
    "last_synced": "ISO-8601",
    "watch_log": [ … sync snapshots … ]
  }
}
```

**Widget** (the unit the dashboard renders). `kind` ∈ `metric | chart | insight | comparison | table | text`:
```jsonc
{ "id": "w<hex>", "kind": "chart", "title": "Revenue by region",
  "spec": { "type": "bar", "x": "region", "y": "revenue", "group_by": …, "agg": … }, // rebuildable spec
  "plotly_json": { data, layout },   // deterministically drawn from spec
  // metric: { label, value, sub, spec }   insight: { title, text, sources[], query, as_of }
  // comparison/table: rendered from the dataset rows, no per-widget data
}
```
Chart `type` ∈ `line, bar, scatter, histogram, pie, box, heatmap, area, treemap`.
**The LLM only ever emits specs; charts are always drawn deterministically by the backend.**

---

## 4. Features (the complete catalogue)

1. **Instant dashboards** — one click from any dataset (no AI cost): metric cards, 9 chart types,
   entity comparison (radar for ≥3 metrics, grouped bar for 2), searchable/sortable/paginated data
   table + CSV export, inline text notes. Templates: `minimal / overview / full / kpi / visual` + a
   `focus` column that leads the headline metric and first charts.
2. **Edit by chat or by hand** — the **dashboard assistant** turns natural language into structured
   **ops** applied *in place* (never a rebuild). Ops: `add_chart, update_chart, remove_widget,
   add_metric, update_metric, move_widget, add_table, add_comparison, add_analysis, add_key_findings,
   add_text, update_text, add_insight` (→ runs live research, stores `query`+`as_of`), `rename_dashboard`.
   Also: a prebuilt component gallery, form editors (`WidgetEditor`), hover reorder/edit/remove.
3. **Deep research (the "AI council")** — `plan_searches()` writes 3 topic-generic web queries →
   Perplexity Sonar gathers facts → several LLMs answer independently → **anonymous peer review** →
   a **chairman** synthesises one cited report + follow-up questions. Findings auto-pin to a dashboard.
4. **Living monitor / sync** — the differentiator. "**Update**" re-pulls connector data (records metric
   value **deltas**) AND re-runs every pinned research insight's stored query (records **new sources**),
   then shows a plain-English "**what changed**" feed + `last_synced` + a `watch_log` snapshot.
5. **Data connectors** — Power BI-style import from SQL (PostgreSQL/MySQL/SQLite, **SELECT-only** guard)
   or a JSON REST API; result materialised as a CSV so every downstream feature works; config saved in
   `data/sources.json` for Refresh.
6. **Prediction engine** — deterministic ELO Monte-Carlo / ELO-Poisson (Dixon-Coles) / XGBoost, ensembled
   with internet (35%) + council (25%) probabilities. **Dormant unless the data looks like ratings.**
7. **Exports** — ONE dark structured layout for reports and dashboards; PDF chain WeasyPrint → headless
   Chrome `--print-to-pdf` → HTML fallback (`BROWSER_PATH` env overrides Chrome discovery).
8. **Public share links** — owner mints an unguessable read-only link (`/share/<token>`). Viewers need no
   sign-in and can't edit. The public payload is a strict **allowlist**: never `owner_id`, file paths,
   connector credentials (`file.source`), or chat history; the raw dataset is included **only** when a
   table/comparison widget exists (data minimization). Revocable. Share button on the dashboard header and
   the research report.
9. **Super admin** (`/admin`) — password-gated (env `ADMIN_PASSWORD`, independent of Clerk): users,
   per-user research/dashboard/event counts, 14-day activity from `data/analytics.jsonl`.
10. **Marketing landing** (`/`) — animated (pure-CSS) feature demos, use-cases, FAQ; full SEO (see §7).

---

## 5. Backend API (27 endpoints, all reached through the Next proxy)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/analyse` | owner | **Core pipeline (SSE)**: analysis → research → council → report → auto-dashboard |
| POST | `/api/reanalyse` | owner | Re-run analysis on a filtered dataset (in-memory) |
| POST | `/api/upload` | user | Upload CSV/Excel/JSON (50 MB cap, sanitised filename) |
| POST | `/api/connect` | user | Import from SQL DB (SELECT-only) or REST API → materialise as CSV |
| GET | `/api/conversations` | owner-scoped | List (filtered to the signed-in owner) |
| POST | `/api/conversations/create` | user | Create with a client-generated id |
| GET | `/api/conversations/{id}` | owner | Full record |
| GET | `/api/conversations/{id}/status` | owner | Poll pipeline stage/progress |
| GET | `/api/dataset/{id}` | owner | Raw dataset rows (capped) for the table |
| POST | `/api/dashboard` | owner/user | Standalone dashboard from a file, OR (re)build spec on a record |
| POST | `/api/dashboard/{id}/chat` | owner | **The editor**: NL message → LLM ops → in-place mutation; or direct `ops` |
| GET | `/api/dashboard/{id}/suggestions` | owner | Prebuilt one-click components from the dataset |
| POST | `/api/dashboard/{id}/sync` | owner | **Living monitor**: re-pull + re-research → `changes` feed |
| POST | `/api/conversations/{id}/share` | owner | Mint/return a public share token |
| DELETE | `/api/conversations/{id}/share` | owner | Revoke |
| GET | `/api/public/{share_id}` | **none** | Read-only allowlist view (token is the capability) |
| GET | `/api/export/{id}` | owner | Export PDF/HTML (`?format=`, `?mode=dashboard`) |
| GET | `/api/export-format` | any | Which format the server can produce |
| GET/POST | `/api/account/settings` | user | Per-user BYO AI keys (returned masked) |
| POST | `/api/account/validate` | user | Live-check an OpenRouter key |
| GET | `/api/admin/overview` | `ADMIN_PASSWORD` | Users + analytics (via `X-Admin-Password` header) |
| GET/POST | `/api/settings*` | **blocked at the proxy** | Global dev-mode settings — never reachable from the browser |
| POST | `/api/error-log` | any | Best-effort client error logging |

Ownership is enforced by `_owned(id, req)` (404s non-owners AND ownerless legacy records when an identity
is present). `_stamp_owner` runs at create sites. No identity present (open dev mode) = everything visible.

---

## 6. Auth, keys & security model

- **Clerk = identity only** (sign in/up/session/out). **Auth-optional**: empty
  `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` → **open dev mode** (no login, global keys, all data visible).
  Set the keys → route protection + per-user scoping turn on automatically.
- **BYO keys**: `config.get_api_key()` / `get_gemini_api_key()` read the request-scoped user
  (`current_user_ctx` ContextVar bound in middleware) FIRST — identity present → only that user's keys
  (None → pipeline hard-stops with guidance). **The owner's keys are never spent on users' requests.**
- **`PROXY_SHARED_SECRET`** (same value both sides): when set, the backend 403s any `/api` request lacking
  the `x-proxy-secret` header — so a publicly-reachable backend only accepts the Next proxy.
- **Admin** (`/admin`): gated by `ADMIN_PASSWORD` (constant-time compare), independent of Clerk.
- **Share security lesson (important, already fixed):** Next.js 16 decodes `%2f` inside route/`[...path]`
  segments into real slashes, and `fetch()`/`new URL()` then collapse `..`. A path-traversal auth-bypass
  was found and fixed by: `encodeURIComponent` on the share id in the server fetch; the proxy rejects any
  `..` path segment; the middleware only grants the public/admin exemption for clean paths (no `%`, no `..`);
  and the exemption is bounded to `api/public/`. **Rule: never interpolate a decoded route param into a URL,
  and never gate auth exemptions on an un-normalized path prefix.**

---

## 7. SEO

`layout.js` sets metadataBase + a title template + OpenGraph/Twitter/robots. File-convention routes:
`app/{robots,sitemap,manifest,opengraph-image,icon}.js` — the OG social card and favicon are **generated at
request time via `next/og`** (no binary assets). JSON-LD: `SoftwareApplication` on the landing + a `FAQPage`.
App/admin/share routes are `noindex`; marketing + legal pages are indexable. `NEXT_PUBLIC_SITE_URL` drives
canonical/sitemap URLs (defaults to `https://datavisual.studio`).

---

## 8. Testing (this is a finalized, tested codebase)

Run everything from the **project root** via the **Makefile** (`make help` lists targets):

- **`make test-backend`** — **pytest** (`backend/tests/`, **71 tests**, hermetic temp data dir, no network):
  trust boundaries (`is_valid_id`, share lifecycle), the dashboard chart builder + every op, templates,
  BYO-key resolution, data profiling, and FastAPI **TestClient integration** (upload → dashboard → edit →
  share → public allowlist → revoke, ownership 404s, admin gate). `conftest.py` monkeypatches the data dir.
- **`make e2e`** — **Playwright** (`frontend/e2e/`, **6 tests**): landing/SEO + the deterministic
  upload→dashboard→share→public journey. `make e2e-install` once to get chromium.
- **`make smoke`** — full-stack HTTP smoke (`scripts/smoke.mjs`) over a running stack (golden path + the
  `%2f` traversal guards + SEO routes).
- **`make test`** = pytest + `next build`. **`make build`** = backend import check + `next build`.
- Quick manual checks: `uv run python -c "import backend.main"`, `cd frontend && npm run build`.

The tests are real and have already caught bugs (an `is_valid_id("..")` gap; a degenerate 2-metric radar).

---

## 9. How to run locally

```bash
make install                 # uv sync + npm install (both apps)
make dev                     # runs backend (8001) + frontend (3000) together; Ctrl-C stops both
# or individually:
uv run python -m backend.main            # backend — ALWAYS from project root
cd frontend && npm run dev               # frontend
```
Open dev mode needs **no keys**. To exercise auth/BYO keys, put Clerk keys in `frontend/.env.local`.
To exercise the AI pipeline, set an OpenRouter key (per-user via the "AI keys" modal, or global via the
backend `.env` in open mode). `data/settings.json` currently holds a working OpenRouter key for dev;
note `anthropic/claude-opus-4.8` returns 402 (too costly) on that key — pick verified-affordable model ids.

---

## 10. Current state (READ THIS)

- **Everything builds and all tests pass.** `make build` green; 71 pytest + 6 e2e + smoke all pass.
- **⚠️ There is a large uncommitted working tree (~43 files).** It contains the share feature, the animated
  SEO landing, all SEO files, the test suites, the Makefile, the polished auth pages, the entity-comparison
  radar fix, and the **two critical `%2f` security fixes**. **The very first action for anyone continuing is
  to commit this** (the owner commits/pushes on request only — confirm before pushing). If someone were to
  `git stash`/reset, they would reintroduce the security holes.
- **Last commit:** `ef08fdf docs: drop upstream fork credit from README`. Branch `main`,
  remote `git@github.com:4mohdisa/datavisual.studio.git`.
- **Runtime data present** in `data/` (gitignored): ~16 conversations, 3 users.
- **Deployment is ready**: `docker-compose.yml` (backend image installs Chromium; frontend standalone),
  `backend/Dockerfile`, `frontend/Dockerfile`, and `DEPLOYMENT.md` with the AWS path + env checklist.

---

## 11. Known issues / tech debt

- **JSON store is racy (low severity, pre-existing).** `storage.save_conversation` is a blind whole-file
  overwrite (no tmp-file + `os.replace`) and there's no per-conversation write lock (only `_shares_lock`
  around the two share functions). Concurrent writers on the same record can clobber each other (worst case:
  a freshly minted share link 404s). **Durable fix:** atomic writes + a per-conversation lock used by all callers.
- **Dashboard-assistant sometimes gives thin answers** to non-edit *questions* ("what is this report about?")
  because the editor prompt is tuned to emit ops. Improving the "answer a question vs. apply an edit" branch
  is a good UX win.
- **`_dataset_payload` re-reads the file from disk on every public view** — fine now; cache if share traffic grows.
- **`prediction_engine.py` (1545 lines) is large and mostly dormant** — deliberate; leave unless the product pivots.

---

## 12. Suggested next features (prioritised)

1. **Scheduled auto-sync + a "what changed" email digest** — the natural evolution of the living monitor
   (the sync already produces a changes feed; add cron + email).
2. **Threshold alerts** — "notify me when revenue drops >10% or a new source contradicts the thesis".
3. **Storage durability** (atomic writes + locking) — the one real reliability gap before scale.
4. Drag-to-rearrange / resize widgets; cross-filtering between charts; dashboard embeds (`<iframe>` of the
   share view); more connectors (Google Sheets, BigQuery); team edit-sharing; an AI-spend meter; light theme.

---

## 13. The sharpest gotchas (things that bite)

1. Run the backend from the **project root** or you get `ModuleNotFoundError: backend` + a silent dead process.
2. **Restart the backend after backend edits** (module caching).
3. Backend is **port 8001**, not 8000.
4. **Plotly only via `LazyPlot.jsx`** (ssr:false) — direct import breaks SSR.
5. Never drop a non-conversation `.json` into `data/conversations/` — `list_conversations` iterates it
   (now guarded to skip non-records; keep indexes like `shares.json` in `data/`, the parent).
6. **Never interpolate a decoded route param into a URL** (the `%2f` traversal class — see §6).
7. Charts carry a non-serialisable `dataframe` key in memory — strip before persisting.
8. A radar/scatterpolar needs **≥3 numeric columns** to read as a shape (fixed: 2-metric case renders a bar).
