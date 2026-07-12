# datavisual.studio — Overnight Plan

Execute phases **in order**. Never skip. Never ask. Commit and push after each phase.

Companion docs: `PROJECT_AUDIT.md` (the map), `CLAUDE.md` (gotchas), `DEPLOYMENT.md`.

---

## Research findings — gaps nobody had logged

These were found by auditing the codebase against a public launch. Each is fixed in a phase below.

1. **Vercel function duration will kill the pipeline.** `/api/analyse` streams SSE through the Next
   proxy; a 4-model council runs for minutes. Serverless functions cap out first. → **Phase 2**
2. **Vercel body-size limit will kill the 50 MB upload.** The file crosses the proxy function. → **Phase 2**
3. **BYO API keys are stored in plaintext** in `data/users.json`. A volume snapshot or a box
   compromise leaks keys that cost *users* real money. → **Phase 1**
4. **`data/` is the database and has no backup.** One `docker compose down -v` and it's all gone. → **Phase 1**
5. **No rate limiting** anywhere, on a free public product. → **Phase 6**
6. **Uploads and exports are never garbage-collected.** The disk fills silently. → **Phase 6**
7. **Zero-key onboarding is missing.** Instant dashboards need *no* AI key — but nothing tells a new
   visitor that, so they hit a "add your OpenRouter key" wall before ever seeing value. Biggest
   conversion miss in the product. → **Phase 6**
8. **Owner-only fields will leak into public shares.** Phase 7 adds `schedule` / `alerts` /
   `alert_log` / `digests` to the dashboard record — which is what `/api/public/{id}` serves from. → **Phase 7**

---

## Hard rules — violating any of these fails the run

1. **Never** `git stash` / `reset --hard` / `checkout -- .` / `clean` before Phase 0 is committed. The
   uncommitted tree is the only copy of two **proven critical** security fixes.
2. **No database.** JSON under `data/`. No Postgres/SQLite/Redis/queue/APScheduler.
3. **One sanctioned new dependency: `cryptography`** (Phase 1, key encryption) — and only if it isn't
   already in the lock file. Nothing else. If you think you need another, log it in `DECISIONS.md`
   and find another way.
4. **The public share payload is a strict allowlist.** Every new field on the dashboard record is
   owner-only until proven otherwise. `unsub_token` never leaves `users.json`.
5. **`DashboardWidgets.jsx` renders BOTH the editor and the public read-only view** (handler-gated).
   Assume any UI you add there leaks into `SharedView` unless you prove it doesn't.
6. **Never interpolate a decoded route param into a URL.** Next 16 decodes `%2f` inside a route
   segment into a real slash; `fetch()`/`new URL()` then collapse `..`. That is exactly how the two
   criticals happened.
7. **The LLM emits specs only.** Chart drawing, delta computation, alert evaluation, data queries —
   all executed by deterministic Python.
8. **Owner keys are never spent on a user's request**, including background jobs.
9. **All frontend network calls go through `lib/api.js`.** No inline `fetch` in a component.
10. **All new UI is built from `components/ui/`** and the existing oklch tokens in `globals.css`.
    **Do not re-theme the app.** Keep near-black, white primary, 0.2rem radius.
11. Backend from project root, port **8001**. Plotly only via `LazyPlot.jsx`. Restart the backend
    after backend edits.
12. **Do not touch `prediction_engine.py`.**
13. No `git push --force`. Work on `main`. Do not stack branches.

## Operating rules for an unattended run

- **Never ask a question. Never wait for confirmation.** Take the smallest reversible option, log it
  in `DECISIONS.md` under "Assumptions to confirm", move on.
- **`main` must be deployable at every commit.** If you run out of time mid-phase, revert that
  phase's incomplete work, commit the green state, and write `HANDOFF.md`.
- **Abort rule:** if a phase won't go green after two honest attempts, stop it, commit what *is*
  green, note it in `HANDOFF.md`, move to the next phase. Do not burn the night on one wall.
