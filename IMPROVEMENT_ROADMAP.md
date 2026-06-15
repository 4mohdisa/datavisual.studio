# 🚀 Datavisual.studio — Overnight Improvement Roadmap

> **Instructions for Claude Code:** Read this file completely before writing a single line of code. Work through each phase in order. Complete every task in a phase before moving to the next. Run `npm run build` and `uv run python -c "import backend.main"` after every phase to confirm nothing broke. Report what was completed at the end of each phase before proceeding.

---

## PHASE 1 — UI POLISH AND LAYOUT FIXES

### 1.1 — Sidebar Improvements
- [ ] Add a search/filter input at the top of the conversation list — filters conversations by title in real time, no backend call needed
- [ ] Group conversations by date: Today, Yesterday, Last 7 days, Older — insert a small muted label before each group
- [ ] Show a loading skeleton while conversations load instead of a blank sidebar
- [ ] Conversation rows: truncate long titles with ellipsis at 28 chars (currently wrapping)
- [ ] On hover, the three-dot menu should appear with a smooth opacity transition (200ms), not instantly

### 1.2 — Chat Layout
- [ ] The floating input bar currently sits at the same depth as all content. Add a subtle `backdrop-blur` behind it so content scrolling underneath is slightly blurred, not fully visible
- [ ] Messages container: add a subtle top fade (gradient from `oklch(0.12)` to transparent, 60px) so messages appear to fade in from above, giving depth
- [ ] User message timestamp: show it in muted text below the message bubble, formatted as "2:34 PM" — only visible on hover

### 1.3 — Report Section Improvements
- [ ] Each collapsible section header should show a subtle count badge in muted text: e.g. "Council Opinions (4 models)", "Visualisations (3 charts)", "Internet Research (15 sources)"
- [ ] The "How we got here" section is collapsed by default — that is correct. But add a small preview subtitle under the collapsed header: "5 explanation charts — weight breakdown, source comparison, ELO trajectory, breakdown table"
- [ ] Prediction section: add a small "Computed at HH:MM" timestamp in muted text below the prediction table header

### 1.4 — Loading and Progress States
- [ ] Replace the text stage labels in AnalysisProgress.jsx with a cleaner timeline: a vertical line on the left, circle node per stage, stage label on the right. Active node pulses. Completed nodes are filled.
- [ ] Add a subtle shimmer skeleton to the Dataset Overview section while data loads instead of showing empty section boxes
- [ ] When the council is running, show a small animated bar under each model tab label indicating it is being queried

### 1.5 — Activity Panel
- [ ] Activity panel: when it first opens, animate the items in from the bottom one by one with 60ms stagger between each item
- [ ] Sources tab: group sources by domain (all espn.com sources together, all bbc.com together). Show the domain as a section header with a count badge
- [ ] Activity panel: add a "Copy all sources" button at the top of the Sources tab that copies all source URLs to clipboard as a formatted list

### 1.6 — Model Cards in Prediction Suite
- [ ] Model A and B cards: add a small sparkline-style mini bar chart at the bottom of each card showing the probability distribution of the top 5 entities as tiny horizontal bars — gives a visual summary without needing to read the numbers
- [ ] Model agreement dot: currently only in the ensemble row. Also add it to the comparison chart as a coloured band behind each group of bars — green band = high agreement, red band = low agreement
- [ ] Model C placeholder card: add an animated dashed border (CSS animation, 2s cycle) to make it look more like a live widget waiting for data rather than a static placeholder

### 1.7 — Typography and Spacing
- [ ] Audit all font sizes. Currently mixing 11pt, 12pt, 13pt, 14pt. Standardise to a 4-step scale: 12px (muted/meta), 14px (body), 16px (section labels), 20px (headings)
- [ ] All table cells: ensure consistent 12px vertical padding, 16px horizontal padding
- [ ] Comparison tables: the "—" placeholder for missing data should be styled in a distinct muted colour `oklch(0.35)` so it is clearly different from real data

---

## PHASE 2 — PREDICTION ENGINE IMPROVEMENTS

### 2.1 — Bracket Seeding (Critical)
- [ ] The current bracket simulation uses random shuffling. Add ELO-based seeding for the group stage. In a real 48-team World Cup, teams are seeded based on ranking — top teams are separated into different groups to avoid early elimination of favourites
- [ ] Implement proper pot-based seeding: divide teams into 4 pots by ELO rating. Teams from the same pot cannot be in the same group. This makes the simulation dramatically more accurate
- [ ] Add a `seeding` config option: `seeded` (pot-based), `random` (current), `historical` (use actual 2026 draw if available)

