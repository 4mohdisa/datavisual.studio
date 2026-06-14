# Datavisual.studio — Frontend

React 19 + Vite + Tailwind CSS frontend for the
Datavisual.studio prediction platform.

## Stack
- React 19, React Router v7, Vite
- Tailwind CSS v3
- react-plotly.js for interactive charts
- lucide-react for icons

## Dev
  npm install
  npm run dev      # http://localhost:5173
  npm run build    # production build
  npm run lint     # ESLint

## Key components
- App.jsx — routing, SSE stream handler, conversation state
- Report.jsx — orchestrates all report sections
- PredictionSuite.jsx — Model A/B/C cards + ensemble
- CombinedPrediction.jsx — weighted prediction table
- ActivityPanel.jsx — live research reasoning timeline
- Charts.jsx — Plotly chart renderer
