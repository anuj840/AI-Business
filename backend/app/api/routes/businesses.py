"""Business + pipeline API routes.

Vertical-slice scope (spec section 73/74):

  POST /api/businesses            create a business record
  GET  /api/businesses            list businesses
  GET  /api/businesses/{id}       fetch one
  POST /api/businesses/{id}/analyze   run the full crawl->score->audit->outreach pipeline synchronously
  GET  /api/businesses/{id}/analysis  fetch the persisted result of the last /analyze run

Note: this pipeline runs synchronously in-request for the vertical slice.
Once Redis/worker infra (spec section 39) is introduced, this endpoint will
be changed to enqueue a job and return {"job_id", "status": "queued"} per
spec section 39 without changing the pipeline logic itself.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger
from app.models.business import (
    Audit,
    Business,
    LeadScore,
    Opportunity,
    OpportunityType,
    OutreachDraft,
    Website,
    WebsiteAnalysis,
)
from app.schemas.business import BusinessCreate, BusinessOut, PipelineResultOut
from app.services.pipeline import run_full_pipeline

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
        }
        if outreach_draft
        else None,
    )


@router.post("/{business_id}/analyze", response_model=PipelineResultOut)
async def analyze_business(business_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    business = await db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    try:
        result = await run_full_pipeline(business)
    except Exception as exc:  # noqa: BLE001
        logger.error("pipeline.unhandled_error", business_id=str(business_id), error=str(exc))
        raise HTTPException(status_code=500, detail="Analysis pipeline failed unexpectedly") from exc

    await _persist_pipeline_result(db, business, result)

    return PipelineResultOut(
        business=BusinessOut.model_validate(business),
        website_status=result["website_status"].value,
        pages_crawled=result["pages_crawled"],
        facts=result["facts"],
        quality_score=result["quality_score"],
        opportunity={
            **result["opportunity"],
            "type": result["opportunity"]["type"].value
            if isinstance(result["opportunity"]["type"], OpportunityType)
            else result["opportunity"]["type"],
        },
        lead_score=result["lead_score"],
        audit=result["audit"],
        outreach_draft=result["outreach_draft"],
    )


async def _persist_pipeline_result(db: AsyncSession, business: Business, result: dict) -> None:
    """Upserts Website/WebsiteAnalysis/LeadScore/Opportunity/Audit/OutreachDraft
    for this business. Wrapped in one transaction so a partial failure never
    leaves inconsistent half-written state (spec section 66)."""

    existing_website = await db.scalar(select(Website).where(Website.business_id == business.id))
    website = existing_website or Website(business_id=business.id)
    website.url = business.submitted_website_url
    website.status = result["website_status"]
    website.pages_crawled = result["pages_crawled"]
    website.crawl_data = result["crawl_data"]
    db.add(website)
    await db.flush()

    existing_analysis = await db.scalar(
        select(WebsiteAnalysis).where(WebsiteAnalysis.website_id == website.id)
    )
    analysis = existing_analysis or WebsiteAnalysis(website_id=website.id)
    analysis.facts = result["facts"]
    db.add(analysis)

    existing_score = await db.scalar(select(LeadScore).where(LeadScore.business_id == business.id))
    lead_score = existing_score or LeadScore(business_id=business.id)
    lead_score.overall_score = result["lead_score"]["overall"]
    lead_score.category_scores = result["quality_score"].get("categories", {})
    lead_score.reasons = result["lead_score"]["reasons"]
    db.add(lead_score)

    existing_opportunity = await db.scalar(
        select(Opportunity).where(Opportunity.business_id == business.id)
    )
    opportunity = existing_opportunity or Opportunity(business_id=business.id)
    opportunity.opportunity_type = result["opportunity"]["type"]
    opportunity.confidence = result["opportunity"]["confidence"]
    opportunity.reasons = result["opportunity"]["reasons"]
    opportunity.recommended_service = result["opportunity"]["recommended_service"]
    db.add(opportunity)

    existing_audit = await db.scalar(select(Audit).where(Audit.business_id == business.id))
    audit = existing_audit or Audit(business_id=business.id)
    audit.report = result["audit"]
    audit.ai_model = result["audit"].get("ai_model")
    db.add(audit)

    if result["outreach_draft"]:
        existing_draft = await db.scalar(
            select(OutreachDraft).where(OutreachDraft.business_id == business.id)
        )
        draft = existing_draft or OutreachDraft(business_id=business.id)
        draft.subject = result["outreach_draft"]["subject"]
        draft.body = result["outreach_draft"]["body"]
        draft.ai_model = result["outreach_draft"].get("ai_model")
        draft.approved = False  # always requires human approval (spec section 29)
        db.add(draft)

    await db.commit()