### 2.2 — Home Advantage Factor
- [ ] Detect if the dataset has an `is_host` column or if any entity is identified as the host nation in the internet research
- [ ] Apply a home advantage ELO boost of +65 ELO points to the host nation in all match simulations — this is the empirically derived value used in most academic ELO football models
- [ ] Surface this in the UI: add a 🏠 icon next to the host nation in the prediction table and a note "Host advantage applied (+65 ELO)"

### 2.3 — Confidence Interval Improvements
- [ ] Current confidence intervals are a flat ±1.5%. Replace with statistically derived intervals based on how consistent the Monte Carlo simulation was
- [ ] Calculate the standard deviation of wins across all 10,000 simulations per entity. Use 1 standard deviation as the confidence range instead of the flat ±1.5%
- [ ] Entities where Model A and Model B agree closely (agreement > 0.85) get a narrower interval. Entities with high disagreement get a wider interval. This makes the confidence signal meaningful

### 2.4 — Form Index Refinement
- [ ] The current form index uses equal weight for wins/losses/draws. Add a result quality weighting: a win against a high-ELO opponent is worth more than a win against a low-ELO opponent
- [ ] Formula: `quality_win = (1 + 0.5 * (opponent_elo / max_elo)) * win_weight`
- [ ] Only apply quality weighting if the dataset has enough data to determine opponent ELO for historical matches

### 2.5 — Prediction Stability Check
- [ ] After running 10,000 simulations, run an additional 1,000 as a validation set and compare the results. If the top entity's probability differs by more than 3 percentage points between the two runs, increase n_simulations to 20,000 automatically and re-run
- [ ] Add to the activity log: "Prediction validated — stable within 0.8% across validation run" or "Increased to 20,000 simulations for stability"

### 2.6 — XGBoost Improvements (when match history CSV is available)
- [ ] Add early stopping to XGBoost training: use 20% of matches as validation set, stop training when validation loss stops improving for 10 rounds
- [ ] Add feature importance extraction: after training, extract which features mattered most and display them in the Model C card: "Top features: ELO difference (38%), recent form (24%), goals scored avg (18%)..."
- [ ] Cache the trained XGBoost model to disk as `data/models/{hash_of_training_data}.pkl` so reloading the same match history CSV skips retraining

---

## PHASE 3 — INTERNET RESEARCH IMPROVEMENTS

### 3.1 — Better Query Construction
- [ ] Currently all three searches use the user's raw question. Add a query enricher that extracts the core topic and entities from the question before building search queries
- [ ] Example: "Which team will win the World Cup?" → extract topic: "FIFA World Cup 2026" + entities: ["Spain", "Argentina", "France", "England"]
- [ ] Use the extracted entities in targeted searches: "Spain Argentina France England World Cup 2026 probability odds" rather than the full user question

### 3.2 — Source Quality Scoring
- [ ] After Perplexity returns sources, score each source by domain authority. Create a priority list: `["fifa.com", "espn.com", "bbc.com", "reuters.com", "apnews.com", "skysports.com", "theguardian.com"]` = high authority, anything else = standard
- [ ] In the Sources tab, show a small coloured badge: 🟢 Authoritative, 🟡 Standard, 🔴 Unknown
- [ ] Weight the internet_probability extraction by source quality — percentages from authoritative sources count 2x

### 3.3 — Research Deduplication
- [ ] Currently the three searches can return the same finding in different phrasing. Add a semantic deduplication step: if two findings say roughly the same thing (same entity + same percentage ± 2%), keep only the one from the higher-authority source
- [ ] Add to activity log: "Deduplicated 3 duplicate findings across searches"

### 3.4 — Live Score Detection
- [ ] Currently `extract_confirmed_facts` scans source titles for score patterns. Extend it to also scan the actual content of each Perplexity result for score patterns, not just the title
- [ ] If a live score is found in the content, extract: home_team, away_team, home_goals, away_goals, match_date
- [ ] Store extracted live scores in `pipeline.live_scores` in the conversation JSON
- [ ] Display confirmed live scores prominently at the top of the Internet Research section as a "Live Results" card with score chips: `Spain 🆚 Germany — 2:1 ✅`

### 3.5 — Research Summary
- [ ] Add a "Research Summary" block at the very top of the Internet Research section (before the detailed findings) showing: queries run, sources found, live scores detected, probability ranges found, and the as-of datetime
- [ ] Format: `3 searches · 28 sources · 2 live scores detected · Probability ranges found for 6 teams · As of June 14, 2026 at 3:47 PM`

