"""Basic analytics (spec section 36) and a "hot deals" worklist.

Scope note: this reports on what we actually collect today --
discovery/analysis/scoring/outreach-draft state. The spec's full funnel
(Discovery -> Contacted -> Reply -> Interested -> Demo -> Trial -> Paid)
needs campaigns and reply-tracking, which don't exist yet (spec section
16/27); this is the honest subset buildable on top of the current schema,
and the "hot deals" view is the direct, actionable answer to "which leads
should I work today" using only data already collected -- no new source
required.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import (
    Business,
    LeadScore,
    Opportunity,
    OpportunityType,
    OutreachDraft,
    Website,
)
from app.models.job import Job, JobStatus
from app.services.scoring.lead_score import priority_label


async def get_analytics_summary(db: AsyncSession) -> dict:
    total_businesses = await db.scalar(select(func.count(Business.id)))

    analyzed_count = await db.scalar(select(func.count(Opportunity.id)))
    not_analyzed = (total_businesses or 0) - (analyzed_count or 0)

    website_status_rows = await db.execute(
        select(Website.status, func.count(Website.id)).group_by(Website.status)
    )
    website_status_breakdown = {row[0].value: row[1] for row in website_status_rows}

    opportunity_rows = await db.execute(
        select(Opportunity.opportunity_type, func.count(Opportunity.id)).group_by(
            Opportunity.opportunity_type
        )
    )
    opportunity_breakdown = {row[0].value: row[1] for row in opportunity_rows}

    reachable_count = await db.scalar(
        select(func.count(Business.id)).where(
            (Business.phone.is_not(None)) | (Business.email.is_not(None))
        )
    )

    # Build the coalesce expression once and reuse the same object in both
    # SELECT and GROUP BY -- two separate func.coalesce(...) calls compile
    # to two distinct bound parameters even with an identical literal,
    # which Postgres then refuses to recognize as the same grouping
    # expression (GroupingError), even though they're semantically equal.
    source_expr = func.coalesce(Business.source_name, "manual")
    source_rows = await db.execute(select(source_expr, func.count(Business.id)).group_by(source_expr))
    source_breakdown = {row[0]: row[1] for row in source_rows}

    total_drafts = await db.scalar(select(func.count(OutreachDraft.id)))
    approved_drafts = await db.scalar(
        select(func.count(OutreachDraft.id)).where(OutreachDraft.approved.is_(True))
    )

    # Priority tiers computed in Python (small dataset; priority_label is a
    # pure function over a score, no need for a SQL CASE expression here).
    score_rows = await db.execute(select(LeadScore.overall_score))
    tier_breakdown = {"HIGH_PRIORITY": 0, "GOOD": 0, "MEDIUM": 0, "LOW": 0}
    for (score,) in score_rows:
        tier_breakdown[priority_label(score)] += 1

    jobs_running = await db.scalar(
        select(func.count(Job.id)).where(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
    )
    jobs_failed = await db.scalar(select(func.count(Job.id)).where(Job.status == JobStatus.FAILED))

    return {
        "total_businesses": total_businesses or 0,
        "analyzed": analyzed_count or 0,
        "not_analyzed": not_analyzed,
        "reachable": reachable_count or 0,
        "website_status_breakdown": website_status_breakdown,
        "opportunity_breakdown": opportunity_breakdown,
        "priority_tier_breakdown": tier_breakdown,
        "source_breakdown": source_breakdown,
        "outreach_drafts_total": total_drafts or 0,
        "outreach_drafts_approved": approved_drafts or 0,
        "jobs_in_progress": jobs_running or 0,
        "jobs_failed": jobs_failed or 0,
    }


async def get_hot_deals(db: AsyncSession, limit: int = 20) -> list[dict]:
    """The leads most worth working right now: real opportunity (not
    IGNORE), a lead score on file, reachable by phone or email, and not
    already approved for outreach (i.e. still actionable) -- sorted by
    lead score descending."""
    stmt = (
        select(Business, LeadScore, Opportunity, OutreachDraft, Website.domain_age_years)
        .join(LeadScore, LeadScore.business_id == Business.id)
        .join(Opportunity, Opportunity.business_id == Business.id)
        .outerjoin(OutreachDraft, OutreachDraft.business_id == Business.id)
        .outerjoin(Website, Website.business_id == Business.id)
        .where(Opportunity.opportunity_type != OpportunityType.IGNORE)
        .where((Business.phone.is_not(None)) | (Business.email.is_not(None)))
        .where((OutreachDraft.approved.is_(False)) | (OutreachDraft.id.is_(None)))
        .order_by(LeadScore.overall_score.desc())
        .limit(limit)
    )
    rows = await db.execute(stmt)

    deals = []
    for business, lead_score, opportunity, draft, domain_age_years in rows.all():
        deals.append(
            {
                "business_id": str(business.id),
                "name": business.name,
                "city": business.city,
                "region": business.region,
                "phone": business.phone,
                "email": business.email,
                "domain_age_years": domain_age_years,
                "lead_score": lead_score.overall_score,
                "priority": priority_label(lead_score.overall_score),
                "opportunity_type": opportunity.opportunity_type.value,
                "recommended_service": opportunity.recommended_service,
                "has_outreach_draft": draft is not None,
                "outreach_approved": bool(draft.approved) if draft else False,
            }
        )
    return deals
