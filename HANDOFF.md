# Overnight run — handoff

_What shipped, what didn't, and how to check it in five minutes._

## TL;DR

**The app is deployable now.** Tag **`v1.0.0-launch`** is pushed and passes the full suite. The ship
gate (phases 0–6) is complete: security fixes committed, data made safe (atomic writes + key
encryption + backups), the host split made Vercel-ready (polling pipeline + direct upload), the broken
assistant fixed (it computes answers now), UI/state gaps closed (real 404/500, mobile sidebar),
the landing became a living-monitor hero, and launch hardening landed (zero-key onboarding, rate
limiting, disk GC, CSP). Phase 7's **alerts** slice also shipped as post-launch upside.

Deploy `v1.0.0-launch` per **`DEPLOY_RUNBOOK.md`**. Everything after the tag is additive and green.

## Verify in 5 minutes

```bash
make install           # once
make test-backend      # 115 pytest, hermetic, no network
make build             # backend import + next build
# with the stack running (make dev, or backend :8001 + frontend):
make smoke-split       # 17 checks: SEO, %2f guards, golden path, /health, >5MB upload
```
All of the above were green at tag time.

## What shipped (per phase, each committed + pushed to `main`)

| Phase | What | Proof |
|---|---|---|
| 0 | Committed the uncommitted tree **security-first** (the two `%2f` traversal fixes led) | 7 commits |
| 1 | **Atomic JSON writes** + per-conversation lock; **Fernet key encryption** at rest + boot migration; `backup.sh` | +9 tests |
| 2 | **Polling pipeline** by default (SSE behind `?stream=1`); **HMAC direct upload** (>4.5MB skips the proxy); `vercel.json`, conditional standalone, `/health`, security headers | verified live (40ms kickoff; 17/17 split smoke) |
| 3 | **Assistant fixed**: intent router + `backend/query.py` deterministic query engine → answers are computed, not guessed; "Pin as widget" | +14 tests |
| 4 | Real **404/500/error** boundaries; **mobile sidebar** slide-over; automated `UI_AUDIT.md` sweep | no true page overflow anywhere |
| 5 | **Living-monitor hero** — a dashboard that changes while you watch (count-up, delta flip, "what changed" writes itself) | verified live |
| 6 | **Zero-key onboarding** (3 samples + "Try it with sample data"); **rate limiting**; **disk GC**; **CSP** | +9 tests; 429 verified live |
| SHIP | `v1.0.0-launch` tagged; `DEPLOY_RUNBOOK.md` | — |
| 7 (partial) | **Threshold alerts** on metric widgets, owner-only, evaluated on sync | +7 tests |

Test count went 71 → **115 pytest**; smoke 15 → **17** (+ the >5MB upload under `SPLIT=1`).

## What did NOT ship (remaining upside, in priority order)

- **Phase 7 remainder** — the *scheduled* sync (`backend/scheduler.py` asyncio lifespan task),
  email digests (`email_send.py` / `digest.py` via Resend), and the **unsubscribe** flow. Alerts and
  the manual "Update" already fire; automating them on a timer + emailing the digest is the next step.
  Deliberately deferred: the background task + external email + unsubscribe security are the riskiest
  parts and shouldn't land hastily right after a clean launch tag. A frontend **alert bell** on metric
  hover (handler-gated so it can't render in `SharedView`) is also pending — alerts work via the chat
  today ("alert me if revenue drops 10%").
- **Phase 8** — dashboard customization: drag/resize widgets, cross-filtering, saved views, duplicate.
- **Phase 9** — research quality: two-round search, per-claim citations, disagreement panel, research
  cache, spend meter, council picker.

## Things to confirm with me (also in `DECISIONS.md`)

1. **Single replica is assumed everywhere** — rate-limit buckets, the per-conversation lock, the
   single-use upload nonce, and (when built) the scheduler are all in-process. Don't run >1 backend
   replica without addressing this.
2. **`SECRET_KEY` is required in prod** and losing it means users re-enter their API keys.
3. The **assistant's full LLM round-trip couldn't be verified live tonight** — the dev OpenRouter key's
   fast model was >90s slow in this sandbox. The deterministic query engine + router are tested; the LLM
   glue mirrors the already-working editor. Please run one real question against it.
4. **CSP `script-src` is permissive** (`'unsafe-inline' 'unsafe-eval' https:`) because Next inlines
   scripts and Plotly evals; tighten to nonces after verifying against the live Clerk domain.
5. The **backend host RAM** — this backend loads pandas + xgboost + scikit-learn + Chromium; if the EC2
   box is small, give it a separate instance (see runbook §0).

## Docs on disk

`DEPLOY_RUNBOOK.md` (go-live), `DECISIONS.md` (every non-obvious call + assumptions), `UI_AUDIT.md`
(the sweep), `PROJECT_AUDIT.md` + `PROJECT_CONTEXT.md` (the map), `CLAUDE.md` (gotchas, updated),
`OVERNIGHT_PLAN.md` (the plan I executed).