---

## PHASE 4 — DATASET DASHBOARD

This is the biggest new feature. Add a dedicated `/dashboard/:conversationId` route that shows the uploaded dataset as an interactive dashboard rather than a chat report.

### 4.1 — Route Setup
- [ ] Add a new route `/dashboard/:id` in `main.jsx`
- [ ] Add a "View Dashboard" button to the Dataset Overview section in the report that navigates to `/dashboard/{conversationId}`
- [ ] Add a back arrow in the dashboard to return to `/chat/{conversationId}`

### 4.2 — Dashboard Layout
- [ ] Full-width layout, no sidebar (or collapsible sidebar)
- [ ] Dark theme consistent with the rest of the app
- [ ] Three-section layout: top metrics strip, main chart area, data table below

### 4.3 — Top Metrics Strip
- [ ] Automatically detect and display the 4 most relevant metrics from the dataset as stat cards:
  - For ELO datasets: highest current rating, lowest rating, most wins, largest rating range
  - For any dataset: max value, min value, mean, total unique entities
- [ ] Each card: metric label, large value, small change indicator if time column exists (e.g. "↑ 12 since 2020")

### 4.4 — Main Chart Area
- [ ] Show all auto-generated Plotly charts from the analysis in a responsive grid
- [ ] Allow user to toggle between charts using tab pills above the chart area
- [ ] Add a "Generate more charts" button that calls `/api/reanalyse` with no filters, just requests additional chart types the auto-detection might have missed:
  - Box plots for all numeric columns
  - Scatter matrix for top 5 correlated numeric columns
  - Animated bubble chart if time + two numeric + one categorical column detected

### 4.5 — Entity Comparison Tool
- [ ] Below the main charts, a comparison selector: user picks 2-6 entities from a dropdown (e.g. Spain, Argentina, France)
- [ ] Shows a radar chart comparing those entities across all key numeric dimensions (ELO, wins, goals, etc.)
- [ ] Shows a side-by-side stat card for each selected entity

### 4.6 — Data Table
- [ ] At the bottom of the dashboard: a full interactive data table
- [ ] Sortable by clicking column headers
- [ ] Searchable: a text input filters rows in real time
- [ ] Paginated: 25 rows per page with Next/Prev controls
- [ ] Download button: exports the current filtered/sorted view as a CSV

### 4.7 — Dashboard PDF Export
- [ ] Add an "Export Dashboard" button that calls `/api/export/{id}?mode=dashboard`
- [ ] The dashboard export should contain: metrics strip, all charts, entity comparison table, full data table
- [ ] Different layout from the report export — more visual, less text

---

## PHASE 5 — PERFORMANCE OPTIMISATIONS

### 5.1 — Frontend Bundle
- [ ] Run `npx vite-bundle-visualizer` and identify the largest modules
- [ ] Plotly.js is 5.2MB — implement dynamic import so it only loads when a chart is about to render: `const Plot = lazy(() => import('react-plotly.js'))`
- [ ] Wrap all `lazy()` components with `Suspense` with a skeleton fallback

### 5.2 — Backend Response Speed
- [ ] The data_analysis step runs synchronously before research begins. Move chart generation to run in a background thread using `asyncio.create_task` so chart JSON is computed while Perplexity searches are running in parallel
- [ ] Add response compression to all FastAPI endpoints: `from fastapi.middleware.gzip import GZipMiddleware` — this reduces SSE payload size significantly for large reports

### 5.3 — Conversation Load Speed
- [ ] When the app loads, fetch only conversation metadata (id, title, status, created_at, file attached) instead of full conversation JSON for the sidebar list
- [ ] Add a new endpoint `GET /api/conversations` that returns metadata only
- [ ] Only fetch the full conversation JSON when the user clicks on a specific conversation

### 5.4 — Chart Caching
- [ ] Currently charts are regenerated from the full dataset on every `/api/reanalyse` call with filters applied. Cache the base charts (no filters) in the conversation JSON and only recompute when filters actually change
- [ ] Add `chart_fingerprint` to the conversation JSON — if the filter state matches the last fingerprint, return cached charts immediately

---

## PHASE 6 — NEW FEATURES

### 6.1 — Comparative Analysis (Two Datasets)
- [ ] Allow attaching a second main dataset in addition to the match history CSV
- [ ] When two datasets are attached, offer a "Compare datasets" mode
- [ ] In compare mode, run prediction models on both datasets and show a side-by-side comparison of their top predictions
- [ ] Useful for: "How does the 2022 World Cup ELO compare to 2026 ELO predictions?"

