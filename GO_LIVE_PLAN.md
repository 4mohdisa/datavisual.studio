# datavisual.studio — Go-Live Plan

**The build is done.** What's left: one live bug in the headline feature, a test suite nobody has
watched run, and a deployment shape that has never been exercised — including the AWS backend host
itself.

Short plan. There is no large backlog behind it.

---

## Before this session can finish

```bash
gh auth login
```

and paste **real** Clerk production keys into `frontend/.env.local` — the last session found
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` present but **empty strings**.

Phase 0 needs neither. Phases 1–3 do.

## Deployment shape (confirmed)

**Frontend on Vercel. Backend from this monorepo on an existing AWS instance. Storage is JSON files on
that instance's disk.**

**There is no SQL database and nothing to provision for one.** `sqlalchemy`, `psycopg2-binary` and
`pymysql` appear in the backend dependencies **only for the user-facing data connectors** — so a *user*
can import a table from *their own* Postgres/MySQL/SQLite. They are not this application's storage.
Anyone reading the dependency list will assume a database server is required. It is not. Say so plainly
in the runbook so nobody provisions one.

(Postgres for the app's own storage is a separate, later piece of work. It changes nothing here.)

## Hard rules

Storage stays JSON. No new runtime dependencies. `main` only, no force pushes. Deleting anything needs a
zero-reference grep. **Never run `next build` while the dev server is running against the same
`.next`** — it corrupts the dev server's CSS and produces phantom failures. A green tick requires
evidence a human could re-check.

---

# PHASE 0 — The assistant errors on the most common question there is

**Reported, in the real UI:**

> **User:** what is this about?
> **Assistant:** Dashboard edit failed

Two failures in one response. A **question** was routed down the **edit** path, and that path threw. The
error text is wrong too — it says "edit" for something that was never an edit.

**"What is this about?" is the first thing most people type into an assistant they've never used.** On
`/demo` that is a stranger's first interaction with the product. This outranks CI.

### 0a. Reproduce and capture the real failure — don't guess

Real browser, Network and console open, backend log alongside. Establish precisely: what status and body
does `POST /api/dashboard/{id}/chat` return? What did the **server's** `classify_intent` decide? Where
did it throw — intent classification, query-spec generation, spec execution, the answer guard, or the
endpoint itself? And is **"Dashboard edit failed"** a generic frontend catch-all for any chat failure? If
so that's a second, separate bug. **Write the failing test before fixing.**

### 0b. The likely root cause — it's in your own docs

The original project audit, §11 known issues, verbatim: *"Dashboard-assistant sometimes gives thin
answers to non-edit questions ('what is this report about?') because the editor prompt is tuned to emit
ops."* Flagged at the beginning, listed as a stretch item, never done — and now degraded from a thin
answer into a hard error.

**The gap:** `backend/query.py` answers **data** questions by emitting a query spec and executing it with
pandas. "What is this about?" is not a data question — nothing to select, nothing to aggregate — so spec
generation produces something empty or invalid and the path falls over.

### 0c. Add a third intent: `meta`

Alongside `question` / `edit` / `both`, route questions **about** the dashboard, the data, or the
assistant itself to a handler that answers from context the backend already holds — **no query spec, no
pandas execution**: the dashboard spec (title, widget titles, what's charted), the dataset profile
(columns and kinds, row count, date range, source), the pipeline summary and report when the record is a
research run, and what the assistant can do.

The engine supplies the facts; the model only phrases them. Same discipline as everywhere else here.

### 0d. Errors must follow intent, and must never be dead ends

The status-label rule now extends to failures: **no path may report an edit failure for something that
wasn't an edit.** An error should say what failed and what to try next — never a bare "failed" with
nowhere to go. Audit every error string in the assistant path.

### 0e. The durable fix: test what people actually type

Three sessions have declared the chatbot fixed; three times it broke within a minute of real use.
**The cause is that the golden set is drawn from the plans** — "total MRR", "customers in June" — all
data queries on the sample dataset. **Nobody has tested the messages a real person sends first.**

Add a **first-message set**, every one required to produce a *useful* response — never an error, never a
dead end:

`what is this about?` · `what can you do?` · `explain this dashboard` · `summarise this` · `what data is
this?` · `help` · `hello` · `hi` · an empty message · a single `?` · a question about a column that
doesn't exist · a bare noun with no verb ("revenue") · a rude or nonsense message.

Run them on **both** a data dashboard and a research record — they differ, and only one has a pipeline
summary. Then run them **on `/demo`**, because that's where a stranger meets it.

---

# PHASE 1 — Make CI green on GitHub

Six sessions have pushed commits triggering runs nobody has looked at. **Assume CI is red** — the
workflow has never been validated in its own environment, and CI differs from the dev Mac in every way
that matters.

Expected failures by likelihood: **Chrome/kaleido** for the chart PNG test (a prior session made it
"skip gracefully" — confirm it actually skips rather than fails); **`playwright install --with-deps`**;
the **e2e port**; **`uv` setup, Node version, WeasyPrint system libs**, and the restore drill.

Method: `gh run list`, `gh run watch` the latest on `main`, read the **actual logs**, fix, push, watch
again — iterate against real runs, not a reading of the YAML. **Repeat until a run is genuinely green**,
then put that URL in `HANDOFF.md`. That URL is the deliverable. If several rounds don't get there, commit
the progress and record exactly which step fails and what the log says, so the next attempt starts from
the failure rather than from scratch.

---

# PHASE 2 — The production shape, including the AWS host

Two halves have never been exercised: the **two-origin split**, and the **backend host itself**.

### 2a. Two-origin boot

`verify-deploy` passes 19/19 — but against the dev stack on a **single origin**. The real deployment is
two origins, and that has never been booted.

- `docker compose` builds both with production env: `PROXY_SHARED_SECRET`, `SECRET_KEY`,
  `ALLOWED_ORIGINS` locked, and **`NEXT_PUBLIC_BACKEND_ORIGIN` pointing at the backend as a genuinely
  separate origin**. Dev Clerk keys are fine — this tests plumbing, not auth.
- Exercise what only breaks across origins: **CORS preflight** on the direct-upload path (allowed from
  the app origin, refused from an unknown one), the **HMAC upload ticket** with a >5MB file, the
  **polling pipeline** to completion, `/health` through the proxy.
- **Run `make verify-deploy` against that two-origin stack.** A check that only passes single-origin
  isn't verifying the deployment.
- Confirm `data/` survives a container restart, and that `next.config` standalone stays gated on
  `DOCKER_BUILD=1` so Vercel uses its native build.

### 2b. Resource headroom — measure it, don't assume

**The likeliest way this deploy fails is the backend being OOM-killed on a box that's already busy.**
The instance already runs another application and has needed a swap file, and this backend imports
pandas, xgboost, scikit-learn, scipy and plotly, then spawns **Chromium** for PDF export.

- Measure the backend's resident memory: at idle, after a full research pipeline, and during a PDF
  export (Chromium is the spike). Record the numbers.
- Compare against the instance's free memory with the other app running.
- **If it doesn't fit with real headroom, say so plainly in the runbook and recommend a larger or
  separate instance.** Do not hand over a deploy that only works until someone exports a PDF.
- Disk: `data/` was already ~63 MB at 16 conversations; uploads are capped at 50 MB each and exports
  accumulate. Note the growth rate and confirm the volume has room.

### 2c. Backend host runbook — a repeatable path, not prose

Write the actual sequence for standing the backend up on the AWS instance. Prefer the existing
`docker compose` path — the backend image already installs Chromium, which is the fiddliest dependency
to get right by hand. Cover:

- **Get the code onto the box** from the monorepo, and how to update it (the repeatable deploy step).
- **Port 8001** — 8000 is taken by the other application.
- **`data/` on a persisted path**, with **`SECRET_KEY` stored alongside it**. A fresh key against
  restored data now refuses to boot rather than silently losing every user's API key — that behaviour is
  correct, and the runbook must explain it so it isn't mistaken for a fault.
- **Single replica / worker = 1**, pinned in the config. In-process locks, rate limiter and upload
  nonces all assume it.
- **No database to install** — and why the SQL libraries are present anyway (see the top of this plan).

### 2d. Reachability, TLS and the proxy chain

Vercel must reach the backend over **HTTPS**, so it needs a public hostname (e.g. `api.` on the domain),
TLS, and a reverse proxy in front.

- **`ALLOWED_ORIGINS` = the Vercel app origin only.** Never a wildcard.
- **`PROXY_SHARED_SECRET` set identically on both halves** — the backend 403s anything arriving without
  it, which is what stops a publicly-reachable backend from being used directly.
- **Don't expose port 8001 to the world** in the security group; let the reverse proxy front it.
- **`TRUSTED_PROXY_HOPS` must match the real proxy chain.** The rate limiter derives the client IP from
  `X-Forwarded-For` using that hop count — set it wrong and you either rate-limit every user as one
  client or let a spoofed header bypass the limiter entirely. Verify it against the actual chain
  (reverse proxy, plus Cloudflare if it's in front), don't guess.
- **Enforce IMDSv2 on the instance** — defence in depth alongside the SSRF egress guard, since the two
  are independent.

### 2e. The two crons — install before announcing

- **Backup of `data/`.** It is the only copy; no hosted database is holding one for you. A dead disk
  means every user's dashboards are gone. **This goes in before anyone is invited.**
- **`make gc`** — uploads and exports grow forever otherwise, and a full disk on a shared box takes the
  other application down with it.

---

# PHASE 3 — Live auth walk, then tag

If real Clerk keys are present: two accounts, real sessions, screenshots. A signs up → a `u_<hex>` record
appears in `users.json`; A creates a dashboard; **B signs in and gets 404 on A's dashboard, conversation,
dataset and export**; A's share link still opens anonymously; a forged `x-clerk-user-id` without the
proxy secret is refused. **Run the Phase 0e first-message set under real auth too** — every chatbot test
so far has been in open dev mode.

With CI green and its URL recorded: tag **`v1.1.0-golive`**, update `DEPLOY_RUNBOOK.md`, and write the
go-live sequence into `HANDOFF.md`.

---

## Definition of done

- **`what is this about?` returns a useful answer** — on a data dashboard, a research record, and
  `/demo` — with a failing-first test and a browser screenshot. **The whole first-message set passes,
  none of it erroring.**
- **No error message reports an edit failure for a non-edit action.**
- **A green CI run on GitHub, with its URL in `HANDOFF.md`.**
- **The two-origin production shape booted and `make verify-deploy` passed against it.**
- **Backend memory measured under load** (pipeline + PDF export) against the instance's real headroom,
  with an honest verdict in the runbook.
- **A repeatable backend deploy sequence** covering port 8001, persisted `data/` + `SECRET_KEY`, single
  replica, TLS and the proxy chain (`ALLOWED_ORIGINS`, `PROXY_SHARED_SECRET`, `TRUSTED_PROXY_HOPS`,
  IMDSv2), the backup and GC crons — and a plain statement that **no database needs installing**.
- Live two-account walk done with screenshots (if keys are present).
- **`v1.1.0-golive` tagged**, `HANDOFF.md` opening with `DEPLOY`.