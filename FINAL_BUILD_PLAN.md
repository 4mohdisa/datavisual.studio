# datavisual.studio — Final Build Plan

**One plan. The app becomes complete, accessible, public, and deployed.**

Secret-scan → clean up → auth live → fix the chatbot → build one accessible design system → put every
app screen on it → build the portfolio-grade marketing site (landing, About, legal, SEO) → deploy.

**Scope honesty:** this is a large plan — likely more than one session. It is sequenced so it
**degrades gracefully**. There is a **SHIP GATE after Phase 6**: everything before it makes the product
live, public and honest. Everything after it makes it excellent. If you run out of time, stop cleanly at
a phase boundary with `main` deployable — never mid-phase.

**Backend work is out of scope tonight** except the auth integration in Phase 2. No Postgres migration,
no new pipeline features. That comes later.

---

## Read this first: the repo changed recently

A cleanup session removed genuinely dead code (`Blocks.jsx`, `start.sh`, `@axe-core/playwright`, 5 dead
symbols, 2 CSS keyframes, 2 unreachable import branches; net −768/+31, suite green at 276 pytest /
5 Vitest / 22 e2e) and **fixed a real bug**: `DEPLOY_RUNBOOK.md` pinned `v1.0.0-launch` in five places,
so following it would deploy the *pre-correctness* build.

**It also deleted most of the documentation**, along with an earlier commit
(`9ba41ad docs: remove overnight plan artifacts`). Gone: `HANDOFF.md`, `DECISIONS.md`,
`FEATURE_AUDIT.md`, `PROJECT_CONTEXT.md`, `DEPLOYMENT.md`, both sub-READMEs, probably
`PROJECT_AUDIT.md`. Survivors: `README.md`, `CLAUDE.md`, `DEPLOY_RUNBOOK.md`.

**So:**

1. **`ls` before assuming any doc exists.**
2. **`HANDOFF.md` and `DECISIONS.md` come back — but gitignored.** They're working notes, not
   public-repo content. That's why they were deleted; keep them out of git, not out of existence.
3. **The dead-code sweep is done. Don't redo it.** Phase 1 is structure + docs + dependency audit only.
4. **The secret-scan lead is gone but the risk isn't** — `DECISIONS.md` recorded that a working
   OpenRouter key lived in `data/settings.json` during dev. Scan history on its own merits.

## Hard rules

Storage stays JSON under `data/`. **No new runtime dependencies** beyond Clerk's server SDK. Dev/test
deps are fine (you'll need `@axe-core/playwright` back — the cleanup removed it because the a11y tests
were never written; now they will be). LLM emits specs only; owner keys never spent on a user's request;
strict public allowlist; no `%2f` interpolation; all frontend calls via `lib/api.js`; port 8001; Plotly
only via `LazyPlot.jsx`; don't touch `prediction_engine.py`; `main` only; no force pushes.

## Operating rules

- **Never ask. Never wait.** Ambiguous → smallest reversible option → log it → keep going.
- **`main` deployable at every commit.** Abort rule: two honest attempts, commit what's green, move on.
- **A green tick requires re-checkable evidence** — a CI run URL, a screenshot, a saved artifact.
  Reading code is not verification. Local-green is not remote-green.
- **Deleting anything requires a zero-reference grep in the commit body.**
- `HANDOFF.md` opens with `DEPLOY` or `DO NOT DEPLOY`.

---

# PHASE 0 — Secret scan + CI (hard gate)

### 0a. Scan all of git history

The repo is about to be public. **`.gitignore` does not protect history** — once public, anyone can pull
a committed secret out of the log. The pack is small (~279 KB), so this is fast.

Every commit: OpenRouter / Anthropic / Google / OpenAI keys, Clerk secret keys, `PROXY_SHARED_SECRET`,
`SECRET_KEY`, `ADMIN_PASSWORD`, any `.env*`, `data/settings.json`, `data/users.json`. Use
`git rev-list --all` + `git grep`, `git log -p`, and `gitleaks`/`trufflehog` if available. Match key
**patterns** (`sk-`, `sk-or-`, `sk-ant-`, JWT shapes), not just filenames.

### 0b. If ANY secret is found

