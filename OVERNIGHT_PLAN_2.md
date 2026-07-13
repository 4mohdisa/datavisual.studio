# datavisual.studio — Overnight Plan 2

Night 1 shipped Phases 0–6 and tagged `v1.0.0-launch`. **That tag is not deployable.** Phase 0 below
contains a live critical vulnerability, a suspected product-breaking bug, and several things nobody
has ever watched succeed.

Execute in order. Never skip. Never ask. Commit and push after each phase.

This is **more than one night**. That is deliberate. Phases 0–1 are the ship gate; everything after is
sequenced so the night can end anywhere and leave `main` deployable.

---

## What Night 1 got wrong — do not repeat

1. **A long-running verification was killed by a bash timeout and took the backend down with it.** The
   assistant's real LLM round-trip was never proven. **Never run a >60s check in the foreground.**
   Background it, redirect to a log file, poll the log.
2. **A feature was declared done when only its deterministic core was tested.** The query engine has
   14 passing tests and has never answered a single real question. **If a feature involves an LLM, it
   is not done until one real round-trip has been observed and logged.**

## Hard rules (binding)

No database — JSON under `data/`. **No new dependencies** (`cryptography` was the one sanctioned
exception and is already in). The LLM emits specs only; all evaluation is deterministic Python. Owner
keys are never spent on a user's request, including background jobs. The public share payload is a
strict allowlist — every new field on the dashboard record is owner-only until proven otherwise, with
a test. `DashboardWidgets.jsx` renders both the editor and the public view — assume anything you add
leaks into `SharedView` until you prove it doesn't. Never interpolate a decoded route param into a URL
(`%2f`). All frontend calls go through `lib/api.js`. Backend from project root, port 8001. Plotly only
via `LazyPlot.jsx`. Don't touch `prediction_engine.py`. Work on `main`, no force pushes, no branches.

## Operating rules

- **Never ask. Never wait.** Ambiguous → smallest reversible option → log in `DECISIONS.md` under
  "Assumptions to confirm" → keep going.
- **`main` must be deployable at every commit.** Out of time mid-phase → revert the incomplete work,
  commit green, update `HANDOFF.md`.
- **Abort rule:** two honest attempts, then stop, commit what's green, move on.
- **`HANDOFF.md` opens with `DEPLOY` or `DO NOT DEPLOY`.** Nothing ambiguous. It is the first line I read.

---

# PHASE 0 — Pre-deploy blockers

**If any of this fails, `HANDOFF.md` line one is DO NOT DEPLOY.**

### 0a. SSRF in the data connectors — CRITICAL, exploitable today

`POST /api/connect` takes a **user-supplied URL** (REST connector) or DB host (SQL connector) and the
backend fetches it **server-side**. There is no egress restriction. On your infrastructure that means
a signed-in user can point it at:

| Target | What they get |
|---|---|
| `http://169.254.169.254/latest/meta-data/iam/security-credentials/` | **Your AWS IAM role credentials** — if IMDSv1 is enabled (the default on older launch configs) |
| `http://localhost:8000/...` | **Applyable.** Your other app is on the same box, on that port |
| `http://127.0.0.1:8001/api/settings` | Your **global AI keys** — the proxy blocks this path, the backend does not. Only `PROXY_SHARED_SECRET` stands in the way, and a misconfig removes it |
| `http://10.x / 192.168.x / 172.16.x` | Anything else on the private network |

Fix, at the single place every outbound connector request is made:

- **Resolve the hostname first, then validate the resolved IPs** — not the string. Block loopback,
  private, link-local (`169.254.0.0/16`), CGNAT, multicast, reserved, and IPv6 equivalents
  (`::1`, `fc00::/7`, `fe80::/10`, IPv4-mapped forms).
- **Re-validate after every redirect.** A redirect to `169.254.169.254` defeats a check done only on
  the original URL. Cap redirects; consider disabling them.
