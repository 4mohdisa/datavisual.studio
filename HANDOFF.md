DEPLOY

# Overnight run 2 — handoff

_First line is the verdict. Deploy tag **`v1.0.1-launch`**, not `v1.0.0-launch`._

## Verdict: DEPLOY `v1.0.1-launch`

`v1.0.0-launch` (Night 1) is **superseded and should NOT be deployed** — it shipped with a live SSRF
critical and a suspected rate-limiter/poller collision. Night 2 (Phase 0 + Phase 1, the ship gate)
fixed every pre-deploy blocker, proved the LLM paths live for the first time, and shipped the
irreversible event instrumentation. Deploy **`v1.0.1-launch`** per `DEPLOY_RUNBOOK.md`.

## Why this tag is safe

**Phase 0 — pre-deploy blockers (all fixed + tested):**

| Item | Fix | Proof |
|---|---|---|
| 0a SSRF in connectors (CRITICAL) | `backend/ssrf.py` — resolve host, validate resolved IPs, block loopback/private/link-local/CGNAT/metadata + IPv6/IPv4-mapped; revalidate redirects; scheme allowlist; SQL host guard; dev-only escape hatch refused in prod | 35 tests |
| 0b rate-limiter vs poller | `/status` is GET + not in the limited set → poller can never 429 itself; made explicit + AppShell poll backoff | poll-volume test (200 GETs, 0×429) + positive control |
| 0c XFF keying | limiter keys on X-Forwarded-For w/ `TRUSTED_PROXY_HOPS` (default 1); forged prefix can't bypass | tests both directions |
| 0d orphaned jobs | boot sweep flips restart-orphaned `running`→`error`; frontend caps poll at ~15min | test + observed live ("swept 2 …") |
| 0e SECRET_KEY loss | boot **refuses** if ciphertext won't decrypt with the current key (no silent "keys lost") | test |
| 0f CSV injection | export prefixes `= + - @ \t \r` cells with `'` | — |
| 0g forged identity | forged `x-clerk-user-id` w/o proxy secret → 403; refuse boot in a deployed env missing the secret | test |
| 0h **prove the LLM paths** | assistant computed **total MRR = 480506** (exact) in **3.3s**; one full deep-research run to completion (~5min, 4/4 council models, 238 sources, 10.3k-char synthesis) | observed + logged live |
| 0i restore drill | `make restore-test` — backup→restore→boot→**conversations load AND keys decrypt** | PASS |
| 0j CORS preflight | env-driven origins (no wildcard); OPTIONS on the upload carve-out not swallowed | tests |
| 0k sample endpoint | unauthenticated compute endpoint is hard rate-limited | test |

**Phase 1 — ship-gate essentials:**

- **1a** hero copy was already honest ("one click keeps it in sync"); repointed the primary CTA to /demo.
- **1b** public **`/demo`** — a prebuilt sample dashboard via the read-only `SharedView`, no auth/key.
- **1c** first-party **event instrumentation** (the irreversible piece): `anon_id` cookie on first visit,
  the **anon→user `identify` stitch**, funnel + usage events, dedicated `/api/events` route (no proxy
  exemption), privacy-safe props. **Events flow from this tag onward.** Verified live.
- **1d** /demo and /share verified flawless at 390px.

## Verify in 5 minutes

```bash
make install
make test            # 182 pytest (hermetic) + next build — GREEN
# with the stack running (make dev):
BASE=http://localhost:3100 node scripts/smoke.mjs   # 16/16 — SEO, %2f guards, golden path, health
make restore-test    # PASS — backup restores AND keys decrypt
```

Counts: pytest 115 → **182**. All green at tag time. `/api/demo` + `/api/events` verified live; the
assistant + a full research pipeline observed end-to-end (see `DECISIONS.md` → Night 2 → 0h).

## What was NOT run here (and why it's fine)

- **`make e2e`** (Playwright) defaults to port **3000**, which is occupied by your other app on this
  machine, so it couldn't bind cleanly. The same journeys are covered hermetically by the pytest
  TestClient integration (upload→dashboard→edit→share→public→revoke, ownership 404s) **and** live by the
  16-check smoke above. Run `make e2e` yourself on a box where 3000 is free.
- **`make smoke-split`** (>5MB direct upload) needs `NEXT_PUBLIC_BACKEND_ORIGIN` + `SPLIT=1`; the base
  16-check smoke is green.

## What's next (Phases 2–9, more than one night — `main` is deployable at each commit)

Phase 2 deep testing (CI, LLM cassettes, pathological data corpus, visual regression) **before** Phase 3
theme-token refactor (tokenise with zero visual change first) **before** Phase 4 landing/onboarding
rebuild. Then analytical depth (5), the scheduler/digest/unsubscribe to complete the living monitor (6),
research quality (7), dashboard customisation (8), close-out (9). See `OVERNIGHT_PLAN_2.md`.

## Confirm with me (in `DECISIONS.md` → "Assumptions to confirm")

1. **Single replica assumed** — rate-limit buckets, per-conversation lock, upload nonce, events limiter
   are all in-process. Don't run >1 backend replica without addressing it.
2. **`SECRET_KEY` travels WITH `data/`** — back them up together; a fresh key against restored data now
   **refuses to boot** (0e) rather than silently losing keys.
3. Enforce **IMDSv2** on the instance regardless of the code SSRF fix (runbook §0.3) — defence in depth.
4. Connector **sqlite/file DB URLs** are a separate local-file-read follow-up (flagged, out of 0a scope).