### 6.2 — Custom Prediction Weights
- [ ] Add a settings panel (gear icon near the prediction section) that lets the user adjust the three weights: dataset %, internet %, council %
- [ ] Sliders: each slider adjusts one weight, the others auto-adjust to sum to 100%
- [ ] "Recalculate" button reruns the combination with new weights (no new API calls needed — just recombine the stored source probabilities)
- [ ] "Reset to defaults" restores 40/35/25

### 6.3 — Share Report
- [ ] Add a "Share" button to the report that generates a static snapshot of the current report as a self-contained HTML file
- [ ] The HTML file includes all charts as embedded base64 images (requires kaleido), the full report content, and the prediction table
- [ ] User downloads this HTML and can share it or host it anywhere — it has no dependencies

### 6.4 — Keyboard Shortcuts
- [ ] `Cmd/Ctrl + K` — opens a command palette (simple fuzzy search over conversation titles)
- [ ] `Cmd/Ctrl + N` — new conversation
- [ ] `Cmd/Ctrl + /` — toggle activity panel
- [ ] `Escape` — close any open modal, dropdown, or panel
- [ ] `Cmd/Ctrl + Enter` — submit message (alternative to clicking the send button)

### 6.5 — Anomaly Detection
- [ ] In the data analysis phase, after computing statistics, add a basic anomaly detection pass using IQR method (already used for quality notes)
- [ ] For each numeric column, flag rows where the value is more than 3 IQR from the median as anomalies
- [ ] Store anomalies in the data summary and show them in the Dataset Overview as a collapsible "Anomalies detected" section with the entity names and values
- [ ] Inject anomaly information into the council prompt: "Note: the following entities have anomalous values that may affect predictions: [list]"

---

## PHASE 7 — CODE QUALITY AND DOCUMENTATION

### 7.1 — Remove Remaining Debug Artifacts
- [ ] Search for all `console.log` calls in the frontend and remove or gate them behind a `localStorage.getItem('debug')` check
- [ ] Search for all hardcoded strings that should be constants and move them to a `frontend/src/constants.js` file
- [ ] Remove any commented-out code blocks older than this session

### 7.2 — Error Boundary
- [ ] Add a React ErrorBoundary component that wraps the entire app
- [ ] If any component throws an unhandled error, show a clean error screen: "Something went wrong. The error has been logged." with a "Reload" button
- [ ] Log the error to the backend via `POST /api/error-log` (simple file append, no database)

### 7.3 — Backend Type Hints
- [ ] Audit all Python functions in the backend for missing type hints
- [ ] Add type hints to all function signatures in `prediction_engine.py`, `data_analysis.py`, `research.py`, `report_builder.py`
- [ ] Run `uv run mypy backend/` and fix all type errors

### 7.4 — API Documentation
- [ ] FastAPI auto-generates OpenAPI docs at `/docs`. Ensure all endpoints have:
  - A docstring describing what the endpoint does
  - Response model types defined
  - Example request body in the docstring
- [ ] Add `title="Datavisual.studio API"`, `version="1.0.0"`, `description="Multi-model AI prediction platform API"` to the FastAPI constructor

---

## END OF PHASES — FINAL CHECKS

After completing all phases:

```bash
# Backend check
uv run python -c "import backend.main; print('Backend OK')"
uv run python -c "from backend.prediction_engine import build_dataset_models, run_monte_carlo_tournament, run_monte_carlo_poisson; print('Prediction engine OK')"

# Frontend check
npm run build
npm run lint

# Check bundle size
npx vite-bundle-visualizer 2>/dev/null || echo "Install with: npm install -D rollup-plugin-visualizer"

# Git commit everything
git add -A
git commit -m "feat: overnight improvements — UI polish, prediction engine, dashboard, performance

Phase 1: UI polish — sidebar search, chart sparklines, loading timeline, activity panel animations
Phase 2: Prediction — ELO seeding, home advantage, confidence intervals, stability check
Phase 3: Research — query enrichment, source quality scoring, live score extraction
Phase 4: Dashboard — /dashboard/:id route, metrics strip, entity comparison, data table
Phase 5: Performance — lazy Plotly, GZip, metadata-only sidebar load, chart caching
Phase 6: Features — comparative analysis, custom weights, share report, keyboard shortcuts, anomaly detection
Phase 7: Code quality — error boundary, type hints, API docs"

git push origin main
```

Report the full list of completed tasks from each phase with a ✅ or ❌ per task before pushing.
