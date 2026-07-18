# datavisual.studio — Launch Plan

The product is close. Last session fixed the chatbot, shipped a real accessibility layer, and put
authorship in place. **Two things have been blocked on credentials for four sessions, and the biggest
owner request — the portfolio landing — hasn't been built yet.** This plan closes both.

Execute in order. Never skip. Never ask. Commit and push after each phase.

---

## Where things stand

**Done and verified last session:** secret scan clean (all blobs, commit messages, key patterns — no
secret in history); `lib/intent.js` extracted so status follows the server's authoritative intent
(the bug was a client heuristic that defaulted to "Updating the dashboard…" for any message not
starting with a question word — so "biggest month" lied while the server answered); deterministic
aggregation gate (731, not 483) with golden tests; chart `role="img"` + aria-labels decoded from
Plotly's binary typed arrays, plus a **View as table** toggle; assistant `aria-live`; skip link,
landmarks, reduced-motion, AA tokens; axe 0 serious/critical on 5 routes; **a real mobile bug fixed**
(the 360px assistant panel crushed the dashboard at ≤1023px — now a full-screen overlay);
MIT LICENSE, `/about`, footer byline → isaxcode.com, ⭐ star button, SECURITY/CONTRIBUTING/CoC.

Green: **281 pytest · 20 Vitest · 29 e2e.**

**Blocked on credentials (four sessions running):**
1. **CI has never been watched green on GitHub** — `gh` auth is interactive.
2. **The live two-account Clerk walk** — no prod keys were available to the agent.

