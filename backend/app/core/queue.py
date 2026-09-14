"""Lazily-initialized ARQ connection pool, shared across requests.

A single pool is created on first use and reused -- creating a new Redis
connection pool per request would be wasteful and is unnecessary since arq's
pool is safe for concurrent use.
"""
from __future__ import annotations

import asyncio

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings

_pool: ArqRedis | None = None
_lock = asyncio.Lock()


async def get_arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        async with _lock:
            if _pool is None:
                settings = get_settings()
                _pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _pool
