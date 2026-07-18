# Architecture

How datavisual.studio is put together, and the reasoning behind the decisions that aren't obvious from
the code. If you're evaluating the engineering, start here.

## The one-paragraph version

A stranger's browser talks to a **Next.js app** (Vercel). Anything data-related is proxied through a
single authenticated Next route to a **FastAPI backend** (a separate origin — an AWS box), which keeps
all state as **JSON files on local disk** under `data/`. The LLM is never trusted with arithmetic: it
emits **query specs**, and a deterministic Python engine executes them, so every number the product shows
can be defended. There is **no database** — that's a deliberate constraint, explained below.

## Request path

```
Browser
  │  all data calls go through lib/api.js → same-origin /api/backend/*
  ▼
Next.js  (Vercel)
  ├─ app/…                     server + client pages (marketing, /studio, /dashboard/[id], /share/[t], /demo)
  ├─ middleware.js             Clerk: protects app routes, leaves marketing/public routes open
  └─ app/api/backend/[...path] the ONLY browser→backend door. Verifies the Clerk session, attaches
                               trusted identity headers (x-clerk-user-id / x-user-email / x-user-name)
                               + x-proxy-secret, forwards to FastAPI, streams the response back.
  ▼  (server-to-server; a separate origin in prod: Vercel ↔ AWS)
FastAPI  (:8001, AWS)
  ├─ main.py                   endpoints + middleware (proxy-secret guard, per-user+per-IP rate limit,
  │                            security headers, request-scoped identity)
  ├─ dashboard.py / query.py   the dashboard spec engine + deterministic query execution
  ├─ answer_guard.py           numeric grounding — refuses to state a number it can't defend
  ├─ data_analysis.py          profiling, column measure classification (stock/flow/ratio), auto-charts
  ├─ research.py / council.py  the deep-research pipeline (3 web searches → 3-stage LLM council)
  ├─ storage.py + atomic.py    read-modify-write JSON under a per-conversation lock, atomic on disk
  ├─ crypto.py                 users' API keys encrypted at rest (Fernet, keyed off SECRET_KEY)
  ├─ users.py                  Clerk id → our own u_<hex> id (auth provider swappable at one lookup)
  └─ ssrf.py / ratelimit.py    connector egress guard + in-process token-bucket limiter
  ▼
data/   (the entire "database")
  conversations/*.json · uploads/ · exports/ · users.json · sources.json · settings.json · analytics.jsonl
```

The **direct-upload carve-out** is the one exception to "the browser never calls the backend directly":
files >4.5 MB POST straight to the backend origin, authorized by a short-lived HMAC upload ticket the
Next server mints. This exists because Vercel serverless caps request bodies; it's gated by the ticket
(constant-time compare, expiring, single-use, traversal-rejecting), not the proxy secret.

## Where things live

- **`backend/`** — FastAPI package. `main.py` is the HTTP surface; everything else is a focused module.
  Run it as `python -m backend.main` from the repo root (relative imports), port **8001**.
- **`frontend/`** — Next.js 16 App Router, JSX, Tailwind. `app/` holds thin pages; `components/` the UI
  (`components/ui/` is the primitive kit); `lib/api.js` is the **only** fetch layer. Plotly is loaded
  **only** through `components/LazyPlot.jsx` (importing plotly.js at module scope breaks SSR).
- **`data/`** — all runtime state, gitignored. Backing this directory up backs up everything.
- **`scripts/`** — `backup.sh`, `restore-test.sh`, `smoke.mjs`. **`Makefile`** is the task runner
  (`make help`).

## Invariants (do not break these)

1. **The LLM emits specs; Python computes.** The model turns a question into a JSON query spec; the
   deterministic engine (`query.py`) executes it and phrases the answer *from the result*. The model never
   does arithmetic. This is the whole reason the product can be trusted with numbers.
2. **Numeric grounding.** Every number in an answer must appear in the executed result or be a shown
   derivation, or the answer fails closed (`answer_guard.py`). A stock measure (MRR, headcount) is never
   summed across time — "total MRR" is the latest period, computed deterministically.
3. **BYO API keys.** Users bring their own OpenRouter/Gemini keys; the owner's key is **never** spent on a
   user's request. Keys are encrypted at rest and resolved per-request from the signed-in identity.
4. **Strict public allowlist.** The public share/demo payload is an explicit allowlist — every new field
   on a dashboard record is owner-only until proven otherwise, with a test. A structural test walks the
   router and fails the build if a new endpoint isn't classified into an auth posture.
5. **No `%2f` interpolation.** Next decodes `%2f` inside catch-all segments into real slashes; a decoded
   route param interpolated into a fetch URL is an auth-bypass class. Encode, or 400 on `..`.
6. **Single replica.** Locks, the rate limiter, and upload nonces are all in-process. Scale-out needs
   these externalised first — pin worker/replica = 1.
7. **`SECRET_KEY` travels with `data/`.** It decrypts the stored API keys; a fresh key against a restored
   `data/` makes every key unreadable, so the backend **refuses to boot** on that mismatch rather than
   silently degrading.

## Decisions worth explaining

- **No database, by design.** State is JSON on disk. For a single-tenant-per-box, single-replica product
  this removes an entire operational surface (no migrations, no connection pool, no separate backup
  target) and makes the security model tractable: one directory is the trust boundary, `is_valid_id()` is
  the one filename check, `data/` is the one thing to back up. The cost — no horizontal scale — is
  acceptable at this stage and cleanly contained (everything funnels through `storage.py` and the `u_<hex>`
  id), so a Postgres migration is a well-scoped future project rather than a rewrite.
- **A thin authenticated proxy, not CORS-to-backend.** The browser only ever talks to its own origin; the
  Next proxy is the single place that verifies the Clerk session and attaches trusted identity headers.
  The backend trusts those headers *only* when the proxy secret is present, so a public backend can't be
  addressed directly with a forged identity.
- **The council emits rankings, not prose it's trusted on.** The multi-model research council anonymises
  each model's answer ("Response A/B/…") for a blind peer-review stage, then a chairman synthesises. No
  single model's confidence is load-bearing; a model that silently drops out is surfaced, not hidden.
- **Polling by default, SSE opt-in.** The analysis pipeline runs as a background task and persists its
  stage; the client polls. SSE exists behind a flag but times out on serverless, so it isn't the default.

## Testing & CI

`make test` (pytest, hermetic) · `make e2e` (Playwright, configurable `E2E_PORT`) · Vitest component tests
· `make smoke` (full-stack HTTP) · `make restore-test` (backup→restore→keys-decrypt). CI runs the lot on
every push. See `CONTRIBUTING.md` for the contributor bar and `DEPLOY_RUNBOOK.md` to go live.
