"""Outreach draft approval endpoint.

Sending is out of scope for the vertical slice (no email infra yet, spec
section 28/58) — this endpoint only implements the human-approval gate
(spec section 29) so the data model and workflow are correct from day one.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.business import OutreachDraft

router = APIRouter(prefix="/api/businesses", tags=["outreach"])


@router.get("/{business_id}/outreach-draft")
async def get_outreach_draft(business_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    draft = await db.scalar(select(OutreachDraft).where(OutreachDraft.business_id == business_id))
    if not draft:
        raise HTTPException(status_code=404, detail="No outreach draft found. Run /analyze first.")
    return {
        "id": draft.id,
        "subject": draft.subject,
        "body": draft.body,
        "approved": draft.approved,
        "ai_model": draft.ai_model,
    }


@router.post("/{business_id}/outreach-draft/approve")
async def approve_outreach_draft(business_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    draft = await db.scalar(select(OutreachDraft).where(OutreachDraft.business_id == business_id))
    if not draft:
        raise HTTPException(status_code=404, detail="No outreach draft found. Run /analyze first.")
    draft.approved = True
    await db.commit()
    return {"id": draft.id, "approved": True}
