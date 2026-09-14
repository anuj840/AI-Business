"""Basic analytics API (spec section 36).

  GET /api/analytics/summary     funnel/breakdown counts
  GET /api/analytics/hot-deals   the leads most worth working right now
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.analytics.service import get_analytics_summary, get_hot_deals

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
async def analytics_summary(db: AsyncSession = Depends(get_db)):
    return await get_analytics_summary(db)


@router.get("/hot-deals")
async def hot_deals(limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    return await get_hot_deals(db, limit=limit)