**Do not publish.** `HANDOFF.md` line one: `DO NOT DEPLOY — secret in git history`. List each finding
(commit, file, kind). Write purge commands (`git filter-repo`/BFG) **and** a rotation checklist — a key
that was ever public must be **rotated**, not merely deleted. **History rewrites and force-pushes are
the owner's to run, not yours.** The rest of the night proceeds privately.

### 0c. CI green on GitHub — outstanding for three nights

Auth `gh`, trigger the workflow, `gh run watch` to completion, fix the YAML against **real runs** until
green. Expect Chrome/kaleido, Playwright browsers, and the e2e port to be the failures — CI is a
different environment from the dev box. **Nothing publishes or deploys on a suite nobody has watched run
remotely.** Put the passing run URL in `HANDOFF.md`.

---

# PHASE 1 — Structure, dependencies, docs

### 1a. Dependency audit

The dead-code sweep is done; dependencies deserve one more pass. Cross-check `package.json` and the
Python deps against real imports (`depcheck`/`knip` if available, grep otherwise). Remove what's
provably unused — with the grep in the commit body. **Re-add `@axe-core/playwright` as a dev dep**;
Phase 3 uses it properly this time.

### 1b. Folder structure

Clear module boundaries; no loose scratch files at root; tests where they belong; scripts in `scripts/`.
Fix every import a move breaks; green after each.

### 1c. Docs

