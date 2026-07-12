# datavisual.studio

Living dashboards and AI-researched reports from your data. Turn any dataset into
an editable dashboard, then let a council of AI models research your question on the
live web — and tell you **what changed** since last time. Free: bring your own AI keys.

Built by [Mohammed Isa](https://github.com/4mohdisa) (mohdisa233@gmail.com)

## What it does

- **Instant dashboards** from CSV/Excel/JSON — or connect a SQL database
  (PostgreSQL, MySQL, SQLite) or a JSON REST API, Power BI-style. Metrics,
  9 chart types, entity comparison, a searchable/sortable data table, CSV export.
- **Edit by chat or by hand** — "add a pie of revenue by product", "remove the
  histogram". Edits apply to the same dashboard in place.
- **The living monitor** — one **Update** re-pulls your data *and* re-runs the
  research questions you pinned, then shows a plain-English feed of what moved.
- **Deep research council** — several AI models answer independently, review each
  other anonymously, and a chairman synthesises one cited report; the findings land
  on a dashboard automatically.
- **Share** any dashboard or report as a public, read-only link.
- **Export** to structured PDF or self-contained HTML.
- **Prediction engine** (ELO / Poisson / XGBoost) activates automatically when the
  data looks like ratings.

## Monorepo layout

```
backend/    FastAPI engine (Python, uv) — owns ALL data on local disk. Port 8001.
frontend/   Next.js 16 app + thin auth proxy. Port 3000.
scripts/    smoke.mjs (full-stack HTTP smoke test)
data/        runtime state (gitignored): conversations, uploads, users, exports…
Makefile     one-command tasks (make help)
```

There is **no external database** — back up `data/` and you have everything.

## Quick start

```bash
make install     # backend (uv) + frontend (npm) deps
make dev         # runs backend :8001 and frontend :3000 together (Ctrl-C stops both)
```
Open http://localhost:3000. With no Clerk keys the app runs in **open dev mode**
(no sign-in). Prefer two terminals? `make backend` and `make frontend`.

Individual pieces:
```bash
uv run python -m backend.main      # backend only (from the project root)
cd frontend && npm run dev         # frontend only
```

## Testing

```bash
make test            # backend pytest (hermetic) + frontend production build
make test-backend    # 70+ unit + integration tests (trust boundaries, dashboard
                     #   engine, ops protocol, share allowlist, ownership, admin gate)
make e2e-install     # one-time: install the Playwright chromium browser
make e2e             # browser e2e (landing, SEO, upload→dashboard→share journey)
make smoke           # full-stack HTTP smoke over a running stack (make dev first)
```

## AI keys (bring your own)

The app is free — each signed-in user brings their own **OpenRouter** (required) and
optional **Gemini** keys, saved from the sidebar **"AI keys"** panel. Keys are stored
privately with your account and only ever sent to the AI providers. In open dev mode
(no Clerk), a global `OPENROUTER_API_KEY` in the backend `.env` is used as a fallback.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) — Docker Compose or split backend/frontend hosting.
Required prod env: `PROXY_SHARED_SECRET` (both sides), Clerk keys (frontend),
`ADMIN_PASSWORD`, `FRONTEND_ORIGIN`, and `NEXT_PUBLIC_SITE_URL` (SEO/canonical).
PDF export + charts need Chromium/Chrome on the backend host (the Docker image
installs it). See also [CLAUDE.md](CLAUDE.md) for technical notes and
[PROJECT_AUDIT.md](PROJECT_AUDIT.md) for a full architecture + feature map.

## Tech stack

- **Backend:** FastAPI, pandas, Plotly, kaleido, WeasyPrint, scipy/scikit-learn/xgboost,
  SQLAlchemy, OpenRouter + Google Gemini.
- **Frontend:** Next.js 16 (App Router), React 19, Tailwind CSS, a custom UI kit,
  react-plotly.js, Clerk (identity only).

---

## 🔬 How predictions work — example

**Upload:** `elo_ratings_wc2026.csv` · **Ask:** *"Which team is most likely to win the 2026 World Cup?"*

1. pandas detects the ELO rating + country + snapshot-date columns
2. Model A runs 10,000 bracket simulations; Model B runs 10,000 Poisson (Dixon-Coles) sims
3. Ensemble average of the dataset models
4. Perplexity gathers live results, odds and expert forecasts
5. The council receives dataset + predictions + research, then peer-reviews
6. Final = `dataset 40% + internet 35% + council 25%`; the chairman explains but can't change the numbers

---

## 📄 License

MIT © [Mohammed Isa](https://github.com/4mohdisa)
