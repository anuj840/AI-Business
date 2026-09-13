"""Regression test for a real bug found during manual end-to-end testing:
httpx's `timeout=` kwarg is a per-operation (e.g. per-read) timeout, not a
ceiling on total request duration. Ollama's non-streaming response only
arrives after generation fully completes, and a small/rambling model can
occasionally run for minutes without tripping a per-read timeout -- so a
90s "timeout" was observed taking 280+ seconds in practice. Fixed by
wrapping the call in asyncio.wait_for for a real hard deadline.
"""
import asyncio
import time

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.services.ai.ollama_provider import OllamaProvider


@pytest.mark.asyncio
async def test_generate_respects_hard_timeout_even_if_response_eventually_arrives():
    get_settings.cache_clear()
    provider = OllamaProvider()
    provider.timeout_seconds = 1
    provider.max_retries = 0

    async def slow_response(request):
        # Simulate Ollama taking far longer than the configured timeout to
        # finish generating before it ever sends a response.
        await asyncio.sleep(5)
        return httpx.Response(200, json={"message": {"content": "too late"}})

    # assert_all_called=False: asyncio.wait_for cancels the in-flight mock
    # handler before it returns, which is exactly the behavior under test.
    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{provider.base_url}/api/chat").mock(side_effect=slow_response)

        start = time.monotonic()
        response = await provider.generate(system_prompt="sys", user_prompt="hello")
        elapsed = time.monotonic() - start

    assert response.succeeded is False
    assert elapsed < 4, f"expected the call to be cut off near the 1s timeout, took {elapsed:.1f}s"
