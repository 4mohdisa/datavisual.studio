"""Native Google Gemini API client.

OpenRouter adds a markup on every call; Google's own API is cheaper (and its
flash tier has a generous free quota). Any `google/gemini-*` model is routed
here automatically when GEMINI_API_KEY is configured — openrouter.query_model
is the single seam, so every feature (council, titles, dashboard assistant,
prediction extraction) benefits without call-site changes. On any failure the
caller falls back to OpenRouter, so a bad key or quota blip never breaks a run.
"""

import httpx
from typing import Any, Dict, List, Optional

from .config import DEBUG, get_gemini_api_key

_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def is_gemini_model(model: str) -> bool:
    name = (model or "").split("/")[-1]
    return name.startswith("gemini-")


def gemini_enabled(model: str) -> bool:
    return is_gemini_model(model) and bool(get_gemini_api_key())


def build_gemini_payload(messages: List[Dict[str, str]], max_tokens: int) -> dict:
    """Map OpenAI-style messages to Gemini's contents/systemInstruction shape."""
    system_parts = []
    contents = []
    for m in messages:
        role = m.get("role")
        text = m.get("content") or ""
        if role == "system":
            system_parts.append({"text": text})
        else:
            contents.append({
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": text}],
            })
    payload: dict = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": system_parts}
    return payload


async def query_gemini(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    max_tokens: int = 4000,
) -> Optional[Dict[str, Any]]:
    """Call Gemini directly. Returns the same shape as openrouter.query_model
    ({content, reasoning_details, annotations, citations}) or None on failure."""
    api_key = get_gemini_api_key()
    if not api_key:
        return None
    name = model.split("/")[-1]

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{_API_BASE}/{name}:generateContent",
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=build_gemini_payload(messages, max_tokens),
            )
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            if DEBUG:
                print(f"[gemini] {name}: no candidates ({data.get('promptFeedback')})", flush=True)
            return None
        parts = (candidates[0].get("content") or {}).get("parts") or []
        content = "".join(p.get("text", "") for p in parts)
        if not content.strip():
            return None
        return {
            "content": content,
            "reasoning_details": None,
            "annotations": None,
            "citations": None,
        }
    except Exception as e:
        print(f"[gemini] {model} direct call failed ({e}) — falling back to OpenRouter", flush=True)
        return None
