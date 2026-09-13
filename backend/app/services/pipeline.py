"""Vertical-slice pipeline orchestrator.

DISCOVER -> VERIFY -> ANALYZE -> SCORE -> IDENTIFY OPPORTUNITY -> CREATE PROOF
(spec section 1), scoped here to a single business submitted with a name +
optional website URL (spec section 73). Discovery/campaigns/multi-tenant
come in later phases; this function is written so it can later be invoked
from a background worker instead of a request handler without changes.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.models.business import Business, WebsiteStatus
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
