# Datavisual.studio

A multi-model AI research and prediction platform. Upload any dataset, ask any question, and receive a structured report where four leading AI models independently analyse your data alongside current internet research — then a chairman model synthesises a final answer.

Built by Mohammed Isa (mohdisa233@gmail.com)

## What it does

- Upload CSV, Excel, or JSON datasets
- The platform profiles your data, auto-generates interactive charts, and searches the internet for current context
- Four AI models (via OpenRouter) analyse everything independently and review each other's reasoning
- A chairman model produces a synthesised final answer
- Full report with comparison tables, source citations, and a live Activity Panel showing the pipeline in real time
- Follow-up questions answered by the chairman using the full session context

## Setup

### Requirements
- Python 3.10+
- Node.js 18+
- uv (Python package manager)
- An OpenRouter API key at openrouter.ai

### Installation

Backend:
```bash
uv sync
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env
```

Frontend:
```bash
cd frontend
npm install
```

### Running

Terminal 1 — backend:
```bash
uv run python -m backend.main
```

Terminal 2 — frontend:
```bash
cd frontend
npm run dev
```

Open http://localhost:5173

## PDF export

PDF export requires WeasyPrint system libraries.
- macOS:  `brew install pango cairo`
- Linux:  `apt-get install libpango-1.0-0 libcairo2`

Without these, export falls back to HTML automatically.

## Tech stack

- **Backend:** FastAPI, Python 3.10+, pandas, Plotly, WeasyPrint, OpenRouter API
- **Frontend:** React, Vite, Tailwind CSS, react-plotly.js

---

## 🔬 How Predictions Work — Example

**Upload:** `elo_ratings_wc2026.csv` (4,683 rows, 23 columns)
**Question:** *"Which team has the highest probability of winning the 2026 FIFA World Cup?"*

**Pipeline:**
1. pandas detects ELO rating column + country entity column + snapshot_date time column
2. Form index computed from wins/losses/draws weighted toward recent periods
3. Model A runs 10,000 bracket simulations → Spain 27.4%
4. Model B runs 10,000 Poisson simulations with Dixon-Coles → Spain 31.7%
5. Ensemble average → Spain 29.6%
6. Perplexity searches live results, odds, expert forecasts → extracts percentage values
7. All four council models receive dataset + predictions + research
8. Peer review weights model responses by ranking
9. Final: `(29.6% × 0.40) + (internet% × 0.35) + (council% × 0.25)` = final range
10. Chairman explains the numbers, cannot change them

---

## ⚙️ Environment Variables

```env
OPENROUTER_API_KEY=sk-or-v1-...     # Required
DATAVISUAL_DEBUG=false              # Optional: enable debug logging
CRON_SECRET=...                     # Optional: for future cron jobs
```

---

## 📄 License

MIT © [Mohammed Isa](https://github.com/4mohdisa)

---

*Built on top of [karpathy/llm-council](https://github.com/karpathy/llm-council) — extended with data analysis, internet research, a deterministic prediction engine, and a full React frontend.*