- Where `PROJECT_AUDIT.md` §15 conflicts with this file (it recommends APScheduler; it orders
  durability third), **this file wins**.

---

# PHASE 0 — Commit the working tree

`git status` shows ~43 uncommitted files: the share feature, the SEO landing, the test suites, the
Makefile, the Docker setup — and **two `%2f` path-traversal auth-bypass fixes**. The attack:
`/share/..%2f..%2fapi%2fconversations` retargeted other backend endpoints through a request carrying
the **proxy secret but no identity** → backend fell into open mode → cross-tenant leak of connector
credentials and chat history, no valid token needed.

*(Audit §2's file list is incomplete — it omits the tests and Makefile its own §13a describes.
Trust `git status`.)*

1. Verify green: `make build`, `make test-backend`, `make e2e`.
2. Confirm these three pass, and that each is locked in by **both** a pytest and a `scripts/smoke.mjs`
   check. If not, add the missing tests **now**, inside the security commit:
   - `/api/backend/api/public/..%2f..%2fapi%2fconversations` → **400**
   - `/share/..%2f..%2fapi%2fconversations` → renders "unavailable"
   - a legitimate `/share/<token>` → renders the read-only dashboard
3. Commit in logical groups, security first: `fix(security): reject %2f path traversal…` →
   `feat(share)` → `feat(seo)` → `test:` → `build:` → `fix(dashboard): 2-metric comparison` →
   `feat(auth)`. Push.

A **pre-existing** failing test gets an `xfail` + a note. It does not block the security commit.

---

# PHASE 1 — Data safety

### 1a. Atomic writes + locking

Today `storage.save_conversation` is a blind whole-file overwrite with no per-conversation lock. The
audit's own worst case: "Update + Share within the same second" → a freshly minted share link 404s.
Phase 7 adds a *background writer*, which turns this from contrived into routine.

- `_atomic_write_json(path, obj)` — write to `path + ".tmp.<pid>.<uuid4hex>"`, `flush()` + `os.fsync()`,
  then `os.replace(tmp, path)`. `try/finally` unlinks the tmp on failure. Use it for **every** JSON
  writer: conversations, `users.json`, `shares.json`, `sources.json`, `settings.json`.
- `conversation_lock(cid)` — per-id `threading.RLock` from a module dict guarded by a global lock.
  `threading`, not `asyncio` — heavy work runs in the threadpool.
- **Grep every call site** of `load_conversation` / `save_conversation` and wrap the *entire*
  read-modify-write cycle. Locking only the write does not fix a lost update.
- `analytics.jsonl` stays append-only: one `open(path,"a")`, one `write()`.

Tests: `test_atomic_write_leaves_no_partial_file` (patch `os.replace` to raise; original intact, no
`.tmp` left); `test_concurrent_conversation_writers` (20 threads load→append→save on one id, all 20
survive — **write it first and watch it fail**); `test_share_mint_survives_concurrent_dashboard_save`.

### 1b. Encrypt BYO API keys at rest

`data/users.json` holds users' OpenRouter and Gemini keys **in plaintext**. Those keys cost them
money. This is a launch blocker.

- Fernet (`cryptography`) — check the lock file first; it may already be transitive.
- `SECRET_KEY` env. Missing in dev → generate one, write it to `.env`, log loudly. Missing in prod →
  refuse to start.
- **Migration on boot:** detect plaintext keys, encrypt in place, atomic write.
- Keys stay masked on read (already are). Losing `SECRET_KEY` means users re-enter keys — degraded,
  not catastrophic. Say so in the runbook.

### 1c. Backups

`scripts/backup.sh` — tar `data/` → timestamped archive → optional S3 (`BACKUP_S3_URI`). Keep last N.
Add the cron line to `DEPLOY_RUNBOOK.md`. **`data/` is the database. There is no other copy.**

---

# PHASE 2 — Host split: Vercel frontend + AWS backend

**This is the launch blocker. Do it early, prove it, do not leave it for 5am.**

The two changes below are better architecture regardless of host — they just happen to also be what
makes Vercel possible. The existing `docker compose` single-box path stays as the **tested fallback**.

