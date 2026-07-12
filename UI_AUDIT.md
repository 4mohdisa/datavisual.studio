# UI / layout audit

Automated sweep of http://localhost:3100 at 390 / 768 / 1440px. Screenshots in `artifacts/ui/`.

## studio @ 390px  (`/studio`)
- 24 interactive elements below the 44px tap-target guideline

## dashboard @ 390px  (`/dashboard/8a573c86-8fed-44ee-b718-f85c1c777f8d`)
- 53 interactive elements below the 44px tap-target guideline

## share @ 390px  (`/share/dGtz8-wi8urc`)
- 6 interactive elements below the 44px tap-target guideline

---

## Resolution (Phase 4)

- **No true horizontal page overflow at any width** — the earlier "past edge" counts were content
  inside `overflow-x:auto` containers (wide tables, Plotly charts) that scrolls by design; the audit
  now excludes those. The `text-wrap` / container-width ban is satisfied.
- **Studio/chat are now mobile-usable** — the 280px sidebar became an off-canvas slide-over below `md`
  (hamburger + backdrop); the main column is full-width. Previously the hero text wrapped one word
  per line.
- **Real states added:** `app/not-found.js` (branded 404), `app/error.js` (route error boundary with
  retry), `app/global-error.js` (fatal fallback). Empty states already exist (Home flow cards,
  dashboard empty message); loading skeletons exist (`ui/Skeleton`, Dashboard/Sidebar).
- **Remaining (accepted):** sub-44px tap targets in the dense sidebar and dashboard editor. These are
  icon buttons in a desktop-first data tool; enlarging them all would mean re-theming the dense UI
  (out of scope, Hard Rule 10). The sidebar's are off-canvas on mobile. The full dashboard *editor*
  (assistant panel + wide charts) stays desktop-first; the read-only /share view is the mobile surface.