- **Pin the connection to the validated IP** if practical, to beat DNS rebinding. If you can't,
  re-resolve-and-check immediately before connecting and log the gap in `DECISIONS.md`.
- **Scheme allowlist: `http`/`https` only.** No `file://`, `gopher://`, `ftp://`, `data:`.
- Timeout + response size cap + content-type check.
- **Same guard on the SQL connector host.** A DB URL pointing at `localhost` is the same attack.
- `SSRF_ALLOW_PRIVATE=1` as a dev-only escape hatch, default off, **refused in production**.

Tests: every row above, plus a redirect chain into a blocked range, plus a hostname that resolves to a
private IP, plus IPv6 forms.

**In `DEPLOY_RUNBOOK.md`:** enforce **IMDSv2** on the instance regardless. The code fix and the instance
setting are independent — you want both.

### 0b. Rate limiter vs. status polling — suspected product-breaking bug

Night 1's Phase 2 made the pipeline poll `GET /api/conversations/{id}/status` every 1.5s (~40 req/min).
Its Phase 6, four phases later, added rate limiting. **They were never tested together.**

If `/status` falls under a limiter tuned near 20/min, the poller **rate-limits itself into a 429
mid-pipeline** and every long analysis appears to fail in production. A smoke test that never runs a
full pipeline cannot catch this.

- Read the limiter's path matching. Decide whether `/status` is covered — don't guess.
- Exempt status polling, or raise its bucket far above the poll rate.
- **Test:** simulate a 5-minute pipeline's poll volume against the real middleware; assert zero 429s.
- Add **poll backoff** in `AppShell.jsx`: 1.5s for 15s → 3s → 5s. Every poll is a Vercel invocation.

### 0c. Rate limiter must key on `X-Forwarded-For`

Behind Caddy, Cloudflare, or Vercel **every request arrives from one socket IP.** Key on the socket and
you rate-limit your entire userbase as one client on launch day. Derive the client IP from
`X-Forwarded-For` with an explicit `TRUSTED_PROXY_HOPS` (default 1). **Never trust a raw
client-supplied header without a hop count** — otherwise it's spoofable and the limiter is decorative.
Test both directions.

### 0d. Orphaned background jobs

`asyncio.create_task` dies with the process. Restart mid-analysis → the conversation sits in a
non-terminal stage **forever** and the frontend polls it forever.

