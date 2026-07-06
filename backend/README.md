# Datavisual.studio — Backend

FastAPI backend for the Datavisual.studio prediction platform.

## Stack
- Python 3.10+, FastAPI, uvicorn
- pandas, scipy, plotly, xgboost
- OpenRouter API (all models via one key)
- WeasyPrint for PDF generation (HTML fallback when unavailable)
- uv package manager

## Setup
  uv sync
  uv run python -m backend.main    # port 8001

The OpenRouter API key and council/chairman/research models are set from the
frontend Settings UI (stored in data/settings.json); a .env with
OPENROUTER_API_KEY works as a fallback.

## Debug mode
  DATAVISUAL_DEBUG=true uv run python -m backend.main

## Key modules
- main.py — FastAPI endpoints + SSE analysis pipeline
- prediction_engine.py — ELO Monte Carlo, Poisson/Dixon-Coles, XGBoost
- council.py — 3-stage LLM council (independent → peer review → synthesis)
- research.py — 3 Perplexity searches + confirmed fact extraction
- data_analysis.py — pandas profiling + auto chart generation
- report_builder.py — enriched prompt assembly + report structure
- pdf_export.py — WeasyPrint PDF with embedded charts (HTML fallback)

## Multi-user (local)
Identity arrives as trusted headers from the Next.js proxy; backend/users.py
maps Clerk ids to internal `u_<hex>` ids in data/users.json and every
conversation is stamped/scoped by owner_id. Set PROXY_SHARED_SECRET (both
sides) when hosting the backend publicly.

## Endpoints
  GET  /api/settings
  POST /api/settings
  POST /api/settings/validate
  POST /api/conversations/create
  POST /api/upload
  POST /api/connect          (import from SQL database or REST API)
  POST /api/dashboard        (create or rebuild a dashboard widget spec)
  POST /api/dashboard/{id}/chat  (edit the dashboard in place via chat/ops)
  POST /api/dashboard/{id}/sync    (re-pull data + re-run pinned research, report changes)
  POST /api/analyse          (SSE stream)
  POST /api/reanalyse
  GET  /api/conversations
  GET  /api/conversations/{id}
  GET  /api/conversations/{id}/status
  GET  /api/dataset/{id}
  GET  /api/export/{id}
  GET  /api/export-format
