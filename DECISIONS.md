# Decisions log

Every non-obvious call made during the overnight run, one line of rationale each.
Newest phase last.

## Phase 0 — commit the working tree
- Committed in 7 logical groups, **security fix first** (`fix(security)` → share → seo →
  auth → build → test → docs). Files interleave concerns, so groups are dependency-ordered
  whole files rather than per-hunk splits — HEAD is the full green tree either way.
- No `Co-Authored-By: Claude` trailer — Isa earlier had me strip Claude from the
  contributor history, so commits are authored solely by his git identity.

## Phase 1 — data safety
- **Atomic writes** (`backend/atomic.py`) for every persistent JSON state file (conversations,
  users, shares, sources, settings) via temp-file + fsync + `os.replace`. `analytics.jsonl`
  stays append-only (a single append can't tear the file meaningfully).
- **Per-conversation `threading.RLock`** (`storage.conversation_lock`) + `update_conversation`
  helper that re-reads under the lock. The async editor endpoints do their LLM work OUTSIDE
  the lock, then persist via a short synchronous re-read-and-merge — holding a threading lock
  across an `await` would stall the event loop, so that was deliberately avoided.
- `create_share` / `delete_share` now take the per-conversation lock (plus the shares-index
  lock) so a mint can't be clobbered by a concurrent dashboard save.
- **Key encryption at rest** (`backend/crypto.py`, Fernet). Stored form `enc:v1:<token>`;
  plaintext passes through `decrypt` so the boot migration is safe and idempotent. Keys are
  derived from `SECRET_KEY` via SHA-256 so any-length secret works.
- **`SECRET_KEY` policy:** present → use it; missing + `PROXY_SHARED_SECRET` set (prod signal)
  → refuse to start; missing in dev → generate one, append to `.env`, warn loudly.
- **Migration** runs in the FastAPI **lifespan** (not deprecated `on_event`), best-effort so a
  failure never blocks startup.
- Backup is a shell script + cron line (Hard Rule 2: no DB/queue). `data/` is the only copy.

### Assumptions to confirm with Isa
- Losing `SECRET_KEY` means users must re-enter their API keys (ciphertext becomes
  unreadable → treated as "no key"). This is degraded, not catastrophic — acceptable?
- The per-conversation lock is **in-process** and assumes a **single backend replica**. Scaling
  the backend horizontally would reintroduce lost-update races (and, later, double-fired
  scheduler jobs). Single replica is assumed throughout.
- Dashboard-chat now persists via re-read-and-merge of only `dashboard` + `title`. If a future
  field must survive a concurrent edit the same way, add it to that merge.

## Phase 2 — host split
- **Pipeline transport is polling by DEFAULT**; SSE is opt-in (`?stream=1` + `NEXT_PUBLIC_STREAMING=1`).
  The kickoff task uses `asyncio.create_task`, which snapshots the request's contextvars, so the
  user's BYO key resolves inside the background job even after the request unbinds identity.
  Frontend reuses AppShell's existing `startPolling`; fixed `STAGE_ORDER`/`progressFromStage` to
  match the backend's actual stage strings (they were stale and never matched → progress never advanced).
- **Direct upload** (`/api/upload-direct`) is a deliberate, narrow carve-out. Ticket = signed by
  `PROXY_SHARED_SECRET`, 5-min TTL, single-use nonce (in-memory → single replica), traversal-rejecting,
  constant-time compared. Exempt from the proxy-secret guard; gated on `NEXT_PUBLIC_BACKEND_ORIGIN`
  (unset → proxied upload, unchanged). Single-use nonce set is in-memory (lost on restart — a restart
  just invalidates outstanding tickets, which expire in 5 min anyway).
- `next.config` standalone gated on `DOCKER_BUILD=1`. `data/` kept as a **host bind mount** (not a
  named volume) — it survives `docker compose down -v`, which is what the plan actually wants.
- **2c committed separately** from 2a/2b (three commits in this phase) so the safe deploy config was
  banked before the riskier pipeline refactor — honouring "main deployable at every commit" over
  "one commit per phase" where they conflicted.

### Assumptions to confirm with Isa (Phase 2)
- **Full two-origin split verification** (real Vercel frontend + separate AWS backend, plus a full
  pipeline run with a real key) can't run in this sandbox. `make smoke-split` proves the runnable
  parts (polling transport, /health, >5MB upload through the local transport). The true split is a
  **first-boot runbook check** (DEPLOY_RUNBOOK.md §8).
- The single-box `docker compose` path is the **tested fallback** and needs none of 2a/2b — it can
  launch on its own if anything about the split misbehaves.

## Phase 3 — fix the assistant
- **`backend/query.py`** is the real fix: the LLM emits a query spec, pandas executes it, the LLM
  phrases the answer FROM the executed rows. Numbers are computed, never generated. Fully unit-tested
  (group-by/agg/filter/select/sort/errors) independent of any LLM.
- **Intent router** = keyword fast-path (deterministic, tested) + one small LLM call only when the
  message is ambiguous. question → query turn; edit → ops; both → both.
- **"Pin this answer as a widget"** reuses the same spec through the existing add_chart/add_metric op
  (`spec_to_widget_op`) — a question becomes a dashboard widget in one click.
- **Never fails silently:** query errors return a graceful clarification; no-answer-and-no-edit returns
  a real message; no key returns an actionable "add your API key" line.
- Minor: a 'both' message double-appends one history pair (query turn + editor turn each log). Cosmetic;
  left as-is.

### Assumptions to confirm with Isa (Phase 3)
- The full LLM round-trip (spec → execute → phrase) **could not be verified live tonight** — the dev
  OpenRouter key's fast model was too slow (>90s) in this sandbox. The deterministic engine + router are
  tested; the LLM wiring is a copy of the already-working editor pattern. Confirm with a real run.

## Phase 6 — launch hardening
- **Zero-key onboarding** (highest leverage): 3 bundled sample datasets (`backend/samples/`) +
  `POST /api/sample-dashboard` build a real dashboard with NO key, NO cost. "Try it with sample data" is
  the primary hero CTA (`/studio?try=sample` auto-triggers) and a link in the Build card. Verified live.
- **Rate limiting** (`backend/ratelimit.py`): in-memory token bucket, per-user AND per-IP, on
  analyse/upload/upload-direct/connect/sample-dashboard/dashboard-chat. Default 20 burst + 20/min (env
  `RATE_LIMIT_BURST` / `RATE_LIMIT_PER_MIN`). **In-process → single replica.** Disabled in tests
  (`_rate_limiter.enabled=False` in conftest). Verified live (200×20 then 429).
- **Disk GC** (`backend/gc.py`, `make gc`, `python -m backend.gc`): removes orphaned uploads older than N
  days + old exports; **never touches conversations**. Nightly cron in the runbook.
- **CSP** added to the existing headers (nosniff / referrer / frame / HSTS). Permissive where the app
  needs it (Next inline scripts, Plotly eval, Clerk https), strict where free (object-src none, base-uri
  self, frame-ancestors self). `/api/settings*` stays blocked at the proxy.

### Assumptions to confirm with Isa (Phase 6)
- CSP `script-src` allows `'unsafe-inline' 'unsafe-eval' https:` because Next inlines scripts and Plotly
  evals — tighten to nonces post-launch once verified against the live Clerk domain. It does not weaken
  the object-src/base-uri/frame-ancestors protections.
- Rate-limit defaults (20/min) are a conservative floor — tune once you see real traffic.

## Night 2 — Phase 0 (pre-deploy blockers)

### 0a — SSRF egress guard on the data connectors (`backend/ssrf.py`)
- **The vuln:** `POST /api/connect` fetched a user-supplied REST URL and connected to a user-supplied
  DB host **server-side, with no egress restriction** — reachable: AWS metadata `169.254.169.254`,
  localhost, the private network. Fixed at the single choke point (`_run_source_import`).
- **Design:** resolve the host, validate the **resolved IPs** (not the string) against `not is_global`
  **plus** an explicit denylist (version-robust across Python's is_private/is_global registry churn);
  unwrap IPv4-mapped IPv6; scheme allowlist http/https; manual redirect loop that re-validates every
  hop (cap 3); response size cap. Same host guard on the SQL connection string via `make_url`.
- **`SSRF_ALLOW_PRIVATE=1`** is a dev-only escape hatch, auto-refused when `PROXY_SHARED_SECRET` is set
  (the marker of a publicly-reachable prod backend) — a prod misconfig can't open egress.
- **Known residual gap (accepted, per plan):** we validate immediately before the request, but httpx and
  the DB driver re-resolve DNS themselves → a narrow TOCTOU window against a same-host DNS-rebinding
  attacker. Pinning to the validated IP isn't practical without breaking TLS SNI for legit https APIs.
  Mitigated by IMDSv2 (runbook §0.3) at the instance level.
- **sqlite / host-less DB drivers are skipped** by the host guard (no network host). A `sqlite:///`
  connection string pointing at an arbitrary local file is a *local-file-read* concern, not SSRF —
  **flagged as a separate follow-up**, out of Phase 0a's scope.

### 0e — SECRET_KEY-mismatch boot guard (`crypto.verify_key_decryptable`)
- If users.json holds ciphertext that the current key can't decrypt, the backend now **refuses to boot**
  (rather than `decrypt()` silently returning None → "everyone lost their key", which reads as a UI bug).
  Runs **before** the plaintext migration so freshly-encrypted-good values can't mask old-bad ones. Only
  raises when there's ciphertext AND *nothing* decrypts (a single corrupt token doesn't brick boot).

### 0f — CSV-injection guard on the data-table export (`DashboardWidgets.jsx`)
- Client-side CSV export now prefixes any cell starting with `= + - @ \t \r` with `'`. **Assumption to
  confirm:** per the plan's char set this includes leading `-`, so a negative number like `-500` exports
  as the text `'-500` (safe, but Excel won't auto-sum it). Chose plan-literal safety over aesthetics; can
  narrow to `=+@` + `-`-only-when-followed-by-non-digit later if the cosmetic cost matters.

### 0i — backup restore drill (`scripts/restore-test.sh`, `make restore-test`)
- Hermetic: synthetic data/ (a conversation + a REAL encrypted key) → backup.sh → restore to scratch →
  boot the storage+crypto layer against it → assert conversations LOAD **and** encrypted keys DECRYPT.
  **"Boot against it"** is interpreted as running the boot guards (`verify_key_decryptable`) + the load
  path (`list_conversations`) against the restored dir — the meaningful part — not a full uvicorn boot,
  which is slow/flaky and proves nothing extra. Verified PASS. Monthly cron added to the runbook.

### 0j — CORS preflight + no-wildcard origins
- Middleware order confirmed: the guard middlewares run OUTSIDE CORS, but the proxy-secret guard exempts
  `/api/upload-direct` and the rate limiter only touches POST, so the OPTIONS preflight for the direct-
  upload carve-out reaches CORS and returns 200 (tested). Origins are now env-driven via `ALLOWED_ORIGINS`
  (comma-sep; when set it fully replaces the localhost dev defaults so prod never trusts localhost),
  falling back to dev-localhost + `FRONTEND_ORIGIN`. **Never a wildcard** (asserted in a test).

### 0k — sample-dashboard endpoint gated
- `/api/sample-dashboard` is deliberately unauthenticated (zero-key onboarding) but was already in
  `_RATE_LIMITED`; added a test proving it 429s under burst so it can't be a free botnet/compute target.

## Night 2 — Phase 2 (deep testing — in progress, post-tag; main stays deployable)

Done since `v1.0.1-launch` (all additive on `main`): **2a** GitHub Actions CI (`.github/workflows/ci.yml`
— pytest + next build + restore drill on every push/PR); **2d** structural security (route-enumeration:
every endpoint must be classified into one auth posture or the build fails; allowlist deny-scan on
/demo + /public); **2b** malformed-model-output suite; **2c** pathological data corpus (31 inputs);
**2d** SQL read-only guard corpus. Two REAL bugs caught + fixed at the root:

- **500 on a null op** (`apply_ops`): a model returning `null`/a bare string inside the ops array hit
  `AttributeError` → 500 on the dashboard chat endpoint. Fixed: non-dict ops degrade to a note.
- **SQL write-CTE bypass** (`_is_readonly_sql`): the connector's SELECT-only guard only checked the query
  *starts* with SELECT/WITH, so `WITH x AS (INSERT … RETURNING *) SELECT …` and stacked `SELECT 1; DROP`
  walked through — a data-modifying import on a user's DB. Now blocks stacked statements, write keywords
  anywhere, `SELECT … INTO`, and dangerous funcs (pg_sleep/pg_read_file/load_file/benchmark/…).
  **Ceiling (ponytail):** regex heuristic, not a full SQL parser; errs strict (a false reject is a
  non-running import, a false accept could delete data). Swap for sqlparse only if a real bypass appears.

Test count 182 → **258**. Remaining Phase 2 (multi-night): LLM cassettes/FakeLLM + silent-drop
detection, ownership matrix, concurrency, e2e journeys (blocked here: e2e wants port 3000), visual
regression, coverage floor.

## Night 2 — Phase 1 (ship-gate essentials)

### 1a — hero honesty: already correct
- The plan assumed the hero over-promised ("watches while you sleep"). It did NOT — Night 1's copy
  already reads "One click keeps both your numbers and the live web in sync" and the feature copy is all
  user-triggered ("Hit Update", "one Update tells you what moved"). No autonomy claim anywhere in
  user-facing text. Only change: repointed the primary CTA to /demo (see 1b).

### 1b — public /demo (`GET /api/demo` + `app/demo/page.js`)
- A prebuilt sample (SaaS) dashboard in the EXACT read-only share shape, rendered through the existing
  `SharedView` — no auth, no key, no writes, no persistence (built once, cached in `_demo_cache`). The
  `/demo` page fetches the backend server-side (like `/share`), so no Clerk session is needed and no
  proxy exemption was added. Hero primary CTA now → /demo. Owner-only fields deny-scanned in a test.

### 1c — event instrumentation (ships in the gate — irreversible) ✅
- **Transport:** `lib/analytics.js` (anon_id cookie 1yr + session_id + first-touch UTM/referrer) →
  dedicated Next `app/api/events/route.js` → backend `POST /api/events`. A DEDICATED route, NOT a proxy
  exemption — the plan is explicit that exempting prefixes on the `[...path]` proxy is the pattern that
  produced past criticals. Server-side events stitch via the proxy forwarding the `dv_anon_id` cookie as
  `x-anon-id` (one edit, no api.js churn).
- **The anon→user stitch** (the whole point): `components/Identify.jsx` fires `identify` + `signup_completed`
  once per user, linking anon_id → user_id, so a landing visit can be attributed to the signup it became.
- **Events wired:** landing_view, demo_view, demo_interact, signup_completed, identify, error_shown
  (client) + dashboard_created, first_dashboard_created (activation), sample_data_used, connector_used
  (sql|rest), assistant_message (intent+length), sync_run, share_viewed (viral coeff), research_run
  (server). Verified live: `/api/events` wrote the rich shape with anon_id; `/api/demo` returns 12 widgets.
- **Privacy:** props are cleaned to flat scalars (nested/oversized dropped) so a dataset cell can't leak;
  assistant_message logs intent+length, and the message TEXT only when the answer was empty (the exact
  signal to fix the assistant); admin read capped to 30 days. Dedicated per-IP events limiter so anon
  users don't share one `u:anon` bucket.

### 1d — mobile 390px
- Verified /demo (and therefore /share, same `SharedView`) at 390px: no horizontal overflow, metric
  cards 2×2, charts stack full-width and Plotly resizes correctly. Fixed the one issue — the top-bar CTA
  wrapped to 3 lines; badge is now `hidden sm:inline-flex` and the CTA `shrink-0 whitespace-nowrap`.
  Editor stays desktop-first by design (recorded in UI_AUDIT).

### 0h — LLM paths PROVEN live (the thing Night 1 could not) ✅
- **Environment blocker resolved:** the OpenRouter account has credits again (usage ~$4.25, prepaid
  balance). Night 1's "assistant round-trip unverified" was purely an out-of-credits/slow-model
  environment issue, not a code defect.
- **Verified-cheap model:** `openai/gpt-4o-mini` tiny round-trip = 2.1s (<30s). Default assistant fast
  model is `google/gemini-2.5-flash`.
- **Assistant (interactive path):** asked the running backend "What is the total MRR across all rows?"
  on the SaaS sample → answer **"total MRR across all rows is 480506"**, an EXACT match to the CSV
  ground truth (sum = 480506 over 18 rows). Full round-trip (classify_intent → query-spec → deterministic
  compute → phrase) = **3.3s**. This is the real product path, observed and logged.
- **Deep-research pipeline (background path):** one full run to completion via the polling control flow
  (~5 min: research 74s → council stage1/2/3 → synthesis → done). All 4 council models responded
  (gpt-5.1, claude-sonnet-4.5, gpt-4o, gemini-2.5-pro), 238 real Perplexity source URLs, 10.3k-char
  chairman synthesis, 42k-char internet_findings. Not degraded, not a stub.
- **Timing note:** interactive assistant is fast (3.3s). The deep-research council is a deliberately
  long background job (multi-minute) with a progress UI — expected, not a "broken feature".

### 0g — identity-trust boot guard (`main._assert_identity_trust_safe`)
- The proxy-secret guard already 403s any forged `x-clerk-user-id` when `PROXY_SHARED_SECRET` is set
  (tested). The remaining hole was an *open prod* — publicly reachable with the secret unset. Refuse to
  boot when `FRONTEND_ORIGIN` is set (the deploy marker) but `PROXY_SHARED_SECRET` is not. **Signal
  choice:** `FRONTEND_ORIGIN` because docker-compose already hard-requires the secret (`:?set in .env`),
  so only a bare/direct run can reach the unsafe state, and that path sets `FRONTEND_ORIGIN`.

## Night 3 — Phase 0 (assistant correctness) + harness

- **The worst bug is fixed and browser-proven.** "Total MRR" now returns 90,596 (latest month,
  Jun 2026) deterministically via `_stock_total_override` — never 480,506 (the 6× double-count) or an
  arbitrary max, regardless of what aggregation the LLM picks. "How much weekly" is refused (or converted
  with shown arithmetic), never relabelled. Column measures (stock/flow/ratio) classified on ingestion.
  Numeric grounding (`backend/answer_guard`) fails closed: every number in an answer must be in the
  result or a shown derivation. Show-the-working renders the executed spec + result table + stock warning.
- **Golden set (0g):** deterministic engine truths locked in `test_golden_questions.py` (7 tests). Live
  real-model spot-check: total MRR ✓ (90,596), weekly ✓ (refused), highest MRR ✓ (52,761), avg
  customers/plan ✓, churn ✓ (refused, no column).
- **Assumption to confirm — ambiguous "how many in <period>":** the live model sometimes under-aggregates
  ("customers in June 2026" → 483 = one plan, not 731 = all plans). The ENGINE computes 731 correctly
  (tested); the gap is the model's spec choice. Added a spec-prompt hint to sum across other dimensions;
  Phase 5 (answer quality) can tighten further. It's a defensible-but-incomplete answer, not a dangerous
  fabrication — 483 is a real grounded value.
- **Test harness (Phase 4a):** Playwright binds to `E2E_PORT` (default 3100, never 3000); Vitest + RTL +
  axe installed (dev-only). The port excuse is dead.
- **Exports will become light/print-designed** (Phase 1) — a dark PDF wastes ink and reads as broken.
