# Datavisual.studio — Backend

FastAPI backend for the Datavisual.studio prediction platform.

## Stack
- Python 3.10+, FastAPI, uvicorn
- pandas, scipy, plotly, xgboost
- OpenRouter API (all models via one key)
- WeasyPrint for PDF generation (HTML fallback when unavailable)
- uv package manager

## Setup
  cp .env.example .env       # add OPENROUTER_API_KEY
  uv sync
  uv run python -m backend.main    # port 8001

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

## Endpoints
  POST /api/conversations/create
  POST /api/upload
  POST /api/analyse          (SSE stream)
  POST /api/reanalyse
  GET  /api/conversations/{id}
  GET  /api/conversations/{id}/status
  GET  /api/export/{id}
