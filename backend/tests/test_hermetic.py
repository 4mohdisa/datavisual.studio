"""The guard that keeps the suite hermetic (conftest.hermetic_no_outbound).

If either of these fails, some test could quietly reach the real internet — a
live model call would depend on whatever the repo-root `.env` happens to hold.
"""
import httpx
import pytest

import backend.openrouter as openrouter


async def test_query_model_is_stubbed_to_none():
    """No test reaches a real model — query_model returns the no-key path."""
    assert await openrouter.query_model("any/model", [{"role": "user", "content": "hi"}]) is None


async def test_raw_outbound_post_fails_loudly():
    """Any path that bypasses query_model and POSTs for real raises, not silently
    hits the network (e.g. a naive key-validate call)."""
    with pytest.raises(RuntimeError, match="HERMETIC"):
        async with httpx.AsyncClient() as c:
            await c.post("https://openrouter.ai/api/v1/chat/completions", json={})