- **`ARCHITECTURE.md`** — the request path (browser → Vercel/Next proxy → FastAPI → `data/`), where
  things live, the invariants, and the *why* behind non-obvious decisions (this is the rationale the
  deleted `DECISIONS.md` held, and it's genuinely valuable to a public reader).
- **`HANDOFF.md` + `DECISIONS.md` recreated and gitignored.** Note the convention in `CLAUDE.md` so a
  future session neither deletes them nor commits them.

---

# PHASE 2 — Clerk authentication, live (early, so everything downstream is built under real auth)

**Auth goes before the UI work on purpose.** Every prior night ran in open dev mode, so the ownership
model has never been exercised. Doing it now means every screen you build afterwards is verified under
real auth once — not built in dev mode and re-tested later. It also immediately surfaces whether auth is
what broke the chatbot (Phase 3's prime suspect).

### 2a. Frontend

Production Clerk keys in env (**deploy-platform secrets, never committed**; documented in
`.env.example`). Sign-in / sign-up / user-button / sign-out live. Middleware protects app routes;
`/`, `/about`, `/demo`, `/share/*`, `/privacy`, `/terms` stay public. Verify the identity headers
(`x-clerk-user-id` / `x-user-email` / `x-user-name` + `x-proxy-secret`) actually arrive on a real
signed-in request.

### 2b. Backend integration — persist the user on signup

First authed request from a new Clerk id → the backend creates its `u_<hex>` record in `users.json`
(existing `users.py` mapping; confirm it fires and persists atomically). Then a **Clerk webhook**
(`user.created` → a dedicated backend endpoint) so the user exists server-side at signup, not lazily.

**It's a public endpoint taking external POSTs — full paranoia:** verify the **Svix signature** on every
call, reject unsigned/mis-signed, and **do NOT add a prefix exemption to the `[...path]` proxy** (the
pattern behind the two `%2f` criticals) — dedicated route plus traversal/tamper regression tests. If the
webhook is too much, ship solid tested lazy-create and record which in `DECISIONS.md`.

**Per-user key scoping under real auth:** user A's encrypted key used only for A; the owner's key never
spent on a user's request.

### 2c. Prove ownership — its first real test

Two real Clerk accounts, real browser sessions, screenshots: A signs up → `u_<hex>` exists; A creates a
dashboard → owner-scoped; **B gets 404 on A's dashboard, conversation, dataset, export**; A's share link
still opens anonymously; a forged `x-clerk-user-id` without the proxy secret is refused. **Ships on two
accounts and a screenshot, not on assertions.**

---

# PHASE 3 — The chatbot (the owner's top priority)

### 3a. Honest status

**Reported twice:** asking a question about the data shows *"Updating dashboard"* — it's answering, not
updating.

- Reproduce in a real browser with Network + console open. Capture the actual failure. Night 3 added
  intent-driven `busyLabel` — confirm whether it regressed, never covered this path, or is overridden.
  **Phase 2 just changed the auth path; if the chat request now arrives without identity and is
  rejected, that's your bug.**
- **Write the failing e2e test before fixing.**
- Status follows intent everywhere, no stale default: `question` → "Reading your data…" / "Computing…" ·
  `edit` → "Updating the dashboard…" · `both` → "Answering and updating…" · `add_insight` → "Searching
  the web…". **No path shows "Updating dashboard" while answering.**

### 3b. Close the aggregation bug family

Night 3 fixed *summing a stock across time* but left a sibling live, logged as "defensible": **"how many
customers in June" returns 483 (one plan) instead of 731 (all three).** It isn't defensible — 731
answers the question asked; 483 answers one nobody asked, delivered as if they had. **Strangers are
about to try exactly this on a public demo.**

- **Deterministic ambiguity gate:** when the user asks for a total / count / how-many and the executed
  spec carries a `group_by` splitting the measure across a dimension the question never named — either
  aggregate to the total they asked for and say so ("731 customers across all plans in June 2026"), or
  **return both the total and the breakdown.** A breakdown is never wrong; a silent single-group answer
  is. Deterministic Python, not a prompt tweak.
- Extend the golden set with hand-computed totals; run against a real model.
- **Show-the-working makes scope unmissable** — "showing: Starter plan only".

### 3c. Answer experience

Lead with the number and its unit. Never cite an internal column name (`mrr_sum`) at the user. Offer the
next step. Pin-as-metric works. Prove with browser screenshots **under live Clerk**.

---

# PHASE 4 — Design system + accessibility foundation

This is the enabler for Phases 5 and 6. Build it once, correctly, then apply it everywhere.

### 4a. Tokens

Semantic layer in `tokens.css`: `--bg-*`, `--fg-*`, `--border-*`, `--accent*`, `--focus-ring`,
`--success/--warning/--danger`, **`--delta-up`/`--delta-down`**, a 4px spacing scale, radii, shadows, a
**z-index scale** (ad-hoc z-indexes are why overlays fight), motion (`--duration-*`, `--ease-*`). Wire
into `tailwind.config` so `bg-surface`, `text-muted`, `border-default` are real classes.

**Every colour pair must meet WCAG AA before it enters the token file** — 4.5:1 for text, 3:1 for UI
components and graphics. Check them as you define them; retrofitting contrast after the fact means
redoing every screen.

### 4b. Layout primitives

`<Page>` · `<PageHeader title actions>` · `<Section>` · `<Stack gap>` · `<Row gap align justify>` ·
`<Grid cols gap>` · `<Card>` · `<EmptyState>` · `<ErrorState>` · `<LoadingState>`.

**The rule that actually aligns pages: no component sets its own outer margin.** Spacing is owned by the
parent primitive. Children with their own margins is *the* reason pages drift.

### 4c. Component kit, accessible by construction

Complete `components/ui/`: Select, Textarea, Checkbox, Toggle, Popover, Tooltip, Tabs, Table, Badge,
Alert, Toast, Dropdown, Spinner, Skeleton. **Every one ships with hover, focus, disabled, a visible
focus ring, correct ARIA roles, and keyboard operation.** Accessibility is a property of the primitive,
not a later audit — get it right here and every screen inherits it.

- **Modals/drawers:** focus trap on open, focus returns to the trigger on close, Escape closes,
  `aria-modal`, background inert.
- **Every interactive element reachable and operable by keyboard alone**, in a sensible tab order.
- **Target size ≥24×24 CSS px** (WCAG 2.2), ≥44px on touch surfaces.

### 4d. The accessibility work specific to *this* product

Generic a11y advice misses the two things that matter most here:

1. **Charts are invisible to screen readers.** A data-visualisation product with unreadable charts is a
   real gap — and you already have the fix sitting in the codebase. Every chart gets
   `role="img"` + a computed `aria-label` summarising it ("Line chart: MRR over time by plan. Enterprise
   rises from 41,200 to 52,761 across six months."), generated deterministically from the chart spec —
   **not by the LLM**. Then give every chart a **"View as table"** toggle: the data table is the text
   alternative, and it's the same table component you already ship. This is a genuine accessibility win
   and a nice product feature for everyone.
2. **The assistant is a live region.** Answers arrive asynchronously; a screen-reader user gets nothing
   unless you announce them. Wrap the response area in `aria-live="polite"`, announce status changes
   ("Computing…"), and make the answer focusable so it can be reviewed.

Also: skip-to-content link, one `<h1>` per page with correct heading order, landmark regions
(`<header> <nav> <main> <footer>`), form labels with errors associated via `aria-describedby`, and
`prefers-reduced-motion` honoured by **every** animation (relevant — Phase 6 adds more).

### 4e. Automated + manual checks

`@axe-core/playwright` on every route — **zero critical or serious violations**. Then the manual pass
axe can't do: tab through every screen with the mouse unplugged, and confirm the dashboard is usable.
Record findings in `A11Y_AUDIT.md`.

---

# PHASE 5 — Every application screen on the system

`/studio`, `/chat/[id]`, `/dashboard/[id]`, `/share/[t]`, `/demo`, `/admin`, sign-in, sign-up, 404, 500
— at **390 / 768 / 1440**. Screenshot each; fix misalignment, spacing, overflow; empty/loading/error
states everywhere (no blank screens, no dead spinners); one consistent fetch/loading/error pattern —
extend what `AppShell` establishes, don't invent a second.

Sign-in and sign-up get real design attention — they're the first screen a new user sees, and a default
drop-in reads as unfinished.

**Lock it:** Playwright visual snapshots per route × breakpoint, committed and diffed in CI, alongside
the axe scans.

---

## ⛳ SHIP GATE — tag `v1.1.0-golive`

Full suite green (`make test`, `make e2e`, Vitest, axe, `make smoke`, visual snapshots), CI green on
GitHub with a URL, chatbot proven under live Clerk, ownership proven across two accounts.

**At this point the product is live-ready, accessible, and honest.** Phase 6 makes the front door
worthy of a portfolio; Phase 7 ships it. If time runs short, stopping here is a real success.

---

# PHASE 6 — The marketing site: portfolio-grade

This project goes in the owner's portfolio. The site has **two audiences at once**: someone who might
*use* the product, and someone evaluating the owner as an engineer. It must serve both without reading
as a résumé.

### 6a. Landing page — the full story

Built on the Phase 4 system. Sections, in order:

1. **Hero.** A stranger must know what this is within five seconds. The headline carries the idea of
   *change* — the thing Power BI doesn't do. Keep and extend the living-monitor replay (a dashboard that
   changes while you watch).
2. **The problem.** Dashboards tell you what happened; nobody tells you what *changed*. Plain language,
   no jargon.
3. **Who it's for** — concrete personas, not adjectives: a solo founder watching MRR and churn; an
   analyst without a BI budget; a researcher tracking a topic across both their data and the live web; a
   small team that needs a shared, always-current view.
4. **How you use it** — the workflow as a visual, animated sequence: connect data → build a dashboard →
   pin the questions that matter → one click keeps numbers *and* the live web in sync and tells you what
   moved.
5. **What you can do** — the capability showcase, animated: instant dashboards from any CSV, 9 chart
   types, ask questions in plain English and get *computed* answers, the AI research council, public
   share links, PDF/HTML export, threshold alerts.
6. **How it's built** — *the portfolio section.* An architecture diagram (browser → Vercel/Next proxy →
   FastAPI → JSON store), the stack, and the **decisions worth explaining**: the LLM only ever emits
   specs while charts and numbers are computed deterministically; numeric grounding so the assistant
   can't state a figure it can't defend; BYO API keys so users pay their own providers; a multi-model
   council with anonymous peer review; no database, by design. **Write it as engineering reasoning, not
   a feature list** — that's what makes it read as a portfolio piece rather than marketing.
7. **Try it** — the `/demo` CTA, repeated. No sign-up, no key.
8. **Pricing, plainly** — free; you bring your own AI key and pay the provider directly. **Name the real
   per-run cost.** Vagueness about money reads as a trap.
9. **FAQ** (keep, extend).
10. **Footer** — ⭐ Star on GitHub (the repo), **isaxcode.com**, legal links, IdeaRadar.

**No fake social proof.** No invented logos or testimonials. Product proof only: the live demo, a real
share link, "no card, no key to start."

### 6b. Animation — and its tension with SEO

More animation is requested. It has a real cost, so build it to not hurt:

- **Server-render the end state; animate after hydration.** An animation that gates the first paint hurts
  **LCP**, which is both an SEO ranking signal and a real user experience.
- **Reserve space for every animated element** so nothing shifts — **CLS** is the other ranking signal,
  and charts loading into unreserved space is the classic cause.
- CSS transforms/opacity only; no layout-thrashing animation. No new animation library.
- **`prefers-reduced-motion` renders the final state immediately**, everywhere. Non-negotiable — vestibular
  disorders are real and this is a WCAG requirement, not a preference.
- Animation carries meaning (a number ticking, a delta flipping, a source arriving) or it doesn't ship.

### 6c. `/about` — new page

The project's story: why it was built, what problem it solves, what was learned, the hard parts (getting
an LLM to never state an ungrounded number; making a multi-model council agree on a citation; shipping a
data product a screen reader can use). Short author bio with **isaxcode.com** and GitHub. This page is
both portfolio content and genuine SEO surface — it targets queries the landing page can't.

