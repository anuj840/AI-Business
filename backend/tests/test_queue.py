"""Unit test for the lazy ARQ pool singleton (app/core/queue.py).

Full enqueue/worker behavior is verified live against a real Redis + worker
process (no test-DB fixture exists in this repo yet for a DB-backed
integration test) -- see DEPLOYMENT.md / TESTING notes.
"""
from unittest.mock import AsyncMock, patch

import app.core.queue as queue_module


async def test_get_arq_pool_returns_singleton():
    queue_module._pool = None  # reset any state from other tests/imports

    fake_pool = AsyncMock()
    with patch.object(queue_module, "create_pool", AsyncMock(return_value=fake_pool)) as mock_create:
        pool1 = await queue_module.get_arq_pool()
        pool2 = await queue_module.get_arq_pool()

    assert pool1 is pool2
    mock_create.assert_awaited_once()

    queue_module._pool = None  # don't leak state into other tests
