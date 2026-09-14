"""Business + pipeline API routes.

  POST /api/businesses            create a business record
  GET  /api/businesses            list businesses
  GET  /api/businesses/{id}       fetch one
  POST /api/businesses/{id}/analyze   enqueue the pipeline as a background job (spec section 39)
  GET  /api/businesses/{id}/analysis  fetch the persisted result of the last completed run

/analyze returns {"job_id", "status": "queued"} immediately -- the actual
crawl/AI work runs in the ARQ worker process (app/worker/), not this
request. Poll GET /api/jobs/{job_id} for status, then GET .../analysis once
it's COMPLETED.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger
from app.core.queue import get_arq_pool
from app.models.business import (
    Audit,
    Business,
    LeadScore,
    Opportunity,
    OutreachDraft,
    Website,
    WebsiteAnalysis,
)
from app.models.job import Job, JobType
from app.schemas.business import BusinessCreate, BusinessOut, PipelineResultOut

logger = get_logger(__name__)
router = APIRouter(prefix="/api/businesses", tags=["businesses"])


@router.post("", response_model=BusinessOut, status_code=201)
async def create_business(payload: BusinessCreate, db: AsyncSession = Depends(get_db)):
    business = Business(
        name=payload.name,
        submitted_website_url=payload.website_url,
        country=payload.country,
        region=payload.region,
        city=payload.city,
        industry=payload.industry,
        phone=payload.phone,
        email=payload.email,
        notes=payload.notes,
    )
    db.add(business)
    await db.commit()
    await db.refresh(business)
    return business


@router.get("", response_model=list[BusinessOut])
async def list_businesses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Business).order_by(Business.created_at.desc()))
    return result.scalars().all()


@router.get("/{business_id}", response_model=BusinessOut)
async def get_business(business_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    business = await db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


@router.get("/{business_id}/analysis", response_model=PipelineResultOut)
async def get_analysis(business_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Returns the persisted result of the last /analyze run, without
    re-running the pipeline. 404 if /analyze has never been run for this
    business."""
    business = await db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    website = await db.scalar(select(Website).where(Website.business_id == business.id))
    opportunity = await db.scalar(select(Opportunity).where(Opportunity.business_id == business.id))
    lead_score = await db.scalar(select(LeadScore).where(LeadScore.business_id == business.id))
    audit = await db.scalar(select(Audit).where(Audit.business_id == business.id))

    if not (website and opportunity and lead_score and audit):
        raise HTTPException(
            status_code=404,
            detail="No analysis found for this business yet. Run POST /analyze first.",
        )

    analysis = await db.scalar(
        select(WebsiteAnalysis).where(WebsiteAnalysis.website_id == website.id)
    )
    outreach_draft = await db.scalar(
        select(OutreachDraft).where(OutreachDraft.business_id == business.id)
    )

    return PipelineResultOut(
        business=BusinessOut.model_validate(business),
        website_status=website.status.value,
        pages_crawled=website.pages_crawled,
        facts=analysis.facts if analysis else {},
        quality_score={
            "overall": audit.report.get("website_score", 0),
            "categories": audit.report.get("category_scores", {}),
            "reasons": [],
        },
        opportunity={
            "type": opportunity.opportunity_type.value,
            "confidence": opportunity.confidence,
            "reasons": opportunity.reasons,
            "recommended_service": opportunity.recommended_service,
        },
        lead_score={"overall": lead_score.overall_score, "reasons": lead_score.reasons},
        audit=audit.report,
        outreach_draft={
            "subject": outreach_draft.subject,
            "body": outreach_draft.body,
            "ai_generation_succeeded": True,
            "ai_model": outreach_draft.ai_model,
            "requires_human_approval": not outreach_draft.approved,
            "has_contact_channel": bool(business.phone or business.email),
        }
        if outreach_draft
        else None,
    )


@router.post("/{business_id}/analyze", status_code=202)
async def analyze_business(business_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Enqueues the pipeline as a background job and returns immediately
    (spec section 39) -- the crawl/AI work happens in the worker process,
    not this request."""
    business = await db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    job = Job(
        job_type=JobType.ANALYZE_BUSINESS,
        business_id=business.id,
        job_metadata={"business_name": business.name},
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    try:
        pool = await get_arq_pool()
        await pool.enqueue_job(
            "analyze_business_task", str(job.id), str(business.id), _job_id=str(job.id)
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("analyze.enqueue_failed", business_id=str(business_id), error=str(exc))
        raise HTTPException(
            status_code=503, detail="Could not queue analysis job — is Redis running?"
        ) from exc

    return {"job_id": str(job.id), "status": job.status.value}
