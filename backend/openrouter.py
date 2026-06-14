"""OpenRouter API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    max_tokens: int = 4000,
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
        max_tokens: Cap on completion tokens. IMPORTANT: without this, OpenRouter
            reserves credit for each model's *maximum possible* output (tens of
            thousands of tokens for some providers). On a low-balance account that
            reserve can exceed the balance and the request fails with
            402 Payment Required — which is exactly why some council models
            (e.g. Anthropic) failed intermittently while cheaper ones succeeded.
            An explicit cap keeps the reserve small and the responses bounded.

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )

            # Low-balance handling: OpenRouter reserves credit for max_tokens up
            # front and returns 402 "...can only afford N" when the balance can't
            # cover it. Parse N and retry once at that smaller cap so the request
            # still succeeds (with a shorter answer) instead of failing outright.
            if response.status_code == 402:
                import re
                m = re.search(r"can only afford (\d+)", response.text)
                if m:
                    affordable = int(m.group(1))
                    new_max = max(256, affordable - 100)
                    if new_max < payload["max_tokens"]:
                        print(
                            f"[openrouter] {model}: 402 low balance — retrying with "
                            f"max_tokens={new_max} (was {payload['max_tokens']})",
                            flush=True,
                        )
                        payload["max_tokens"] = new_max
                        response = await client.post(
                            OPENROUTER_API_URL, headers=headers, json=payload
                        )

            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details'),
                # Perplexity/Sonar return web citations here — either as
                # message.annotations (url_citation objects) or a top-level
                # citations[] of URL strings. Pass both through so research.py
                # can surface real source URLs.
                'annotations': message.get('annotations'),
                'citations': data.get('citations'),
            }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}