### 6d. Legal pages — accurate, not boilerplate

`/privacy` and `/terms` exist; **make them true.** Night 2 added first-party analytics with an `anon_id`
cookie and a funnel event stream — the current policy predates that and doesn't describe it. State
plainly: what's collected, that it's first-party only with no third-party trackers, what's *not* logged
(dataset contents and cell values are never in an event), that BYO API keys are encrypted at rest, how
long data is kept, and how to request deletion. Provide an analytics opt-out. Honest and specific beats
long and generic.

### 6e. SEO — beyond what's already there

Existing: metadata, generated OG image, robots, sitemap, manifest, SoftwareApplication + FAQPage JSON-LD.
Add:

- **Per-route metadata** — unique title, description, canonical, and OG image for `/`, `/about`,
  `/demo`, `/privacy`, `/terms`. Duplicate titles are the most common self-inflicted SEO wound.
- **Semantic HTML** — one `<h1>` per page, correct heading order, landmark regions. This is the same work
  as Phase 4's a11y foundation: **accessible markup is the SEO markup.** Do it once.
- **JSON-LD:** add **`Person`** (the portfolio signal, linking isaxcode.com and GitHub),
  **`BreadcrumbList`**, and **`HowTo`** for the workflow section.
- Descriptive alt text on every image; internal links between landing ↔ about ↔ demo; new routes in the
  sitemap; app/admin/share stay `noindex`.