- **Boot sweep** in lifespan: non-terminal stage → `error` ("interrupted by a server restart — run it
  again").
- **Frontend:** cap total poll duration (~15 min) → real error, stop polling. A spinner that never ends
  is worse than a failure.

### 0e. `SECRET_KEY` loss guard

Night 1's migration **already encrypted your live user's key.** A new box with a fresh `SECRET_KEY` and
the old `data/` makes every user's API key permanently unreadable.

On boot: ciphertext that won't decrypt with the current key → **refuse to start**, with an explicit
error naming the cause and the fix. **Never silently degrade to "no keys stored"** — that looks like a
UI bug, and users will re-paste keys into a system that is quietly broken.

`DEPLOY_RUNBOOK.md`, in bold: **`SECRET_KEY` travels with `data/`. Back them up together.**

### 0f. CSV injection on export

A cell beginning `=`, `+`, `-`, `@`, tab or CR executes as a formula in Excel. You export CSV from the
data table. Prefix such cells with `'`. Five lines.

### 0g. Forged identity headers

The backend trusts `x-clerk-user-id` from the proxy. **Prove** a request carrying that header but **no
`x-proxy-secret`** is refused. If `PROXY_SHARED_SECRET` is unset, the backend must refuse to boot in
production rather than trusting the internet's idea of who you are.

### 0h. Prove the LLM paths — the thing Night 1 could not

- Pick a **fast, verified-cheap** model id. Confirm it against the live API first — invalid ids 404
  silently and drop from the council; `anthropic/claude-opus-4.8` 402s on the dev key.
- **Ask the assistant a real question about a real dataset. Observe a computed number.** Background
  process → log file → poll the log. Record wall-clock time.
- **Run one full deep-research pipeline to completion.** Nobody has watched this finish since the
  polling refactor rewired its control flow.
- If either takes >30s to first token, say so plainly. **A correct answer that takes 90 seconds is
  still a broken feature.**

### 0i. Backup restore drill

**A backup you have never restored is a hypothesis.** Back up → restore to a scratch dir → boot against
it → confirm conversations load **and encrypted keys still decrypt**. Add `make restore-test`. Put the
real cron line in the runbook.

### 0j. CORS preflight on the direct-upload path

Confirm `OPTIONS` isn't swallowed by the proxy-secret guard or the rate limiter (middleware ordering
decides this, and it's easy to get wrong). `ALLOWED_ORIGINS` env-driven, **no wildcard**.

### 0k. Sample-dashboard endpoint

It does real compute. Authed or hard rate-limited. An unauthenticated compute endpoint on a free public
product is a free botnet target.

---

# PHASE 1 — Ship-gate essentials

### 1a. The hero promises something you didn't ship

Night 1's hero shows a dashboard changing **on its own**. The scheduler was deferred — today it only
changes when someone clicks Update. Until Phase 6, the copy reads **"one click keeps it in sync"**, not
"it watches while you sleep." Fix the hero, the feature copy, and the meta description.

### 1b. `/demo` — public, no sign-in, no key

"Try it with sample data" almost certainly bounces an anonymous visitor into Clerk sign-in, which
destroys the point of zero-key onboarding: **see the value before committing anything.**

Ship a **public `/demo`** route rendering a bundled sample dashboard through the existing `SharedView`
— no auth, no keys, no writes. It is the share view with a prebuilt record. Point the landing CTA at
it.

### 1c. Event instrumentation — **this ships tonight, and here is why**

The charts can wait. **The events cannot.** A visitor you never cookied is permanently unattributable —
you can never go back and ask whether last week's landing page worked. This is the only thing in the
entire plan that is *irreversible if skipped*.

**The anon → user stitch is the whole point.** Set a first-party `anon_id` cookie on first visit. On
signup, emit an `identify` event linking `anon_id` → `user_id`. Without that link you cannot answer
*"did the landing visit become a signup?"*, which is the only question that matters.

Event shape, appended to the existing `data/analytics.jsonl`:

```jsonc
{ "ts": "ISO-8601 UTC", "event": "dashboard_created",
  "user_id": "u_<hex>" | null,   // null = anonymous
  "anon_id": "a_<hex>",          // first-party cookie — survives signup
  "session_id": "s_<hex>",
  "path": "/studio", "referrer": "...",
  "utm": { "source": …, "medium": …, "campaign": … },   // first touch only
  "props": { … } }
```

**Funnel events:** `landing_view` · `demo_view` · `demo_interact` · `signup_started` ·
`signup_completed` (+`identify`) · **`first_dashboard_created`** ← *the activation event* ·
`key_added` · `first_research_run` · `dashboard_shared` · `share_viewed` (by a non-owner — this is your
viral coefficient) · `returned_d1` / `returned_d7` · `error_shown`.

**Usage events — this is the "what are they using most" answer:** `upload_completed`
(rows/cols/size/format) · `connector_used` (sql|rest) · `chart_added` (**which of the 9 types anyone
actually uses**) · `assistant_message` (**intent: question|edit|both — tells you whether the chatbot
fix worked**) · `sync_run` (manual|scheduled) · `alert_created` · `alert_fired` · `export_run` (format)
· `sample_data_used`.

**Privacy — get this right now, not after:**

- **Never log dataset contents or cell values into an event.** Props are metadata only — row counts,
  column types, chart kinds. A cell value in an analytics log is a data leak with extra steps.
- **Do not log question text by default.** Log the intent and the length. **Exception:** log the text of
  messages that produced an *error or an empty answer* — that is exactly the signal you need to fix the
  assistant, and it's proportionate. Disclose it.
- First-party only. No third-party trackers. Update `/privacy` to describe this honestly, and add a
  deletion path.
- `analytics.jsonl` grows forever and `/admin` reads it. Cap the read (last 30 days / tail N) and rotate
  monthly. Cheap now, painful later.

### 1d. Mobile

The **public share and demo views must be flawless at 390px** — that is the surface people forward. The
editor may stay desktop-first; record that in `UI_AUDIT.md` as a deliberate choice, not an unexplained
finding.

---

## ⛳ SHIP GATE — `git tag v1.0.1-launch`

Full suite green → tag → push. **This is the tag to deploy.** If the night ends here, it succeeded, and
from the moment it's live every visitor is being measured.

---

# PHASE 2 — Deep testing

**This comes before the theme and layout refactor on purpose.** Phase 3 touches nearly every file in
`frontend/`. Without visual snapshots and real e2e journeys, you cannot tell a refactor bug from an
intentional change, and you will ship one. **The test net is the precondition for Phase 3 being safe,
not bureaucracy.**

### 2a. CI first, or none of the rest protects anything

GitHub Actions on every push to `main`: `make test` → `make e2e` → `make smoke`. Tests that don't run
automatically are documentation.

### 2b. LLM-path testing — the biggest gap in the suite

Every LLM-touching feature is tested only at its deterministic edges. **The part that actually breaks
is the parsing and application of model output**, and none of it is covered.

- **Cassettes.** A `FakeLLM` replaying fixtures from `backend/tests/fixtures/llm/`, plus a `--record`
  mode that hits the real API once and writes them. Deterministic, offline, fast.
- **Malformed-output suite** — each must degrade gracefully, **never 500, never blank**: prose instead
  of JSON · trailing comma · markdown-fenced JSON · unknown op `kind` · a chart spec naming a column
  that doesn't exist · a wrong-typed axis · `limit: -1` · `null` · `[]` · a 300-op response ·
  OpenRouter 402/429/500/timeout · a model returning nothing.
- **Silent-drop detection.** An invalid model id 404s and vanishes from the council with no user-facing
  signal. **That is a bug.** A council that ran with 2 of 4 models must say so.

### 2c. Pathological data corpus

~25 fixtures in `backend/tests/fixtures/datasets/`, each yielding **a clean dashboard or a clear error —
never a 500, never a hang**:

empty · header-only · one row · one column · all-null column · duplicate column names · unnamed columns
· mixed types · six date formats · unicode/emoji headers · a 300-char column name · BOM ·
semicolon-delimited · CRLF · a column named `index` · numbers as strings with `$` and commas · negatives
in parens · scientific notation · 200 columns · 500k rows · exactly at the 50 MB cap · 1 byte over ·
HTML renamed `.csv` · a zip renamed `.csv` · multi-sheet XLSX · JSON that's an object not an array ·
deeply nested JSON.

Then **guardrails with honest messages**: cap chart categories, table rows, columns — and *tell the
user* rather than hanging or rendering a 10,000-slice pie.

### 2d. Security suite — make it structural, not a list

The best security test **catches the mistake you haven't made yet**:

- **Route enumeration test.** Walk the FastAPI router. Every route must appear in either the
  `owner_scoped` or `explicitly_public` list. **A new endpoint that forgets `_owned()` fails the
  build.** Worth more than twenty hand-written cases.
- **Allowlist deny-scan.** Serialise the public payload to a string; assert it contains none of
  `owner_id`, `file`, `source`, `history`, `schedule`, `alerts`, `alert_log`, `digests`, `unsub_token`,
  or any API key. String-scan, so nothing hides nested.
- **Ownership matrix** — user A against every owner-scoped endpoint of user B → 404.
- **SQL guard:** `DROP` · `; DELETE` · `INSERT` · a CTE with an insert inside · `SELECT … INTO` ·
  stacked queries · comment-obfuscated keywords (`SEL/**/ECT`) · `pg_sleep` · `pg_read_file`.
- **SSRF corpus** from 0a, as permanent regressions.
- **Upload ticket:** expired · replayed · tampered · wrong user · absent.
- **Traversal on every id param** — share, conversation, export, dataset, unsub token.
- **Rate limiter:** a spoofed `X-Forwarded-For` does not bypass.
- **Admin:** brute force is rate-limited. **The admin panel must never expose an API key or a cell
  value** — add it to the deny-scan.

### 2e. Concurrency and limits

Two browsers editing one dashboard. Sync during an edit. Share during a sync. Delete during an export.
A 500k-row build inside a time budget. Assert the row cap on `/api/dataset/{id}` holds.

### 2f. End-to-end journeys

Six e2e tests is not coverage. Add, with the LLM stubbed at the network layer:

- Anonymous: landing → `/demo` → sign-up prompt.
- New user: sign up → empty state → sample data → dashboard → edit by chat → share → **open the share
  link in a fresh incognito context** → revoke → 404.
- Upload >5 MB through the direct-upload ticket.
- Full research pipeline via polling, to completion.
- **Failure journeys** (the ones nobody writes): no key → the keys modal, not a wall · bad CSV → a clear
  message · rate-limited → a clear message · backend down → a clear message, **not a white screen**.
- Mobile 390px on share and demo.
- **axe-core on every route — zero critical violations.**

### 2g. Visual regression

Playwright snapshots for every route × 390/768/1440, committed and diffed. This is what *keeps* the
layout aligned after Phase 3 rather than aligning it once and watching it drift.

### 2h. Coverage floor + API contract

`pytest --cov` with a floor on `backend/` (exclude `prediction_engine.py`) — not because coverage is
truth, but because it surfaces entire untested modules. Plus: every method in `lib/api.js` maps to a
real route in the FastAPI OpenAPI schema.

---

# PHASE 3 — Theme tokens and layout system

Colours are hardcoded across components, so pages don't align and a theme change means find-and-replace.

**The sequencing rule that makes this safe:** *tokenise first with zero visual change, prove it with
snapshots, then restyle.* Refactor and redesign in one pass and you cannot tell a bug from an intention.

### 3a. Tokens — a refactor, not a redesign. Pixels must not move.

Three tiers in `tokens.css`:

1. **Primitives** — raw ramps (`--gray-50…950`, `--green-*`, `--amber-*`, `--red-*`, `--blue-*`).
   **Never referenced by a component.**
2. **Semantic** — the only thing components may use: `--bg-canvas`, `--bg-surface`, `--bg-raised`,
   `--bg-overlay`, `--fg-primary`, `--fg-secondary`, `--fg-muted`, `--fg-on-accent`, `--border-subtle`,
   `--border-default`, `--border-strong`, `--accent`, `--accent-hover`, `--focus-ring`, `--success`,
   `--warning`, `--danger`, **`--delta-up`, `--delta-down`** (the product's language is change — give it
   first-class tokens).
3. **Scales** — spacing on a 4px grid (`--space-1…12`), `--radius-sm/md/lg`, `--shadow-xs/sm/md`, a
   **z-index scale** (`--z-dropdown/--z-modal/--z-toast` — ad-hoc z-indexes are why overlays fight),
   motion (`--duration-fast/base`, `--ease-out`).

Wire it into `tailwind.config` so `bg-surface`, `text-muted`, `border-default` are real classes. Then
refactor **every** component off hardcoded values.

**Acceptance: the Phase 2g snapshots come out pixel-identical.** That is the proof the refactor was clean.

### 3b. Enforcement — the part that makes it stick

A token system nobody enforces decays inside a week. **Fail the build** on: any hex / `rgb(` / `hsl(` /
`oklch(` outside `tokens.css`; any Tailwind default-palette class in `components/` or `app/`
(`bg-gray-800`, `text-white`, `text-zinc-*`…); any raw `z-index`. Ship it as a lint rule in CI. Without
this, Phase 3 is a one-time cleanup that quietly undoes itself.

### 3c. Layout primitives — why pages align

`<Page>` (max-width, padding, rhythm) · `<PageHeader title actions>` · `<Section>` · `<Stack gap>` ·
`<Row gap align justify>` · `<Grid cols gap>` · `<Card>` · `<EmptyState>` · `<ErrorState>` ·
`<LoadingState>`.

**The rule that actually makes layouts align: no component sets its own outer margin.** Spacing is owned
by the parent primitive. Children with their own margins is *the* reason pages drift.

Refactor every route onto them: `/`, `/studio`, `/chat/[id]`, `/dashboard/[id]`, `/share/[t]`, `/demo`,
`/admin`, `/privacy`, `/terms`, sign-in/up, 404, 500.

### 3d. Finish the component kit

Add what the app actually uses: Select, Textarea, Checkbox, Toggle, Popover, Tooltip, Tabs, Table,
Badge, Alert, Toast, Dropdown, Spinner. **Every one with hover, focus, disabled — and a visible focus
ring.** No exceptions.

### 3e. `/styleguide`

A `noindex`, admin-gated route rendering every token and every component in every state. This is how you
*see* inconsistency, and it's what the snapshots point at.

### 3f. Light theme

Once the semantic layer exists, light mode is ~30 redefined variables under `[data-theme="light"]`.
Build the structure. Ship the toggle only if the snapshots stay green.

---

# PHASE 4 — Growth loop: landing, onboarding, and the admin panel that tells you if they worked

Built **on Phase 3's system**, so it's right the first time instead of built twice.

### 4a. Landing page — the real rebuild

Night 1 built the living-monitor hero; Phase 1 made its copy honest. Now the rest of the page.

- **The headline is the highest-leverage eight words on the site.** "Power BI plus an AI research
  assistant" is an internal description, not a headline. **The headline must carry the idea of
  *change*** — that is the only thing you do that Power BI doesn't. A stranger must be able to say what
  this does within five seconds.
- **The demo is the proof — put it above the fold as the primary CTA.** *"See a real dashboard"* beats
  *"Create an account"* every time, and `/demo` costs the visitor nothing.
- **You have no social proof. Do not fake it.** No invented logos, no invented testimonials. Use
  *product* proof instead: the live demo, a real share link, "no card, no key required to start."
- **Handle the three real objections, plainly:**
  1. *"Is this free? What's the catch?"* → Free. You bring your own AI key and pay OpenRouter directly.
     **Say the actual dollar figure for a typical run.** Vagueness about money reads as a trap.
  2. *"Do I have to hand you my data?"* → Say exactly what is stored and link `/privacy`.
  3. *"Why not Power BI or Tableau?"* → They tell you what happened. This tells you **what changed** —
     and it watches the web alongside your numbers. Make the comparison honest, not a strawman.
- Pricing said plainly. Keep the FAQ, the SEO metadata and the JSON-LD intact.

### 4b. Onboarding — move the key from step 0 to step 4

The current path drops a new user into an empty studio and then asks for an OpenRouter API key. Most
people don't have one, don't know what it is, and don't know what it costs. **That is the wall.**

- **Name the activation metric first, or "improve onboarding" is unfalsifiable.** Use: *a user is
  activated when they have created a dashboard and asked it one question.* Instrument it (1c). Every
  change below is judged against that number.
- **Signup → a working dashboard in five seconds.** Do not deposit them in an empty room. Post-signup
  lands on a pre-built sample dashboard, already rendered.
- **The empty state IS the sample-data card**, not a file picker. Upload is the secondary action.
- **A real first-run checklist**, dismissible and persistent: (1) build your first dashboard — 30
  seconds, no key · (2) ask it a question · (3) share it · (4) *optional* — add an AI key to unlock deep
  research. **The key is step 4. That reordering is the entire game.**
- **The key modal must teach, not just ask:** what it is · a direct link to OpenRouter's key page ·
  what a run actually costs · that it's encrypted at rest and only ever spent on your own runs · a
  Validate button with instant feedback (the endpoint already exists).

### 4c. Admin panel — build it out of your own chart builder

`/admin` exists (password-gated, users, counts, 14-day activity). Make it the thing you actually watch.

**It is a dashboard. You are a dashboard company. Render it with the product's own deterministic chart
builder via `LazyPlot.jsx`** — no new charting library, no new dependency, and every improvement to the
chart engine improves the admin panel for free. Dogfood it.

- **Overview tiles:** users · active 7d · new 7d · dashboards · research runs · shares created · share
  views · errors 24h.
- **Funnel chart** with drop-off percentages, straight off the 1c events. **This is the single most
  valuable view on the page** — it is the only thing that tells you whether 4a and 4b worked.
- **Activity over time** — events/day, 30 days.
- **Feature usage, ranked** — *your literal question: what are they using most.* Which of the 9 chart
  types get used. Connectors: SQL vs REST. Assistant: question vs edit ratio (**this is how you learn
  whether the chatbot fix landed**). Exports by format. Sample data vs upload.
- **Per-user table**, sortable: user · signed up · last active · dashboards · research runs · has key? ·
  activated? · errors. **Click a user → their event timeline.** That's the "what has this person been
  doing" view.
- **Error feed** — last 100, newest first, **grouped by message with counts** so one repeated bug doesn't
  drown the list. You should not be SSHing into a box to `cat error.log` on launch day.
- Auto-refresh every 30s. Do not build websockets.
- Guard it: brute-force rate limit, `noindex`, and **never render an API key or a dataset cell value**
  (2d covers this — make sure it does).

---

# PHASE 5 — Analytical depth

The product's analysis is currently **descriptive**: profile, chart, count. Everything below is
deterministic Python on libraries already installed (pandas, scipy, sklearn, xgboost). **No AI key
required — so it all works on the free, zero-key path.** That is the point.

- **Auto-insights on upload.** "Three things worth knowing about this dataset" — computed, not
  generated. A new visitor gets *real analysis* before they ever paste a key.
- **Drivers.** "What moves X?" — correlation plus simple feature importance.
- **Trend and seasonality.** *"Revenue is up 12% — but it's up 14% every year in this month."* That
  sentence is the whole product.
- **Segment comparison.** A vs B across every metric, ranked by difference. The most useful analytical
  primitive in business data, and you don't have it.
- **Distribution shift** between two periods (KS test).
- **Data quality report** — missingness, duplicates, cardinality, constant columns, type mismatches.
- **Significance-aware deltas and alerts.** *A living monitor that cries wolf on random variation is
  worse than no monitor.* When a delta sits inside the noise, say so — and **do not fire an alert on
  it.** Nothing else in this plan raises the quality ceiling more.

---

# PHASE 6 — Complete the living monitor

**Alerts exist in the backend and are invisible in the UI. A backend-only feature is not a feature.**

- **Alert bell UI** on metric widgets → rule editor. Fired alerts: badge on the widget, row in the
  changes feed. **Handler-gated so it cannot render in `SharedView`.**
- **Scheduler** — asyncio task in the FastAPI **lifespan** (not the deprecated `@app.on_event`), no
  APScheduler. Ticks every `SCHEDULER_TICK_MINUTES` (default 5). Bind the owning user into
  `current_user_ctx` so `get_api_key()` resolves **their** key; no key → skip insight re-runs, still do
  the free connector re-pull, mark `skipped_no_key`. **Never fall back to the owner's key.** Cap insight
  re-runs. Each record in its own `try/except`. **Hard-off in `conftest.py`.**
- **Single-replica guard.** Locks, rate limiter, upload nonces and the scheduler are all in-process. If
  the worker count is >1, **refuse to start the scheduler** rather than double-firing every job and
  sending every user two emails.
- **Schedule:** `{enabled, freq, hour, weekday, tz, last_run_at, last_status, last_error}`. Use
  `zoneinfo`. **Adelaide is UTC+9:30/+10:30 — a half-hour offset with DST. Never hand-roll it.**
- **Digest** — the `changes` feed → an in-app record *and* an HTML email. **Light theme, inline styles,
  table layout, ≤600px, plain-text part.** Do not reuse the dark export CSS; dark emails render badly in
  Outlook and Gmail. **Nothing changed → do not send.**
- **Email** — Resend over the existing `httpx`. No `RESEND_API_KEY` → **no-op + log.**
- **Unsubscribe — the riskiest change here.** Spam Act: working unsubscribe + sender identity on every
  email.
  - **Do NOT add a prefix exemption to the `[...path]` proxy** — that is the exact code that produced the
    two criticals. Use a **dedicated Next route** `app/unsubscribe/[token]/`.
  - **The page POSTs behind a confirm button. It must not mutate on GET.** Outlook Safe Links and
    Gmail's proxy auto-fire every GET in an email and would silently unsubscribe people who never
    clicked.
  - Token `secrets.token_urlsafe(32)`, gated with `is_valid_id` **before any lookup**. `%2f` regression
    tests on the new surface.
- **Only now** may the landing copy promise automatic watching. Go back and finish 1a.

---

# PHASE 7 — Research quality

- **Ground the search plan in the dataset.** `plan_searches()` writes *topic-generic* queries. It has the
  columns, the entities, the date range — it should write *specific* ones. Biggest single quality lift
  available, and it's nearly free.
- **Two-round adaptive search:** gather → find gaps and contradictions → a second, targeted round.
- **Per-claim citations, then verify them.** A verification pass checks the cited snippet actually
  supports the claim. **Flag or strip unsupported claims.** An uncited number in a research report is
  worse than no report.
- **Surface disagreement.** The council already peer-reviews — show *where the models disagreed and why*
  instead of burying it. Disagreement is information.
- **Contradiction between sources** — when two conflict, say so. Don't average them into mush.
- **Source quality and recency weighting** — a regulator, a filing or a paper outranks a content farm.
- **Research cache** keyed on (query, day) so a sync doesn't re-spend within 24h.
- **Cost estimate before the run**, spend meter after. BYO keys means users want the number *before* they
  click.
- **Council picker** — validate every model id against the live API, and **never drop a model silently**.
- Follow-ups become one-click runs. `as_of` freshness badge on every finding.

---

# PHASE 8 — Dashboard customisation

Drag to rearrange + resize; persist `{x,y,w,h}`; CSS grid; single column on mobile. Duplicate a widget;
per-widget colour **from the tokens** (Phase 3 makes this trivial); inline rename. **Cross-filtering** —
click a bar or segment → filters the whole dashboard (reuse `/api/reanalyse`), with a visible filter
chip bar and "clear all" (without the chips it reads as broken, not clever). Saved views. Per-widget
refresh.

---

# PHASE 9 — Close out

Update `CLAUDE.md`, `PROJECT_AUDIT.md` (§11, §15), `DECISIONS.md`, `HANDOFF.md`, `DEPLOY_RUNBOOK.md`,
`UI_AUDIT.md`. Tag `v1.1.0`.

---

## Definition of done

- CI green on `main`. `make test`, `make e2e`, `make smoke`, `make smoke-split`, `make restore-test`.
- **A real assistant answer and a complete research run, both observed and logged with timings.**
- Visual snapshots committed; the token refactor left them **pixel-identical**.
- The lint rule blocking hardcoded colours is **in CI and failing builds**.
- **Events are flowing from the ship-gate tag onward**, with the anon → user stitch working.
- `v1.0.1-launch` tagged and pushed.
- `HANDOFF.md` opens with **DEPLOY** or **DO NOT DEPLOY**.
- No new dependencies.