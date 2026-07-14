# datavisual.studio — Overnight Plan 3

**Tonight you build almost nothing. You prove what exists, and you fix what's lying.**

Nights 1 and 2 built and hardened the backend to 258 passing tests. In five minutes of real use the
owner found five bugs — **every one of them a frontend-runtime bug that pytest structurally cannot
see.** The e2e suite was skipped on Night 2 because port 3000 was busy, and the work shipped anyway.

That is the whole problem. Fix the cause, not just the five symptoms.

Execute in order. Never skip. Never ask. Commit and push after each phase.

---

## The bug that outranks everything

Real transcript, on the sample dataset:

> **User:** What is the total MRR across all rows?
> **Assistant:** The total MRR across all rows is 480506, as indicated by the 'mrr_sum' column.
>
> **User:** how much weekly I am making
> **Assistant:** Based on the `mrr_sum` of 480506, your weekly earnings are 480506.

Both answers are wrong, and the second is dangerous.

- The dataset is **18 rows = 6 months × 3 plans**. MRR is *monthly recurring revenue* — a **stock**,
  not a flow. Summing it across six months **counts the same recurring revenue six times.** Actual
  current MRR is roughly **$91k**. The tool said **$480,506**.
- Then it took that number, attached the word "weekly", performed **no conversion whatsoever**, and
  restated it. There is no reading of that sentence which is true.

**A data product that confidently reports wrong numbers is worse than no data product.** This is not a
quality issue to tune later. It is the product being broken. Phase 0.

## Hard rules

Runtime dependencies: **still zero**. **Dev/test dependencies are now sanctioned** — Vitest,
`@testing-library/react`, `@axe-core/playwright`. They never reach a user's browser, and the
alternative is continuing to ship a frontend nobody has ever tested. Everything else from
`OVERNIGHT_PLAN_2.md` still binds: no database, LLM emits specs only, owner keys never spent on a
user's request, strict public allowlist, no `%2f` interpolation, all frontend calls via `lib/api.js`,
port 8001, Plotly only via `LazyPlot.jsx`, don't touch `prediction_engine.py`, `main` only, no force
pushes.

## Operating rules

- **Never ask. Never wait.** Ambiguous → smallest reversible option → `DECISIONS.md` → keep going.
- **`main` deployable at every commit.** Abort rule: two honest attempts, commit what's green, move on.
- **Reading code is not verification.** Last night's agent verified with pytest and missed every bug the
  owner found in five minutes. **If a phase touches the UI, you prove it in a real browser and you save
  a screenshot as evidence.** No screenshot, no green tick.
- `HANDOFF.md` opens with `DEPLOY` or `DO NOT DEPLOY`.

---

# PHASE 0 — The assistant must never state a number it cannot defend

Five fixes. All of them are about the same thing: **the engine executes literally, and then the model
narrates freely.** Close both gaps.

### 0a. Numeric grounding — no number in an answer that isn't in the result

A hard, testable check, in code, not in a prompt:

- Extract every number from the model's answer.
- **Each one must either appear in the executed result table, or be the output of an arithmetic
  derivation the answer explicitly shows** ("MRR is monthly; weekly ≈ 91,204 ÷ 4.33 = 21,063").
- Any number that fails this check → **fail closed.** Re-ask once with the violation named; if it fails
  again, show the result table and say the answer couldn't be phrased safely.
- **"Your weekly earnings are 480506" fails this check trivially** — 480506 is a monthly-sum figure
  being reported as a weekly one with no derivation shown. That single rule catches the worst bug.

### 0b. Column semantics — stocks, flows, and ratios are not the same thing

The engine happily summed a stock across time. It must know better.

On ingestion, classify every column: **identifier · category · timestamp · flow** (additive: sales,
units, count, revenue-in-period) · **stock** (non-additive across time: MRR, ARR, headcount, balance,
inventory, price, customers) · **ratio** (non-additive at all: %, rate, average, per-unit).

Infer from name heuristics **and** data shape — a measure that stays roughly stable per entity across
consecutive periods is a stock, not a flow.

Then **guard the aggregation**:

| Aggregation | Column kind | Behaviour |
|---|---|---|
| `SUM` across a time dimension | **stock** | **Block or warn loudly.** "Summing MRR across 6 months counts the same recurring revenue six times. Current MRR (Jun 2026) is $91,204. The raw sum is $480,506." |
| `MEAN` | **ratio** | Warn — averaging averages is wrong without weights |
| `SUM` | **ratio** | Block |

This is not defensive plumbing. **It is the single most differentiating thing in the plan** — most BI
tools will happily sum your MRR across time and hand you a garbage number. Do it right and say so.

### 0c. Time-series awareness