- **Core Web Vitals** measured, not assumed — LCP, CLS, INP on the landing at mobile width. Fix what's
  red before calling this done.

---

# PHASE 7 — Monorepo, authorship, deploy

### 7a. Monorepo + production-shaped boot

`docker compose` builds both with prod env: `PROXY_SHARED_SECRET`, `SECRET_KEY`, `ALLOWED_ORIGINS`
locked, real Clerk keys, `NEXT_PUBLIC_BACKEND_ORIGIN` pointing the frontend at the backend as a
**separate origin** (the real Vercel↔AWS shape). `vercel.json` roots at `frontend`; standalone only under
`DOCKER_BUILD=1`; `/health` green; CORS preflight passes from the app origin, refused from unknown.

### 7b. Authorship and the open-source package

- **`LICENSE` — MIT, Mohammed Isa**, current year.
- **Author metadata everywhere it belongs:** README, `package.json` `author` field, site `author` meta
  tag, and the `Person` JSON-LD — **Mohammed Isa (@4mohdisa)**, linking **isaxcode.com**.
- **Footer:** ⭐ Star on GitHub (repo link) **and** isaxcode.com. The *author byline* links isaxcode.com,
  not the GitHub profile; the *star button* links the repo.
- **`SECURITY.md`** — private vulnerability reporting. **`CONTRIBUTING.md`** — how to run it, test
  commands, the PR bar (CI green), the invariants a contributor must not break.
  `CODE_OF_CONDUCT.md`, `.env.example` for both halves with every var documented and **no real values**,
  issue/PR templates.