### 2a. Kill the long-lived SSE through the proxy

A Vercel function will time out long before a 4-model council finishes.

- Convert `/api/analyse` to **job kickoff + polling**: the POST returns immediately; the frontend
  polls `GET /api/conversations/{id}/status` (**this endpoint already exists**) every ~1.5s until
  done, then fetches the record.
- Keep SSE as an opt-in enhancement behind `NEXT_PUBLIC_STREAMING=1`. **Polling is the default and
  must work end to end on its own.**
- `AppShell.jsx` owns this. Progress UI must be identical either way.

### 2b. Fix the upload path

A 50 MB file cannot cross a Vercel serverless function.

- The authed proxy mints a **short-lived HMAC upload ticket**: HMAC over `user_id + exp + nonce`,
  5-minute TTL, single use, signed with `PROXY_SHARED_SECRET`.
- The browser POSTs the file **directly to the backend origin** with the ticket. Backend verifies
  (`secrets.compare_digest`), applies the same 50 MB cap and filename sanitisation, binds the upload
  to that user.
- **Strict CORS: the app origin only.** No wildcard.
- This is a **deliberate, narrow carve-out** from "the browser never calls FastAPI directly." Document
  it in `CLAUDE.md`. Treat the ticket with the same paranoia as a share token: reject `..`,
  constant-time compare, never interpolate into a path.

### 2c. Monorepo deploy config

- `vercel.json` — root directory `frontend`, ignore backend changes.
- `next.config.mjs` — make `output: 'standalone'` **conditional on `DOCKER_BUILD=1`**. Vercel must use
  its native build, not standalone.
- `BACKEND_URL` env drives the proxy target. `.env.example` for both halves.
- Backend: a `/health` endpoint, security headers, `PROXY_SHARED_SECRET` enforced, CORS allowlist.
- Keep `docker-compose.yml` working. Verify `data/` is a **persisted named volume** — a container
  restart must not wipe every conversation. This is the highest-severity item in the phase.

### 2d. Prove the split

Do not declare this done on inspection. Add a `make smoke-split` target that:
builds the frontend with `BACKEND_URL` pointing at a **separate origin**, runs both, and executes the
full smoke + e2e against that configuration — including a >5 MB upload and a full pipeline run.

---

# PHASE 3 — Fix the assistant (the broken chatbot)

**Reported symptom:** asked a question about the data, got nothing back.
**Root cause (audit §11):** the editor prompt is tuned to emit *ops*, so a plain question falls through
and returns thin or empty output.

### 3a. Intent router

Classify every message → `question` | `edit` | `both`. A keyword fast-path plus one small LLM call
returning a JSON verdict. Route accordingly. `both` does both.

### 3b. Deterministic data query engine — `backend/query.py`

This is the real fix. The assistant currently has no way to *compute* an answer, so it either
hallucinates or says nothing.

- The LLM emits a **query spec**: `{select, filter, group_by, agg, sort, limit}`.
- The backend executes it with pandas and returns a small result table.
- The LLM then phrases the answer **from the executed result** — never from memory, never from the
  raw file. Numbers in answers are computed, not generated. (Hard Rule 7.)
- Answers name the columns and rows used.
- **"Pin this as a widget"** on every answer → one click reuses the same spec through the existing
  `add_chart` / `add_metric` op. A question becomes a dashboard. This is the product moment.

### 3c. Context

Verify the assistant actually receives: the dataset schema (columns, dtypes, sample values, row
count, null counts), the current dashboard spec, and — for research records — the pipeline summary.
If it doesn't, that alone explains the reported failure.

### 3d. Never fail silently

No ops and no answer → show a real message. Add an error boundary. A blank reply is a bug, not an
outcome.

Tests: question → answer containing computed numbers; edit → ops applied; both → both; unknown column
→ graceful clarification, not a crash; no API key → a clear, actionable message.

---

# PHASE 4 — UI and layout audit

### 4a. Find the bugs automatically

