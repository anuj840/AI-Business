"""Lead scoring engine (spec section 14).

Produces an explainable 0-100 score. In the vertical slice we only have
the business record + website facts to work with (no review counts /
historical conversion data yet — those arrive with the discovery engine
in a later phase), so the rule set below is intentionally conservative
and documented so it's easy to extend.
"""
from __future__ import annotations

from app.models.business import WebsiteStatus

NO_WEBSITE_BONUS = 25
STRONG_CONTACT_BONUS = 10
MULTI_PAGE_PRESENCE_BONUS = 6


def calculate_lead_score(
    *,
    website_status: WebsiteStatus,
    website_quality: dict | None,
    facts: dict | None,
) -> dict:
    """Returns {"overall": int, "reasons": [{"label": str, "points": int}]}."""
    reasons: list[dict] = []
    points = 0
    facts = facts or {}

    if website_status == WebsiteStatus.NO_WEBSITE_FOUND:
        points += NO_WEBSITE_BONUS
        reasons.append(
            {
                "label": "No confirmed website — clear new-website opportunity",
                "points": NO_WEBSITE_BONUS,
            }
        )
    elif website_quality is not None:
        overall_quality = website_quality.get("overall", 0)
        # Poor existing websites represent opportunity too; invert the quality
        # score into scoring "room to improve" points, capped.
        improvement_room = max(0, 60 - overall_quality)
        weighted = round(improvement_room * 0.4)
        if weighted:
            points += weighted
            reasons.append(
                {
                    "label": f"Website quality {overall_quality}/100 — room for improvement",
                    "points": weighted,
                }
            )

    if facts.get("has_phone") or facts.get("has_email"):
        points += STRONG_CONTACT_BONUS
        reasons.append(
            {"label": "Public business contact available", "points": STRONG_CONTACT_BONUS}
        )

    if facts.get("pages_crawled", 0) >= 3:
        points += MULTI_PAGE_PRESENCE_BONUS
        reasons.append(
            {"label": "Multiple service/content pages present", "points": MULTI_PAGE_PRESENCE_BONUS}
        )

    if facts.get("has_chat_widget") and facts.get("has_booking_system") and website_quality and website_quality.get("overall", 0) >= 80:
        # Excellent digital presence — de-prioritize per spec section 62.
        points = min(points, 32)
        reasons.append(
            {"label": "Strong existing digital presence — low priority", "points": 0}
        )

    overall = max(0, min(100, points))
    return {"overall": overall, "reasons": reasons}


def priority_label(score: int) -> str:
    if score >= 85:
        return "HIGH_PRIORITY"
    if score >= 65:
        return "GOOD"
    if score >= 40:
        return "MEDIUM"
    return "LOW"
