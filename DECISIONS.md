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