The engine has a time column and did not use it. When a dataset has a time dimension and the user asks
for a "total" of a **stock** measure, the correct default is **the latest period**, not the sum — and
the answer must say which it used and why.

### 0d. Refuse rather than invent

"How much weekly am I making" requires a unit conversion that isn't in the data. The engine must either:

1. **do it explicitly and show the arithmetic**, or
2. **say it can't be answered from this data.**

**It must never restate an existing number under a new unit.** Add a golden test for exactly this
question and exactly this failure.

### 0e. Show the working — the fix for trust

Under every answer, render the **executed query spec** (filter · group-by · aggregation · rows used)
and the **result table** it was phrased from — collapsed by default, one click to open.

If the user could have seen `SUM(mrr) over 18 rows = 480,506` they would have caught the error
instantly. **Transparency is the feature.** It also makes "Pin this as a metric" honest, because they
can see what they're pinning.

### 0f. Honest status messages

The UI says **"Updating dashboard…"** while *answering a question*. It's not updating anything. The
intent router already knows the difference — the UI just ignores it.

Drive the copy from the intent: `question` → "Reading the data… / Computing…" · `edit` → "Updating
dashboard…" · `both` → "Updating the dashboard and answering…" · `add_insight` → "Searching the web…".

More broadly: **a spinner that describes the wrong action is worse than no spinner.** Every async
action in the app gets an honest, specific status message. Audit them all.

### 0g. Golden question set

~20 questions against the sample dataset with **known-correct, hand-computed answers**, including:
"what is the total MRR" · "how much am I making weekly" · "which plan grew fastest" · "what's the
average revenue per customer" · "how many customers in June" · plus questions the data **cannot**
answer, where the correct behaviour is a refusal.

Run against a real model. **If any answer is wrong, Phase 0 is not done.**

---

# PHASE 1 — Export is broken

Reported: the button gives no feedback, and the PDF comes out **white, with only some components on it**.

### 1a. The two likely causes — check these first

1. **White PDF:** Chrome's `--print-to-pdf` **strips background colours by default**. Without
   `print-color-adjust: exact` / `-webkit-print-color-adjust: exact`, your dark theme renders as white
   paper. That is almost certainly the entire bug.
2. **Missing components:** **Plotly renders client-side.** If the export HTML is printed before the JS
   executes — or the JS never runs in the print pipeline at all — the charts are simply blank. You
   already have **kaleido** as a dependency *for exactly this purpose*: server-side chart PNGs.

### 1b. Decide: the export is a light, print-designed document

The current design is "one dark structured layout" for both screen and export. **That's a mistake.** A
dark PDF wastes ink, looks broken when printed, and reads as a bug to anyone who opens it. An export
is not a screenshot of your app — it's a document.

**Exports become light and print-designed.** Say so in `DECISIONS.md`.

### 1c. Render charts server-side

Every chart → a **kaleido PNG**, embedded. Never rely on client-side Plotly in a print context.

### 1d. Export the whole thing

Title · generated-at timestamp · the data summary · **every widget** (charts as PNG, metrics as styled
figures, tables as real tables, text notes) · the research report and its **cited sources** if present ·
a footer. "Some components" is not an export.

### 1e. Export needs a state machine

It takes seconds — it spawns Chrome and renders images. Silence is a bug.

`idle → generating (real, specific progress) → download` — plus a genuine **error state**. The user must
never again wonder whether the button did anything.

### 1f. Prove it

Both formats. Assert the generated PDF has more than one page, contains every widget title, and is not
blank. **Open it and look at it.** Save it as evidence.

---

# PHASE 2 — The scroll bug, and the class of bug it belongs to

Reported: the share / report view **doesn't scroll**, so content below the fold is unreachable.

### 2a. Fix it

**Most likely cause:** a flex child without `min-h-0`. A flex item defaults to `min-height: auto`, which
refuses to shrink below its content, so the inner `overflow-y-auto` never activates and the content is
simply cut off. The other usual suspect is `h-screen` + `overflow-hidden` on a wrapper.

### 2b. Then kill the whole class

This is not a one-off. Add a Playwright check across **every route × 390/768/1440 × short and tall
viewport heights**: scroll to the bottom, assert the **last element is reachable and visible**, and
assert nothing is clipped by an ancestor's overflow. A page you cannot reach the bottom of is broken,
and you should find that out from CI, not from your user.

---

# PHASE 3 — Feature audit: drive every feature in a real browser

Produce **`FEATURE_AUDIT.md`** — a matrix, filled in by *using the app*, with a screenshot behind every
row.

| Feature | Works? | Loading state | Error state | Empty state | Mobile 390 | Tested |
|---|---|---|---|---|---|---|

Cover every one, and fix everything red:

