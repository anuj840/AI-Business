"""Business + pipeline API routes.

  POST /api/businesses            create a business record (auto-runs a quick
                                   contact check if a website is given but no
                                   phone/email is)
  GET  /api/businesses            list businesses
  GET  /api/businesses/{id}       fetch one
  POST /api/businesses/{id}/find-contact  fast (~seconds) phone/email-only
                                   check, no AI -- see CONTACT.md
  POST /api/businesses/{id}/analyze   enqueue the full pipeline as a background job (spec section 39)
  GET  /api/businesses/{id}/analysis  fetch the persisted result of the last completed run
  PATCH /api/businesses/{id}/status   update the deal status (spec section 27, scoped down --
                                   see DealStatus's docstring for why this is manual)
  POST  /api/businesses/{id}/activity  log a timeline note, optionally with a status change
  GET   /api/businesses/{id}/activity  fetch the timeline, newest first

/analyze returns {"job_id", "status": "queued"} immediately -- the actual
crawl/AI work runs in the ARQ worker process (app/worker/), not this
request. Poll GET /api/jobs/{job_id} for status, then GET .../analysis once
it's COMPLETED.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger
from app.core.queue import get_arq_pool
from app.models.business import (
    Audit,
    Business,
    DealActivity,
    DealStatus,
    LeadScore,
    Opportunity,
    OutreachDraft,
    Website,
    WebsiteAnalysis,
)
from app.models.job import Job, JobType
from app.schemas.business import (
    BusinessCreate,
    BusinessListItemOut,
    BusinessOut,
    DealActivityCreate,
    DealActivityOut,
    DealStatusUpdate,
    PaginatedBusinessesOut,
    PipelineResultOut,
)
from app.services.contact.finder import quick_contact_check

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

    # Auto contact check: fast (a few seconds), so it's fine to await inline
    # rather than requiring a separate job. Never blocks creation on failure.
    if business.submitted_website_url and not (business.phone and business.email):
        try:
            found = await quick_contact_check(business.submitted_website_url)
            if found["reachable"]:
                business.phone = business.phone or found["phone"]
                business.email = business.email or found["email"]
                db.add(business)
                await db.commit()
                await db.refresh(business)
        except Exception as exc:  # noqa: BLE001 - never fail business creation over this
            logger.warning("business.auto_contact_check_failed", error=str(exc))

    return business


@router.post("/{business_id}/find-contact")
async def find_contact(business_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Fast (~seconds), AI-free phone/email-only check -- see CONTACT.md.
    Updates the business's phone/email if not already set; never overwrites
    an existing value (same rule as the full pipeline's backfill)."""
    business = await db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    if not business.submitted_website_url:
        raise HTTPException(
            status_code=400,
            detail="This business has no website URL, so there's nothing to check.",
        )

    found = await quick_contact_check(business.submitted_website_url)

    updated = False
    if not business.phone and found["phone"]:
        business.phone = found["phone"]
        updated = True
    if not business.email and found["email"]:
        business.email = found["email"]
        updated = True
    if updated:
        db.add(business)
        await db.commit()
        await db.refresh(business)

    return {
        "phone": business.phone,
        "email": business.email,
        "reachable": found["reachable"],
        "pages_checked": found["pages_checked"],
        "updated": updated,
    }


@router.get("", response_model=PaginatedBusinessesOut)
async def list_businesses(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    total = await db.scalar(select(func.count(Business.id))) or 0
    total_pages = max(1, (total + page_size - 1) // page_size)

    rows = await db.execute(
        select(Business, Website.domain_age_years)
        .outerjoin(Website, Website.business_id == Business.id)
        .order_by(Business.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        BusinessListItemOut.model_validate(business, from_attributes=True).model_copy(
            update={"domain_age_years": domain_age_years}
        )
        for business, domain_age_years in rows.all()
    ]
    return PaginatedBusinessesOut(
        items=items, total=total, page=page, page_size=page_size, total_pages=total_pages
    )


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


@router.patch("/{business_id}/status", response_model=BusinessOut)
async def update_deal_status(
    business_id: uuid.UUID, payload: DealStatusUpdate, db: AsyncSession = Depends(get_db)
):
    business = await db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    try:
        new_status = DealStatus(payload.status)
    except ValueError:
        valid = ", ".join(s.value for s in DealStatus)
        raise HTTPException(
            status_code=422, detail=f"Invalid status {payload.status!r}. Valid values: {valid}"
        ) from None

    business.deal_status = new_status
    business.deal_status_updated_at = datetime.now(timezone.utc)
    db.add(business)

    # The status change itself is worth a timeline entry even without an
    # accompanying note, so the activity feed is a complete record of every
    # status transition, not just the ones a human happened to annotate.
    db.add(DealActivity(business_id=business.id, status=new_status, note=None))

    await db.commit()
    await db.refresh(business)
    return business


@router.post("/{business_id}/activity", response_model=DealActivityOut, status_code=201)
async def add_deal_activity(
    business_id: uuid.UUID, payload: DealActivityCreate, db: AsyncSession = Depends(get_db)
):
    business = await db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    new_status = None
    if payload.status is not None:
        try:
            new_status = DealStatus(payload.status)
        except ValueError:
            valid = ", ".join(s.value for s in DealStatus)
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status {payload.status!r}. Valid values: {valid}",
            ) from None
        business.deal_status = new_status
        business.deal_status_updated_at = datetime.now(timezone.utc)
        db.add(business)

    if not payload.note and new_status is None:
        raise HTTPException(status_code=422, detail="Provide a note, a status, or both.")

    activity = DealActivity(business_id=business.id, status=new_status, note=payload.note)
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity


@router.get("/{business_id}/activity", response_model=list[DealActivityOut])
async def list_deal_activity(business_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    business = await db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    rows = await db.execute(
        select(DealActivity)
        .where(DealActivity.business_id == business_id)
        .order_by(DealActivity.created_at.desc())
    )
    return rows.scalars().all()
