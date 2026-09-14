"""FastAPI application entrypoint."""
from __future__ import annotations

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import analytics, businesses, discovery, jobs, outreach
from app.core.config import get_settings
from app.core.db import engine
from app.core.logging import configure_logging, get_logger
from app.core.queue import get_arq_pool

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(businesses.router)
app.include_router(outreach.router)
app.include_router(discovery.router)
app.include_router(jobs.router)
app.include_router(analytics.router)


@app.get("/health")
async def health():
    """Liveness check — process is up. No dependency checks here."""
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Readiness check — verifies critical dependencies (spec section 55)."""
    checks = {"database": False, "ollama": False, "redis": False}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ready.database_check_failed", error=str(exc))

    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            checks["ollama"] = resp.status_code == 200
    except Exception as exc:  # noqa: BLE001
        logger.warning("ready.ollama_check_failed", error=str(exc))

    try:
        pool = await get_arq_pool()
        await pool.ping()
        checks["redis"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ready.redis_check_failed", error=str(exc))

    all_ok = all(checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}