**Not yet built:** the portfolio landing rewrite (the owner's headline ask), layout primitives and the
component kit, the secondary-screen breakpoint sweep, SEO completion, legal accuracy, and deploy
verification.

---

## Environment hazards learned last session — don't repeat them

- **Never run `next build` while the dev server is running against the same `.next` directory.** It
  corrupts the dev server's compiled CSS and produces phantom failures. Last session lost real time
  chasing contrast violations that were stale artifacts. Stop dev first, or build to a separate dir.
- **axe must wait for `.page-transition` to reach full opacity** before analysing. Mid-fade, every colour
  reads darker and contrast checks fail spuriously. This is already fixed in the scan — keep it.
- **Verify a claimed root cause before acting on it.** Last session changed tokens from `oklch()` to hex
  on the theory that Playwright's Chromium renders oklch grays darker — then found the real cause was the
  page-transition fade. The hex change is fine to keep (it's more portable), but **check the token layer
  isn't now inconsistently split between hex and oklch**, and correct the reasoning in `DECISIONS.md`.

## Hard rules

Storage stays JSON. **No new runtime dependencies.** LLM emits specs only; owner keys never spent on a
user's request; strict public allowlist; no `%2f` interpolation; all frontend calls via `lib/api.js`;
port 8001; Plotly only via `LazyPlot.jsx`; don't touch `prediction_engine.py`; `main` only; no force
pushes. Deleting anything requires a zero-reference grep in the commit body.

## Operating rules

- **Never ask. Never wait.** Ambiguous → smallest reversible option → log it → keep going.
- **`main` deployable at every commit.** Abort rule: two honest attempts, commit what's green, move on.
- **A green tick requires evidence a human could re-check** — a CI run URL, a screenshot, a saved
  artifact.
- `HANDOFF.md` (gitignored) opens with `DEPLOY` or `DO NOT DEPLOY`.

---

# PHASE 0 — Unblock the two credential-gated items

**These may now be unblocked** — the owner was asked to run `gh auth login` and place Clerk production
keys in `frontend/.env.local` before this session. Check both. **If either is still unavailable, log it
and move on immediately — do not stall.** The rest of the plan is productive without them.

### 0a. CI green on GitHub

`gh auth status`. If authed: list recent runs, `gh run watch` the latest on `main` to completion, and
**fix the workflow against real run logs** until it is green. Expect the usual CI-vs-dev-box gaps —
Chrome/kaleido for chart PNGs, `playwright install --with-deps`, the e2e port, system libs. **Put the
passing run URL in `HANDOFF.md`.** This is the single item gating `DEPLOY`.

### 0b. The live two-account ownership walk

If Clerk prod keys are present: boot with them and walk it in a real browser with screenshots —
A signs up → a `u_<hex>` record exists in `users.json`; A creates a dashboard; **B signs in and gets 404
on A's dashboard, conversation, dataset and export**; A's share link still opens for an anonymous
viewer; a forged `x-clerk-user-id` without the proxy secret is refused.

The backend ownership matrix is already proven deterministically with simulated headers — this closes
the gap between "the code is right" and "the product behaves right under real identity."

**Also verify the chatbot works under live Clerk**, which last session could only test in dev mode.

---

# PHASE 1 — Finish the design system (before the landing, so it isn't built twice)

Phase 2 rebuilds the landing. Build it on primitives or you'll build it twice — the same reasoning that
put testing before the theme refactor.

### 1a. Layout primitives

`<Page>` · `<PageHeader title actions>` · `<Section>` · `<Stack gap>` · `<Row gap align justify>` ·
`<Grid cols gap>` · `<Card>` · `<EmptyState>` · `<ErrorState>` · `<LoadingState>`.

**No component sets its own outer margin.** Spacing belongs to the parent primitive — children with
their own margins is *the* reason pages drift.

### 1b. Component kit, accessible by construction

Complete `components/ui/`: Select, Textarea, Checkbox, Toggle, Popover, Tooltip, Tabs, Table, Badge,
Alert, Toast, Dropdown, Spinner. Each ships with hover, focus, disabled, a visible focus ring, correct
ARIA roles and keyboard operation. Target size ≥24×24 CSS px.

### 1c. Focus management — the gap axe cannot see

**axe cannot test focus trapping, and the mobile assistant overlay shipped last session is a drawer.**
Right now it very likely has no trap and doesn't restore focus on close, which makes it unusable by
keyboard even though the automated scan is clean.

Every modal, drawer and overlay: focus moves in on open, **is trapped while open**, Escape closes,
**focus returns to the trigger** on close, `aria-modal`, background inert. Then do the manual pass axe
can't: **unplug the mouse and operate the whole app by keyboard**, including opening and closing the
assistant on mobile width. Record it in `A11Y_AUDIT.md`.

### 1d. Verify the a11y work reaches the public surfaces

`ChartCard` lives in `DashboardWidgets.jsx`, which renders **both** the editor and the public read-only
view. Confirm the chart aria-labels and the **View as table** toggle work on `/share/[t]` and `/demo` —
those are the surfaces strangers actually see, so that's where the accessibility matters most. Confirm
too that no editor-only control leaked into `SharedView` (the recurring hazard).

---

# PHASE 2 — The portfolio landing (the headline unfinished ask)

Built on Phase 1's primitives. This page serves **two audiences at once**: someone who might use the
product, and someone evaluating the owner as an engineer. It must serve both without reading as a résumé.

### 2a. The sections, in order

1. **Hero.** A stranger knows what this is within five seconds. The headline carries the idea of *change*
   — the thing Power BI doesn't do. Keep and extend the living-monitor replay.
2. **The problem.** Dashboards tell you what happened; nobody tells you what *changed*. Plain language.
3. **Who it's for** — concrete, not adjectives: a solo founder watching MRR and churn; an analyst with no
   BI budget; a researcher tracking a topic across their data *and* the live web; a small team needing a
   shared, always-current view.
4. **How you use it** — an animated sequence: connect data → build a dashboard → pin the questions that
   matter → one click keeps numbers and the live web in sync and tells you what moved.
5. **What you can do** — the capability showcase, animated: instant dashboards from any CSV, 9 chart
   types, plain-English questions with *computed* answers, the AI research council, share links,
   PDF/HTML export, threshold alerts.
6. **How it's built** — *the portfolio section.* An architecture diagram (browser → Vercel/Next proxy →
   FastAPI → JSON store), the stack, and the decisions worth explaining: the LLM only ever emits specs
   while charts and numbers are computed deterministically; numeric grounding so the assistant can't
   state a figure it can't defend; BYO API keys; a multi-model council with anonymous peer review; no
   database, by design. **Write it as engineering reasoning, not a feature list** — that's what makes it
   read as a portfolio piece rather than marketing.
7. **Try it** — the `/demo` CTA. No sign-up, no key.
8. **Pricing, plainly** — free; bring your own AI key and pay the provider directly. **Name the real
   per-run cost.** Vagueness about money reads as a trap.
9. **FAQ.**
10. **Footer** — ⭐ Star on GitHub, isaxcode.com, legal links, IdeaRadar. (Already built — keep it.)

**No fake social proof.** No invented logos or testimonials. Product proof only: the live demo, a real
share link, "no card, no key to start."

### 2b. Animation, without paying for it in SEO

- **Server-render the end state; animate after hydration.** Animation that gates first paint hurts
  **LCP**, which is both a ranking signal and a real experience.
- **Reserve space for every animated element** — unreserved space is the classic cause of **CLS**.
- CSS transforms and opacity only. No new animation library.
- **`prefers-reduced-motion` renders the final state immediately.** Non-negotiable — a WCAG requirement,
  not a preference.
- Animation carries meaning (a number ticking, a delta flipping, a source arriving) or it doesn't ship.

---

# PHASE 3 — Finish the screens

The primary screens are done. Sweep the rest at **390 / 768 / 1440**: `/chat/[id]`, `/share/[t]`,
`/admin`, sign-in, sign-up, 404, 500. Screenshot each; fix alignment, spacing, overflow; empty, loading
and error states present everywhere.

**Commit visual snapshots** per route × breakpoint and diff them in CI, alongside the axe scans. This is
what stops the alignment drifting the next time anything changes.

---

# PHASE 4 — SEO and legal accuracy

### 4a. SEO completion

`Person` and `BreadcrumbList` JSON-LD shipped with `/about`. Finish:

- **Per-route metadata** — unique title, description, canonical and OG image for `/`, `/about`, `/demo`,
  `/privacy`, `/terms`. Duplicate titles are the most common self-inflicted SEO wound.
- **`HowTo` JSON-LD** on the workflow section; keep `SoftwareApplication` and `FAQPage`.
- One `<h1>` per page with correct heading order; descriptive alt text; internal links between landing ↔
  about ↔ demo; new routes in the sitemap; app/admin/share stay `noindex`.
- **Core Web Vitals measured, not assumed** — LCP, CLS, INP on the landing at mobile width. Fix what's
  red. The new animation makes this a real risk, not a formality.

### 4b. Legal pages must be true

Night 2 added first-party analytics with an `anon_id` cookie and a funnel event stream. **The current
privacy policy predates that and doesn't describe it.** State plainly: what's collected; first-party
only, no third-party trackers; what is *never* logged (dataset contents and cell values are excluded
from events by design); that BYO API keys are encrypted at rest; retention; how to request deletion.
Provide an analytics opt-out. Specific and honest beats long and generic.

### 4c. A public accessibility statement

`A11Y_AUDIT.md` is gitignored working notes. For an open-source, portfolio-facing project, a short
public **`ACCESSIBILITY.md`** (or a README section) stating the conformance target (WCAG 2.2 AA), what's
been verified, and the known gaps is genuinely valuable — and stating gaps honestly reads better than
silence.

---

# PHASE 5 — Deploy verification

### 5a. Production-shaped boot

`docker compose` builds both with prod env: `PROXY_SHARED_SECRET`, `SECRET_KEY`, `ALLOWED_ORIGINS`
locked, real Clerk keys, `NEXT_PUBLIC_BACKEND_ORIGIN` pointing the frontend at the backend as a
**separate origin** (the real Vercel↔AWS shape). `vercel.json` roots at `frontend`; standalone only
under `DOCKER_BUILD=1`; `/health` green; CORS preflight passes from the app origin, refused from unknown.

### 5b. `make verify-deploy`

One command, pass/fail per line: `/health` · the `%2f` trio · a >5MB direct upload · a full pipeline ·
mint and revoke a share · `/admin` rejects a bad password · **the Clerk ownership walk (0b)**.

### 5c. Two drills

- **`SECRET_KEY` travels with `data/`:** correct key → boots and decrypts; a fresh key against the same
  `data/` → refuses to boot with the explicit error. Both directions, in the runbook.
- **Single replica:** pin replica/worker = 1 in deploy config and write that line in the runbook.

### 5d. The runbook

`DEPLOY_RUNBOOK.md` updated to the final tag: Clerk prod instance + domain; secrets set identically
where they must match; **`data/` on a persisted volume with `SECRET_KEY` alongside**; **the backup cron
installed BEFORE announcing** — `data/` is the only copy, no hosted database is holding a backup, so a
dead disk means every user's dashboards are gone; DNS + TLS; Chromium in the backend image;
`make verify-deploy` against the live host; then open the door.

---

# PHASE 6 — Ship

Full suite green; **CI green on GitHub with a URL**; axe clean; Core Web Vitals measured; screenshots
saved. Tag **`v1.1.0-golive`** — its definition requires the CI URL, so don't tag without it. `HANDOFF.md`:
the verdict, the tag, the CI URL, the deploy sequence, and what remains.

---

# Still not tonight

**The Postgres migration and other backend work.** It overturns the JSON invariant the entire security
model leans on — SSRF guard, atomic writes, per-conversation locks, encrypted keys, the single-replica
assumption. It's cleanly contained (everything funnels through `backend/storage.py` and the `u_<hex>`
id), so it deserves its own session with a schema, a migration script against the live `data/`, a
cutover and rollback strategy, and a parity harness proving nothing was lost.

---

## Definition of done

- **CI green on GitHub, URL in `HANDOFF.md`** — the one item gating DEPLOY.
- **Live two-account Clerk walk done with screenshots**, and the chatbot verified under real auth.
- Layout primitives and component kit complete; **focus trapped and restored in every overlay, keyboard
  pass done**; chart a11y confirmed on `/share` and `/demo`.
- **The landing explains what it is, who it's for, how you use it, what you can do, and how it was
  built** — built on the primitives, animated without hurting LCP/CLS.
- Secondary screens swept at 3 breakpoints; visual snapshots committed and in CI.
- Per-route metadata, `HowTo` JSON-LD, Core Web Vitals measured; privacy policy accurate about the
  analytics cookie; public `ACCESSIBILITY.md`.
- `make verify-deploy` passes against a production-shaped boot; runbook ends in a human go-live sequence
  with the backup cron before announce.
- **`v1.1.0-golive` tagged.**
- Storage still JSON; no new runtime dependencies.