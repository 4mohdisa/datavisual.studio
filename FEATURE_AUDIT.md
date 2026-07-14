# Feature audit — driven in a real browser

Night 3 started this. A row is **green only when driven in a browser this session** (per the plan's
"reading code is not verification"). Rows marked _not driven_ are honest gaps for the next session, not
claims. Automated coverage (pytest/Vitest/Playwright) is noted separately from manual browser driving.

Legend: ✅ works (browser-verified) · 🧪 covered by an automated test · ⬜ not driven yet · — n/a

| Feature | Works? | Loading | Error | Empty | Mobile 390 | Tested |
|---|---|---|---|---|---|---|
| **Assistant — numeric answer** (total MRR) | ✅ 90,596, not 480,506 | ✅ "Reading the data…" (0f) | ✅ fail-closed safe answer | — | ⬜ | 🧪 `test_answer_correctness`, `test_golden_questions` |
| **Assistant — invented unit** (weekly) | ✅ refuses / converts | ✅ | ✅ | — | ⬜ | 🧪 |
| **Assistant — show the working** (0e) | ✅ spec + result + warning | — | — | — | ⬜ | manual |
| **Export — PDF** | ✅ 3-page light doc, all widgets | ✅ generating state | ✅ error→retry | — | — | 🧪 `test_export_document`, `ExportDashboardButton.test` |
| **Export — HTML** | ✅ light, charts embedded | ✅ | ✅ | — | — | 🧪 |
| **Share / demo view scroll** | ✅ reaches footer | — | ✅ "unavailable" | — | ✅ | 🧪 `scroll.spec` (route×breakpoint) |
| **/demo** (anon, no key) | ✅ renders + scrolls | ✅ | ✅ | — | ✅ | 🧪 e2e |
| **Landing + legal** | ✅ | — | — | — | ✅ | 🧪 `landing.spec` |
| **Instant dashboard** (metrics + line/bar/pie charts rendered) | ✅ eyeballed saas sample | ✅ | ⬜ | ⬜ | ⬜ | 🧪 upload→dashboard e2e |
| Upload → dashboard → share → public → revoke | 🧪 | — | — | — | — | 🧪 `dashboard-share.spec` |
| All 9 chart types eyeballed (scatter/histogram/box/heatmap/area/treemap) | ⬜ | | | | | ⬜ |
| Deep research — full run, report, sources | ⬜ (proven live Night 2) | | | | | ⬜ |
| Sync / living monitor (upload-only, no connector) | ⬜ | | | | | ⬜ |
| Connectors — real SQL + REST (incl. SSRF-guard error message) | ⬜ | | | | | ⬜ |
| Onboarding — new user empty state → sample → first dashboard | ⬜ | | | | | ⬜ |
| Account — key modal, validate, masked on reload | ⬜ | | | | | ⬜ |
| Admin — renders, events flowing | ⬜ | | | | | ⬜ |
| **Auth with Clerk ON** (ownership, per-user keys) | ⬜ **largest untested surface** | | | | | ⬜ |
| Error paths — backend down · no key · bad CSV · rate-limited | ⬜ (partly e2e) | | | | | ⬜ |

## Driven this session (with browser evidence)

- **Assistant correctness** — `/dashboard/[id]`: asked "total MRR" → *"90,596 on 2026-06-01; the sum
  (480,506) is misleading, as MRR is recurring"*, with Show-the-working exposing `sum(mrr)` + the stock
  warning. Asked "weekly" → refused (never restates a number under a new unit).
- **Export** — generated a real light 3-page PDF + HTML; opened the HTML: white document, metric cards,
  chart titles, embedded (now light) chart images, full data table.
- **Scroll** — `/demo` scrolls to its footer + full 18-row table (previously clipped); cross-route
  Playwright check green at 390/768/1440.

## Not driven yet (next session, in priority order)

1. **Auth with Clerk ON** — the entire ownership/identity/per-user-key surface has never been exercised
   through a real signed-in browser session. Largest risk.
2. The **9 chart types** individually eyeballed (several likely never looked at).
3. **Connectors** end-to-end + the SSRF-guard error message for a legit localhost DB (should say *why*).
4. **Sync on an upload-only dashboard** (no connector) — must degrade honestly, not error.
5. Admin panel, onboarding empty-state, account key modal, error-path white-screen checks.
