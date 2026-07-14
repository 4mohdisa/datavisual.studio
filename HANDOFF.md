DEPLOY

# Overnight run 3 — handoff

_First line is the verdict. Deploy **`v1.0.2-correctness`** (main HEAD) — it supersedes
`v1.0.1-launch`, which reported wrong numbers and had broken export + scroll._

## Verdict: DEPLOY `v1.0.2-correctness`

Night 3 was "prove what exists and fix what's lying." The owner found five frontend-runtime bugs in five
minutes that 258 passing pytest tests structurally could not see. **All five are now fixed, each with a
test that failed before its fix, and each UI fix verified in a real browser with a screenshot.** The
test-harness gap that let them ship is closed.

| Owner-found bug | Fix | Proof |
|---|---|---|
| **Wrong number** — "total MRR" = 480,506 (summed a stock across 6mo×3plan; real ≈ 91k) | measure classifier + deterministic stock-total = latest period | `test_answer_correctness`, `test_golden_questions`; browser: "90,596 on 2026-06-01" |
| **Invented unit** — "weekly earnings are 480,506" (no conversion) | numeric-grounding + unit guard fails closed; refuses/derives | `test_answer_correctness`; browser: refused |
| **Blank/white export** — dark PDF, some components missing | light print-designed CSS + `print-color-adjust`; every widget; light kaleido PNGs | `test_export_document`; browser: 3-page light PDF |
| **No export feedback** — button swallowed errors | `ExportDashboardButton` state machine idle→generating→download/error | `ExportDashboardButton.test.jsx` (Vitest) |
| **Unreachable scroll** — share/demo won't scroll | `min-h-screen`→`h-screen` (real scroll container) | `scroll.spec.js` + cross-route class-killer; browser: reaches footer |

Plus the cause: the **e2e harness now binds to a configurable port** (`E2E_PORT`, default 3100, never
3000) and CI runs **Vitest + Playwright** on every push — the reason Night 2 skipped e2e and shipped bugs.

Local at HEAD: **276 pytest · 5 Vitest · 22 Playwright e2e — all green.** Also see `DECISIONS.md`
(Night 3) for one known limitation (ambiguous "how many in <period>" can under-aggregate; the engine is
correct, the model's spec choice isn't always).

---

# Overnight run 2 — handoff (historical)

_Night 2 shipped `v1.0.1-launch`. Night 3's fixes are additive on top._

## Why `v1.0.1-launch` was safe

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

## Phase 2 progress since the tag (all on `main`, past `v1.0.1-launch`, each commit green)

The tag is the deploy point; these are additive improvements you can re-tag later (Phase 9 → v1.1.0):

- **2a CI** — `.github/workflows/ci.yml` runs pytest + next build + the restore drill on every push/PR.
  *(Check its first run on GitHub — I couldn't observe it here, `gh` isn't authed; every command in it
  passes locally.)*
- **2d structural security** — a route-enumeration test fails the build if any endpoint isn't classified
  into one auth posture (so a new route can't ship without a conscious auth decision); + allowlist
  deny-scan on /demo and /public.
- **2b malformed-model-output** — caught + fixed a real **500 on a null op** in `apply_ops`.
- **2c pathological data corpus** — 31 weird inputs → clean analysis or clean 4xx, never a 500 or hang.
- **2d SQL guard** — caught + fixed a real **write-CTE / stacked-query bypass** in the connector
  (`WITH x AS (INSERT …) SELECT …` used to pass). Now blocks writes, stacked statements, `SELECT … INTO`,
  and dangerous functions.

pytest **182 → 258**. Two real bugs found and fixed by the new tests.

## Still to do (Phases 2 remainder → 9, more than one night)

Phase 2 remainder: LLM cassettes/FakeLLM + silent-drop detection ("council ran with 2 of 4 models" must
say so), ownership matrix, concurrency, e2e journeys (blocked here — e2e wants port 3000, taken by your
other app), visual regression, coverage floor. **Then** Phase 3 theme-token refactor (tokenise with ZERO
visual change first, snapshots pixel-identical) **before** Phase 4 landing/onboarding rebuild. Then
analytical depth (5), scheduler/digest/unsubscribe to complete the living monitor (6), research quality
(7), dashboard customisation (8), close-out + v1.1.0 (9). See `OVERNIGHT_PLAN_2.md`.

## Confirm with me (in `DECISIONS.md` → "Assumptions to confirm")

1. **Single replica assumed** — rate-limit buckets, per-conversation lock, upload nonce, events limiter
   are all in-process. Don't run >1 backend replica without addressing it.
2. **`SECRET_KEY` travels WITH `data/`** — back them up together; a fresh key against restored data now
   **refuses to boot** (0e) rather than silently losing keys.
3. Enforce **IMDSv2** on the instance regardless of the code SSRF fix (runbook §0.3) — defence in depth.
4. Connector **sqlite/file DB URLs** are a separate local-file-read follow-up (flagged, out of 0a scope).
