"""Configuration for Datavisual.studio.

User-editable settings (OpenRouter API key, council/chairman/research models)
live in data/settings.json and are managed from the frontend Settings UI via
/api/settings. Environment variables (.env) act as a fallback so existing
setups keep working. Everything else here is static.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Verbose diagnostic logging. Gated behind an env var so normal runs are silent;
# enable with:  DATAVISUAL_DEBUG=true uv run python -m backend.main
DEBUG = os.getenv("DATAVISUAL_DEBUG", "").lower() == "true"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

SETTINGS_PATH = Path("data/settings.json")

# Defaults — used until the user saves their own settings.
# NOTE: verify any new model id against https://openrouter.ai/api/v1/models
# before adding it; invalid ids 404 and the model silently drops out of the
# council. "anthropic/claude-opus-4.8" returns 402 on low-balance accounts.
DEFAULT_COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "anthropic/claude-sonnet-4.5",
    "openai/gpt-4o",
    "google/gemini-2.5-pro",
]

# Chairman synthesizes the final answer. Sonnet handles conflicting evidence
# more faithfully than GPT-5.1, which was overriding confirmed live internet
# evidence with its training knowledge.
DEFAULT_CHAIRMAN_MODEL = "anthropic/claude-sonnet-4-5"

# Online/search model used by the research layer.
DEFAULT_RESEARCH_MODEL = "perplexity/sonar-pro"

# Cheap, fast model for high-frequency utility calls (dashboard assistant
# edits, title generation, prediction extraction). Gemini Flash goes through
# the direct Google API when GEMINI_API_KEY is set — near-free.
DEFAULT_FAST_MODEL = "google/gemini-2.5-flash"


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text())
    except Exception:
        return {}


_settings = _load_settings()


def save_settings(patch: dict) -> None:
    """Merge non-None fields into data/settings.json and the in-memory copy."""
    from .atomic import atomic_write_json
    _settings.update({k: v for k, v in patch.items() if v is not None})
    atomic_write_json(SETTINGS_PATH, _settings)


def _ctx_user():
    # Imported lazily to avoid a config↔users import cycle at module load.
    from .users import current_user_ctx
    return current_user_ctx.get()


def get_api_key() -> str | None:
    """OpenRouter key. With a signed-in identity, ONLY that user's own key is
    used — the platform owner's key is never spent on users' requests. Open
    mode (no identity, local dev) falls back to settings.json / env."""
    user = _ctx_user()
    if user is not None:
        from .crypto import decrypt
        return decrypt((user.get("settings") or {}).get("openrouter_api_key")) or None
    return _settings.get("openrouter_api_key") or os.getenv("OPENROUTER_API_KEY")


def get_council_models() -> list[str]:
    return _settings.get("council_models") or DEFAULT_COUNCIL_MODELS


def get_chairman_model() -> str:
    return _settings.get("chairman_model") or DEFAULT_CHAIRMAN_MODEL


def get_research_model() -> str:
    return _settings.get("research_model") or DEFAULT_RESEARCH_MODEL


def get_fast_model() -> str:
    return _settings.get("fast_model") or DEFAULT_FAST_MODEL


def get_gemini_api_key() -> str | None:
    """Gemini key — same per-user policy as get_api_key."""
    user = _ctx_user()
    if user is not None:
        from .crypto import decrypt
        return decrypt((user.get("settings") or {}).get("gemini_api_key")) or None
    return _settings.get("gemini_api_key") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def get_settings_view() -> dict:
    """Settings as shown to the frontend — the API key is never sent back in
    full, only a masked hint so the user can tell which key is active."""
    key = get_api_key() or ""
    masked = f"{key[:10]}…{key[-4:]}" if len(key) > 18 else ("•" * len(key))
    return {
        "api_key_set": bool(key),
        "api_key_masked": masked,
        "api_key_source": "settings" if _settings.get("openrouter_api_key") else ("env" if key else None),
        "council_models": get_council_models(),
        "chairman_model": get_chairman_model(),
        "research_model": get_research_model(),
        "default_council_models": DEFAULT_COUNCIL_MODELS,
        "default_chairman_model": DEFAULT_CHAIRMAN_MODEL,
        "default_research_model": DEFAULT_RESEARCH_MODEL,
    }