- **README** — what it is in one clear paragraph, a screenshot or GIF, how it's built (linking
  `ARCHITECTURE.md`), quickstart, features, security **and known limitations**, license, ⭐ star line.

### 7c. Known limitations — state them plainly

The deleted `DECISIONS.md` held these, and a self-hoster must know them: **single-replica only**
(in-process locks, rate limiter, upload nonces); **`SECRET_KEY` must travel with `data/`** or encrypted
keys become unreadable; **`data/` is the only copy — back it up**; sqlite/file DB URLs in the connector
are a known local-file-read follow-up; the SSRF guard has a narrow DNS-rebinding TOCTOU window (mitigate
with IMDSv2). Plus the self-hoster hardening checklist. **Overclaiming security is worse than stating
boundaries** — honest limitations build more trust than a clean-looking omission.

### 7d. `make verify-deploy` + runbook

One command running the whole checklist, pass/fail per line: `/health` · the `%2f` trio · >5MB direct
upload · full pipeline · mint+revoke share · `/admin` rejects a bad password · **the Clerk ownership walk
(2c)**. Two drills: `SECRET_KEY` correct → boots and decrypts; fresh key on the same `data/` → refuses to
boot with the explicit error. **Pin replica/worker = 1** in deploy config and say so in the runbook.

`DEPLOY_RUNBOOK.md` — numbered, copy-pasteable, updated to the final tag: Clerk prod instance + domain;
secrets set identically where they must match; **`data/` on a persisted volume with `SECRET_KEY`
alongside**; **the backup cron installed BEFORE announcing** — `data/` is the only copy, no hosted DB is
holding a backup, so a dead disk means every user's dashboards are gone; DNS + TLS; Chromium in the
backend image; `make verify-deploy` against the live host; then open the door.

---

# PHASE 8 — Ship

Full suite green; CI green on GitHub with a URL; axe clean; Core Web Vitals measured; every screenshot
saved. Repo public with MIT LICENSE and full docs; Phase 0 scan clean and recorded. Tag `v1.2.0` (or
re-tag if Phase 6 changed user-facing behaviour). `HANDOFF.md`: `DEPLOY`, the tag, the CI URL, the deploy
sequence, and what's left.

---

# NOT tonight

**The Postgres migration and other backend work.** The migration overturns the JSON invariant the entire
security model leans on (SSRF guard, atomic writes, per-conversation locks, encrypted keys,
single-replica assumption) — the largest, riskiest change in the project's history. It is cleanly
contained (everything funnels through `backend/storage.py` and the `u_<hex>` id), so it deserves its own
session with a schema, a migration script against the live `data/`, a cutover and rollback strategy, and
a parity harness proving nothing was lost. Not alongside auth-live and a full front-end rebuild.

---

## Definition of done

- **Secret scan clean and recorded** (or publish blocked with purge + rotation instructions).
- **CI green on GitHub, URL recorded.**
- **Clerk live; user persisted on signup; ownership proven across two real accounts with screenshots.**
- **Chatbot: honest intent-driven status, and the aggregation gate closed (731, not 483)** — failing-first
  tests, browser screenshots, under live Clerk.
- **WCAG 2.2 AA:** axe clean on every route; keyboard-only pass; charts have text alternatives; the
  assistant announces; reduced-motion honoured. `A11Y_AUDIT.md` written.
- Every screen on one design system across 3 breakpoints; visual snapshots in CI.
- **Landing explains what it is, who it's for, how you use it, what you can do, and how it was built.**
  `/about` live. Legal pages accurate about the analytics cookie. Per-route metadata, `Person`/`HowTo`/
  `BreadcrumbList` JSON-LD, Core Web Vitals measured.
- **Authorship: Mohammed Isa (@4mohdisa)** in LICENSE, README, package metadata, site meta and JSON-LD;
  footer carries ⭐-star + isaxcode.com; the byline links isaxcode.com, not the GitHub profile.
- `make verify-deploy` passes; runbook ends in a human go-live sequence with the backup cron before
  announce.
- Storage still JSON; no new runtime dependencies; backend work deferred.