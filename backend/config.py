"""Configuration for Datavisual.studio."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Verbose diagnostic logging. Gated behind an env var so normal runs are silent;
# enable with:  DATAVISUAL_DEBUG=true uv run python -m backend.main
# Single source of truth — imported by main, prediction_engine, research, council,
# report_builder so every diagnostic print honours the same switch.
DEBUG = os.getenv("DATAVISUAL_DEBUG", "").lower() == "true"

# Council members - list of OpenRouter model identifiers.
# NOTE: "x-ai/grok-4" and "google/gemini-3-pro-preview" were removed — neither id
# exists on OpenRouter, which is why they "failed silently" (the request 404'd and
# the model never appeared in the council). "anthropic/claude-opus-4.8" was also
# tried but returns 402 Payment Required on this account (too costly), so it's
# replaced with "google/gemini-2.5-pro" (verified 200 + provider diversity).
# Verify any new id against https://openrouter.ai/api/v1/models before adding it.
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "anthropic/claude-sonnet-4.5",
    "openai/gpt-4o",
    "google/gemini-2.5-pro",
]

# Chairman model - synthesizes final response.
# Sonnet handles conflicting evidence more faithfully than GPT-5.1, which was
# overriding confirmed live internet evidence with its training knowledge.
CHAIRMAN_MODEL = "anthropic/claude-sonnet-4-5"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