Playwright sweep: every route (`/`, `/studio`, `/chat/[id]`, `/dashboard/[id]`, `/share/[t]`,
`/admin`, `/privacy`, `/terms`, sign-in) × **390 / 768 / 1440**.

Detect and log: horizontal overflow (`scrollWidth > clientWidth`), elements outside the viewport,
clipped or overlapping text, contrast below WCAG AA (compute from computed styles), missing focus
rings, tap targets under 44px on mobile, images without `alt`.

Write findings + screenshots to `UI_AUDIT.md` / `artifacts/ui/`.

### 4b. Fix all of them

Then add the states the app is missing: **empty states** (invitations to act, not apologies),
**loading skeletons** (`ui/Skeleton` exists), **error boundaries** per route, a real 404 and 500.

Apply the `design-ui` skill for **structure and states only** — spacing rhythm, hover/focus/disabled
on every interactive element, semantic heading order, card and table specs. **Do not re-theme.** A
palette overhaul the night before launch is out of scope (Hard Rule 10).

---

# PHASE 5 — Landing page

Follow the two-pass process from the `frontend-design` skill: brainstorm a token plan, critique it
against the brief, *then* build. Do not skip the critique pass.

**Subject:** a living monitor. The one true claim is *"it tells you what changed."* Everything on the
page serves that sentence.

**Hero = a dashboard that changes while you watch.** Not a screenshot, not a big number with a
gradient. A scripted, deterministic, CSS/JS-only replay loop: a metric ticks up, a delta badge flips,
a new source drops into an insight card, a "what changed" line writes itself. No backend. Honours
`prefers-reduced-motion` by rendering the end state.

**Structural device = the sync log, not `01 / 02 / 03`.** Section eyebrows are timestamps and deltas
(`08:00 · +12.4%`, `Mon · 3 new sources`) — because change and order *are* the content here. Numbered
markers would be decoration; the skill warns against exactly that.

**Type.** Body/UI: Inter. **Every number on the page is set in a mono/tabular face with
`font-variant-numeric: tabular-nums`** — the digits must not jitter as they animate, and the numbers
are the subject. Display: a grotesque with some character, used with restraint.

**Colour — the one risk, and the rule that keeps it from reading as generic.** Keep near-black and
white primary. Add exactly **two accents, and they may only ever appear on a delta**: one for
up/new, one for changed/stale. Never on a button. Never on a heading. Never decorative. "Near-black
plus a bright accent" is a known AI-default look — the accent earns its place *only* by being
semantic.

**Sections:** hero → live-change demo → how it works (connect → build → it keeps watching) → pricing
said plainly (free; you pay your own model provider) → **"Try it with sample data"** (Phase 6) → FAQ →
footer. Keep the existing SEO metadata and JSON-LD intact.

**Copy:** plain verbs, sentence case, no filler. Name things by what the user controls. Errors don't
apologise. An empty screen is an invitation to act.

---

# PHASE 6 — Launch hardening

### 6a. Zero-key onboarding — the highest-leverage thing in this file

Instant dashboards need **no AI key and cost nothing**. Nothing in the product tells a new visitor
that. They arrive, try deep research, hit a "paste your OpenRouter key" wall, and leave.

- Bundle **3 sample datasets** (something with a time column, an entity column, and money).
- **"Try it with sample data"** on the landing hero and in every empty state → one click → a real
  instant dashboard, no key, no cost, no sign-up friction beyond auth.
- If a user *does* trigger deep research with no key, don't wall them — open `ApiKeysModal` inline
  with one line on why it's needed and what it costs them.

### 6b. Rate limiting

In-memory token bucket per user **and** per IP on `/api/upload`, `/api/analyse`,
`/api/dashboard/*/chat`, `/api/connect`. No new dependency. Single replica → in-memory is correct;
note the assumption.

### 6c. Disk retention / GC

Uploads and exports grow forever. A nightly sweep deletes uploads and exports with no referencing
conversation, plus anything older than N days from open-mode/ownerless records. **Never GC
conversations** — they are the database.

### 6d. Headers and errors

CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy`. Confirm `/api/settings*` is still blocked at
the proxy. Error boundaries live.

---

# ⛳ SHIP GATE

Run the full suite. Then:

```bash
git tag v1.0.0-launch && git push origin v1.0.0-launch
```

**The app is now deployable. If the night ends here, it was a success.** Everything below is upside —
and Isa can deploy exactly this tag even if a later phase is half-finished.

Write `DEPLOY_RUNBOOK.md` now, not at the end. Numbered, copy-pasteable, for a human:

1. **Backend host.** *Assumption to confirm:* :8001 is used because :8000 is taken by another of
   Isa's apps on the existing EC2 (`54.153.178.13`, ap-southeast-2). That box already needed a swap
   file; this backend loads pandas + xgboost + scikit-learn + Chromium. **Check free RAM. Recommend a
   separate instance if it's a t3.micro/small.**
2. Clerk → production instance, add the domain, set prod keys.
3. `PROXY_SHARED_SECRET` — generate, set **identically** on Vercel and AWS.
4. `SECRET_KEY` (key encryption), `ADMIN_PASSWORD`, `NEXT_PUBLIC_SITE_URL`, `BACKEND_URL`.
5. Vercel: root directory `frontend`, env vars, domain.
6. DNS + TLS. Chromium must be in the backend image (PDF export).
7. **Fallback path:** if anything about the split misbehaves, `docker compose up` on the AWS box
   serves both halves. That path is already tested.
8. First-boot checks: `/health`; `make smoke` against the live host; the three `%2f` regression
   checks; upload a >5 MB file; run a full pipeline; mint and revoke a share link; `/admin` rejects a
   wrong password.
9. **Set up the `data/` backup cron before you announce anything.**

---

# PHASE 7 — Living monitor: scheduled sync + digest + alerts

*(Post-launch. This is the differentiator, but it does not belong in front of the ship gate.)*

Reuse `sync_dashboard` in `backend/dashboard.py`. Do not rewrite it.

**Owner-only fields — Hard Rule 4.** `schedule`, `alerts`, `alert_log`, `digests` must **never** appear
in `/api/public/{share_id}`. Write a pytest asserting the public payload contains none of them.

**Schedule** on the dashboard record: `{enabled, freq: daily|weekly, hour, weekday, tz, last_run_at,
last_status, last_error}`. Use `zoneinfo`. **Adelaide is UTC+9:30/+10:30 — a half-hour offset with
DST. Never hand-roll it.** `last_run_at` always UTC.

**`backend/scheduler.py`** — an asyncio task in the FastAPI **lifespan** (not the deprecated
`@app.on_event`). Ticks every `SCHEDULER_TICK_MINUTES` (default 5); scans conversations; runs the
existing sync for due records. **Bind the owning user into `current_user_ctx`** so `get_api_key()`
resolves *their* key — no key → skip the insight re-runs, still do the free connector re-pull, set
`skipped_no_key`. **Never fall back to the owner's key.** Cap insight re-runs
(`SCHEDULER_MAX_INSIGHTS`, default 10). Each record in its own `try/except`. `SCHEDULER_ENABLED`
**hard-off in `conftest.py`**. In-process → **assumes a single replica**; scale out and jobs
double-fire. Log it in `DECISIONS.md`.

**`backend/email_send.py`** — Resend over the existing `httpx`. No `RESEND_API_KEY` → **no-op + log**.
Email is strictly optional; the product must work fully without it.

**`backend/digest.py`** — renders the sync `changes` feed to an in-app digest record *and* an HTML
email. **Light theme, inline styles, table layout, ≤600px, plain-text part.** Do not reuse the dark
export CSS — dark emails render badly in Outlook/Gmail and that CSS is print-oriented. Reuse
`_delta_str`. **Nothing changed → do not send.**

**Unsubscribe — the riskiest change here.** Australian Spam Act: a working unsubscribe link and a
sender identity line on every email.

- **Do NOT add a new prefix exemption to the `[...path]` proxy** — that is the exact code that
  produced the two criticals. Use a **dedicated Next route** `app/unsubscribe/[token]/`.
- The page **renders a confirm button that POSTs**. It must not mutate on GET: **Outlook Safe Links
  and Gmail's proxy auto-fire every GET in an email** and would silently unsubscribe people who never
  clicked.
- Token: `secrets.token_urlsafe(32)` in `users.json`. **Gate it with `is_valid_id` before any lookup**,
  exactly as `share_id` is gated. Add `%2f` traversal regression tests for the new surface.

**Threshold alerts** — `dashboard.alerts[]`: `{id, widget_id, label, op: pct_drop|pct_rise|pct_change|lt|gt,
threshold, enabled, cooldown_hours, last_triggered_at, last_value}`. Evaluated on **every** sync,
manual and scheduled, against the deltas the sync **already computes**. **Respect `cooldown_hours`** so
a flapping metric doesn't email twenty times. Chat ops `add_alert` / `remove_alert` — LLM emits the
spec, evaluation stays deterministic. UI: bell on metric hover, **handler-gated so it cannot render in
`SharedView`**. An alert on a deleted widget is **pruned, not crashed on**.

---

# PHASE 8 — Dashboard customisation

- **Drag to rearrange + resize.** Persist `{x, y, w, h}` per widget; render on CSS grid; mobile
  collapses to a single column. Today it's reorder arrows only.
- Duplicate a widget. Per-widget colour override from the existing chart palette. Inline rename.
- **Cross-filtering:** click a bar or segment → filters the whole dashboard (reuse `/api/reanalyse`).
  A visible filter chip bar with "clear all". Without the chips this feels broken, not clever.
- Saved views — a named set of filters.
- "Refresh just this widget."

---

# PHASE 9 — Research quality

- **Two-round search.** `plan_searches()` currently fires one shot of 3 queries. Add: gather → find
  gaps and contradictions → a second, targeted round.
- **Per-claim citations.** The chairman must attach source ids to each claim; flag or strip any claim
  with no support. **This is the single biggest credibility lever in a research product.**
- **Disagreement panel.** The council already peer-reviews — surface *where the models disagreed and
  why* instead of burying it in the synthesis. Disagreement is information, not noise.
- **Research cache** keyed on (query, day) so a sync doesn't re-spend on an identical query within 24h.
- **Spend meter.** BYO keys means users care what a run costs. OpenRouter's `/key` usage endpoint is
  already called by `/api/account/validate` — surface a per-user tally.
- **Council picker.** Let users choose their models. **Verify any model id against the live API before
  offering it** — invalid ids 404 silently and drop from the council; `anthropic/claude-opus-4.8` 402s
  on the dev key.
- `as_of` freshness badge on every finding; stale after N days.

---

# PHASE 10 — Docs and handoff

- `CLAUDE.md`: new gotchas — polling is the default pipeline transport; the upload ticket is a
  deliberate carve-out; `SECRET_KEY` is required in prod; the scheduler is single-replica; Adelaide is
  a half-hour tz; digest emails are light-theme; `data/` volume must persist.
- `PROJECT_AUDIT.md` — it is the main map, so keep it true: §2 status, §6 endpoints, §7 features,
  §9 data model, §11 (**delete the storage-durability item — it's fixed**), §15 roadmap.
- `DECISIONS.md` — every non-obvious call, one line of rationale, plus **"Assumptions to confirm with
  Isa."**
- `HANDOFF.md` — what shipped, what didn't, and how to verify it in five minutes with exact commands.

---

## Definition of done

- `make install && make test && make e2e-install && make e2e` green.
- `make smoke` **and `make smoke-split`** green.
- pytest count materially above 71; smoke check count above 15.
- Every phase committed and pushed to `main`, in order, security fix first.
- **`v1.0.0-launch` tagged and pushed.**
- `DEPLOY_RUNBOOK.md`, `DECISIONS.md`, `HANDOFF.md`, `UI_AUDIT.md` on disk.
- One new dependency at most (`cryptography`), justified in `DECISIONS.md`.