- **Instant dashboards** — metric cards; **all 9 chart types actually rendered and eyeballed** (line,
  bar, scatter, histogram, pie, box, heatmap, area, treemap — some of these have almost certainly never
  been looked at); entity comparison (2-metric **and** 3+-metric radar); the data table (search, sort,
  paginate, **CSV download after the injection fix**); text notes.
- **Assistant** — question, edit, both; the component gallery; form editors; reorder; inline rename.
- **Deep research** — full run, report render, follow-up questions, sources.
- **Sync / living monitor** — **what happens when you click Update on a dashboard built from an
  uploaded file with no connector?** Nobody has ever tried. It must degrade honestly, not error.
- **Connectors** — a real SQL DB and a real REST endpoint, end to end. **Critical regression check: did
  Night 2's SSRF guard break legitimate connectors?** A developer testing against a local database is
  now blocked by design. Make sure the *error message says so* instead of failing mysteriously.
- **Exports** — PDF and HTML (Phase 1).
- **Share** — mint, open in a clean incognito context, scroll it, revoke, confirm it 404s.
- **`/demo`** — anonymous, no key, and **it scrolls** (same bug class as Phase 2).
- **Onboarding** — brand-new user, empty state, sample data, first dashboard.
- **Account** — key modal, validate button, key masked on reload.
- **Admin** — renders, with the new events flowing.
- **Auth with Clerk ON.** **Almost all testing to date has been in open dev mode.** The entire
  ownership model, the proxy identity plumbing, and per-user key scoping have never been exercised
  through a real browser session with real Clerk keys. This is the largest untested surface in the
  product.
- **Error paths** — backend down, no API key, bad CSV, rate-limited. Each must produce a clear message,
  **never a white screen**.

---

# PHASE 4 — The frontend test net (the thing whose absence caused all of this)

### 4a. Fix the harness before you write a single test

`make e2e` was skipped on Night 2 because **port 3000 was occupied by another app.** A test suite that
can't run because an unrelated program is using a port is not a test suite. Bind to a configurable or
ephemeral port. **This excuse does not survive tonight.**

### 4b. Then build it

- **Component tests** (Vitest + RTL) for `components/ui/` and every widget renderer: props → render,
  every state (hover, focus, disabled, loading, error, empty).
- **E2E** (Playwright) for **every row of the Phase 3 matrix**, with the LLM stubbed at the network
  layer so it's fast and deterministic — plus one un-stubbed smoke run per night against a real model.
- **Visual regression** — snapshots per route × breakpoint, committed and diffed.
- **Accessibility** — axe on every route, zero critical violations.
- **The failure journeys nobody writes:** backend down · no key · bad file · rate-limited · a share link
  that was revoked · an export that fails.
- **Wire all of it into CI.** A test that doesn't run on every push is documentation.

**Definition of done for this phase: every bug the owner found in five minutes is now caught by a test
that fails without the fix.** Write those five tests first, watch them fail, then confirm the fixes.

---

# PHASE 5 — Answer quality, once answers are correct

Correctness first (Phase 0), then this:

- **Shorter, plainer answers.** Lead with the number and its unit. No preamble.
- **Never cite an internal column name** at the user. The real answer said *"as indicated by the
  'mrr_sum' column"* — `mrr_sum` is an aggregate the engine invented, not something in their file. It
  reads like a leak, because it is one.
- **Offer the next step**: pin it, chart it, or ask the obvious follow-up.
- **Suggested questions generated from the actual columns**, not generic placeholders.
- Say what was assumed: *"I read 'total' as the latest month, since MRR is recurring."*

---

# PHASE 6 — Resume `OVERNIGHT_PLAN_2.md`

Only once Phases 0–5 are green. Pick up at its Phase 2 remainder (LLM cassettes, silent-drop detection,
ownership matrix, concurrency), then **Phase 3 theme tokens → Phase 4 landing/onboarding/admin → Phase
5 analytical depth → Phase 6 living monitor → Phase 7 research → Phase 8 customisation.**

Note: Phase 0b (column semantics) is the foundation for that plan's **significance-aware deltas**. You
are building the same thing from both ends. Keep them consistent.

---

## Definition of done

- **The golden question set passes against a real model.** No wrong numbers. No invented units.
- A PDF export that is **complete, legible, and not blank** — opened and looked at.
- Every route scrolls to its own bottom, at every breakpoint, proven in CI.
- `FEATURE_AUDIT.md` complete, with a screenshot behind every row and **nothing left red**.
- `make e2e` **runs** — no port excuses — and covers every feature in the matrix.
- **The five bugs the owner found each have a test that fails without the fix.**
- CI green. `HANDOFF.md` opens with `DEPLOY` or `DO NOT DEPLOY`.
- Runtime dependencies: still zero.