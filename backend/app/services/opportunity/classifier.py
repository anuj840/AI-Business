"""Rule-based opportunity classification (spec section 13).

Deterministic rules first — AI is used later (in the audit generator) only
to explain/elaborate, never to decide the category itself. This keeps the
classification reproducible and debuggable.
"""
from __future__ import annotations

from app.models.business import OpportunityType, WebsiteStatus

SERVICE_RECOMMENDATION = {
    OpportunityType.NEW_WEBSITE: "Website Package",
    OpportunityType.WEBSITE_REDESIGN: "Redesign Package",
    OpportunityType.WEBSITE_OPTIMIZATION: "Conversion Optimization Package",
    OpportunityType.LEAD_CONVERSION: "Conversion Package",
    OpportunityType.AI_AUTOMATION: "AI Automation Package",
    OpportunityType.SEO_GROWTH: "SEO Package",
    OpportunityType.OTHER_SERVICE: None,
    OpportunityType.IGNORE: None,
}


def classify_opportunity(
    *, website_status: WebsiteStatus, website_quality: dict | None, facts: dict | None
) -> dict:
    """Returns {"type": OpportunityType, "confidence": float, "reasons": [str]}."""
    facts = facts or {}
    reasons: list[str] = []

    if website_status == WebsiteStatus.NO_WEBSITE_FOUND:
        reasons.append("No confirmed website found for this business.")
        return _result(OpportunityType.NEW_WEBSITE, 0.9, reasons)

    if website_status in (WebsiteStatus.WEBSITE_UNCERTAIN, WebsiteStatus.WEBSITE_UNAVAILABLE):
        reasons.append("Website presence could not be confirmed with available signals.")
        return _result(OpportunityType.NEW_WEBSITE, 0.4, reasons)

    quality = (website_quality or {}).get("overall", 0)
    categories = (website_quality or {}).get("categories", {})

    if quality < 40:
        reasons.append(f"Website quality score is low ({quality}/100).")
        return _result(OpportunityType.WEBSITE_REDESIGN, 0.85, reasons)

    conversion = categories.get("conversion", 0)
    automation = categories.get("automation_readiness", 0)
    seo = categories.get("seo_basics", 0)

    if quality >= 80 and conversion >= 70 and automation >= 60:
        reasons.append("Strong technical, conversion and automation signals across the site.")
        return _result(OpportunityType.IGNORE, 0.75, reasons)

    if conversion < 50:
        reasons.append(
            f"Website exists but conversion signals are weak (conversion score {conversion}/100)."
        )
        return _result(OpportunityType.LEAD_CONVERSION, 0.7, reasons)

    if automation < 50:
        reasons.append(
            f"No automated response/engagement detected (automation readiness {automation}/100)."
        )
        return _result(OpportunityType.AI_AUTOMATION, 0.65, reasons)

    if seo < 50:
        reasons.append(f"Website has weak SEO/content fundamentals (seo score {seo}/100).")
        return _result(OpportunityType.SEO_GROWTH, 0.6, reasons)

    if 40 <= quality < 60:
        reasons.append(f"Website is dated/underperforming overall ({quality}/100).")
        return _result(OpportunityType.WEBSITE_OPTIMIZATION, 0.55, reasons)

    reasons.append("No clear, explainable commercial opportunity identified.")
    return _result(OpportunityType.IGNORE, 0.5, reasons)


def _result(opportunity_type: OpportunityType, confidence: float, reasons: list[str]) -> dict:
    return {
        "type": opportunity_type,
        "confidence": confidence,
        "reasons": reasons,
        "recommended_service": SERVICE_RECOMMENDATION.get(opportunity_type),
    }
