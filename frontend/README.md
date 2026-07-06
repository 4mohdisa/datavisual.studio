# Datavisual.studio — Frontend

Next.js 16 + custom UI components + Tailwind CSS frontend for the
Datavisual.studio prediction platform.

## Stack
- Next.js 16 (App Router), React 19
- Tailwind CSS v3 with a CSS-variable dark palette
- Custom UI primitives in components/ui (Button, Input, Field, Modal, Skeleton)
- react-plotly.js for interactive charts (client-only via next/dynamic)
- lucide-react for icons

## Dev
  npm install
  npm run dev      # http://localhost:3000
  npm run build    # production build

The backend must be running on port 8001 (override with NEXT_PUBLIC_API_BASE).

## Structure
- app/ — routes: / and /chat/[id] (AppShell), /dashboard/[id] (Dashboard)
- components/AppShell.jsx — conversation state, SSE stream handler, shortcuts
- components/Report.jsx — orchestrates all report sections
- components/PredictionSuite.jsx — Model A/B/C cards + ensemble
- components/ActivityPanel.jsx — live research reasoning timeline
- components/Settings.jsx — API key + model configuration modal
- components/ui/ — the custom component library
- lib/api.js — backend client (fetch + SSE)
