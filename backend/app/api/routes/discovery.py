"""Lead discovery API (spec sections 6-9).

  POST /api/discovery/run   discover businesses matching criteria, persist
                             new (deduplicated) ones, return the batch

This does not run the analysis pipeline on the results -- see each
business's own /analyze endpoint (or run it per-business from the
dashboard) once you've reviewed which discovered leads are worth spending
AI/crawl time on.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger
from app.schemas.discovery import DiscoveryRequest, DiscoveryResultOut
from app.services.discovery.provider import DiscoveryCriteria
from app.services.discovery.service import run_discovery

logger = get_logger(__name__)
router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.post("/run", response_model=DiscoveryResultOut)
async def discover_businesses(payload: DiscoveryRequest, db: AsyncSession = Depends(get_db)):
    criteria = DiscoveryCriteria(
        country=payload.country,
        region=payload.region,
        city=payload.city,
        industry=payload.industry,
        max_results=payload.max_results,
    )

    try:
        result = await run_discovery(db, criteria)
    except Exception as exc:  # noqa: BLE001
        logger.error("discovery.unhandled_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Discovery failed unexpectedly") from exc

    return result
