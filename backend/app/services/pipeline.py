"""Vertical-slice pipeline orchestrator.

DISCOVER -> VERIFY -> ANALYZE -> SCORE -> IDENTIFY OPPORTUNITY -> CREATE PROOF
(spec section 1), scoped here to a single business submitted with a name +
optional website URL (spec section 73). Discovery/campaigns/multi-tenant
come in later phases; this function is written so it can later be invoked
from a background worker instead of a request handler without changes.
"""
from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.business import (
    Audit,
    Business,
    LeadScore,
    Opportunity,
    OutreachDraft,
    Website,
    WebsiteAnalysis,
    WebsiteStatus,
)
from app.services.analysis.deterministic import analyze_crawl
from app.services.audit.generator import generate_audit
from app.services.crawler.playwright_crawler import WebsiteCrawler
from app.services.opportunity.classifier import classify_opportunity
from app.services.outreach.generator import generate_outreach_draft
from app.services.scoring.engine import score_website
from app.services.scoring.lead_score import calculate_lead_score

logger = get_logger(__name__)


def _location_str(business: Business) -> str:
    parts = [p for p in (business.city, business.region, business.country) if p]
    return ", ".join(parts) if parts else "Unknown"


async def run_full_pipeline(business: Business) -> dict:
    """Runs crawl -> analysis -> scoring -> classification -> audit -> outreach.

    Returns a dict with every intermediate result so the caller can persist
    each piece independently. Never raises for expected failure modes (site
    unreachable, AI unavailable) — those degrade the result, they don't
    abort the pipeline (spec section 66).
    """
    logger.info("pipeline.start", business_id=str(business.id), business_name=business.name)

    website_url = business.submitted_website_url

    if not website_url:
        website_status = WebsiteStatus.NO_WEBSITE_FOUND
        facts: dict = {"reachable": False}
        quality_score = {"overall": 0, "categories": {}, "reasons": []}
        crawl_data = None
        pages_crawled = 0
    else:
        crawler = WebsiteCrawler()
        crawl_result = await crawler.crawl(website_url)
        crawl_data = {
            "root_url": crawl_result.root_url,
            "reachable": crawl_result.reachable,
            "error": crawl_result.error,
            "pages": [
                {
                    "url": p.url,
                    "status": p.status,
                    "title": p.title,
                }
                for p in crawl_result.pages
            ],
        }
        pages_crawled = len(crawl_result.pages)
        facts = analyze_crawl(crawl_result)

        if crawl_result.reachable:
            website_status = WebsiteStatus.WEBSITE_FOUND
            quality_score = score_website(facts)
        else:
            website_status = WebsiteStatus.WEBSITE_UNCERTAIN
            quality_score = {"overall": 0, "categories": {}, "reasons": []}

    # Surface what we already know about this business (phone/email/address
    # from manual entry or the discovery engine) to the audit and outreach
    # generators. Previously this sat unused on the Business row -- a
    # no-website business with a known phone/address still got a near-empty
    # "reachable: false" fact set and an outreach draft with nothing to
    # actually reference.
    facts["known_phone"] = business.phone
    facts["known_email"] = business.email
    facts["known_notes"] = business.notes
    facts["has_any_contact_channel"] = bool(business.phone or business.email)

    opportunity = classify_opportunity(
        website_status=website_status,
        website_quality=quality_score if website_status == WebsiteStatus.WEBSITE_FOUND else None,
        facts=facts,
    )

    lead_score = calculate_lead_score(
        website_status=website_status,
        website_quality=quality_score if website_status == WebsiteStatus.WEBSITE_FOUND else None,
        facts=facts,
    )

    location = _location_str(business)

    audit = await generate_audit(
        business_name=business.name,
        industry=business.industry,
        location=location,
        facts=facts,
        quality_score=quality_score,
        opportunity=opportunity,
    )

    outreach_draft = None
    if opportunity["type"].value != "IGNORE":
        outreach_draft = await generate_outreach_draft(
            business_name=business.name,
            industry=business.industry,
            location=location,
            facts=facts,
            opportunity=opportunity,
        )

    logger.info(
        "pipeline.complete",
        business_id=str(business.id),
        opportunity_type=opportunity["type"].value,
        lead_score=lead_score["overall"],
    )

    return {
        "website_status": website_status,
        "pages_crawled": pages_crawled,
        "crawl_data": crawl_data,
        "facts": facts,
        "quality_score": quality_score,
        "opportunity": opportunity,
        "lead_score": lead_score,
        "audit": audit,
        "outreach_draft": outreach_draft,
    }


def pick_best_email(website_url: str | None, emails_found: list[str]) -> str | None:
    """Prefers an email on the business's own domain (e.g. info@acme.com for
    acme.com) over a generic/third-party one (e.g. a booking platform's
    address) that happened to appear on the page."""
    if not emails_found:
        return None
    if website_url:
        site_domain = urlparse(website_url).netloc.lower().removeprefix("www.")
        for email in emails_found:
            email_domain = email.rsplit("@", 1)[-1].lower().removeprefix("www.")
            if site_domain and email_domain == site_domain:
                return email
    return emails_found[0]


async def persist_pipeline_result(db: AsyncSession, business: Business, result: dict) -> None:
    """Upserts Website/WebsiteAnalysis/LeadScore/Opportunity/Audit/OutreachDraft
    for this business. Wrapped in one transaction so a partial failure never
    leaves inconsistent half-written state (spec section 66).

    Shared by both the (legacy) synchronous request path and the background
    worker task -- kept here rather than in a route module so it has no
    dependency on FastAPI.
    """
    facts = result.get("facts") or {}

    # Backfill Business.email/phone from what the crawl actually found on
    # the site, if we don't already have one -- these are what outreach
    # actually contacts, and previously sat unused inside facts/audit.
    if not business.email:
        best_email = pick_best_email(business.submitted_website_url, facts.get("emails_found") or [])
        if best_email:
            business.email = best_email
    if not business.phone and facts.get("phones_found"):
        business.phone = facts["phones_found"][0]
    db.add(business)

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
