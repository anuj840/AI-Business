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
OLD_DOMAIN_BONUS = 15
OLD_DOMAIN_THRESHOLD_YEARS = 10


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

    # "has_phone"/"has_email" come from crawling a website's page text and
    # are only ever set when a website was actually crawled; "known_phone"/
    # "known_email" are whatever's already on file for the business
    # (manual entry or the discovery engine) regardless of website status --
    # without checking these too, a no-website business could never earn
    # this bonus even when we already have a working contact channel.
    if (
        facts.get("has_phone")
        or facts.get("has_email")
        or facts.get("known_phone")
        or facts.get("known_email")
    ):
        points += STRONG_CONTACT_BONUS
        reasons.append(
            {"label": "Public business contact available", "points": STRONG_CONTACT_BONUS}
        )

    if facts.get("pages_crawled", 0) >= 3:
        points += MULTI_PAGE_PRESENCE_BONUS
        reasons.append(
            {"label": "Multiple service/content pages present", "points": MULTI_PAGE_PRESENCE_BONUS}
        )

    domain_age_years = facts.get("domain_age_years")
    is_old_domain = domain_age_years is not None and domain_age_years >= OLD_DOMAIN_THRESHOLD_YEARS
    if is_old_domain:
        # Technical checks alone can't see visual/design staleness -- an old
        # domain is a real redesign opportunity even on an otherwise-strong
        # site (see the matching override in the opportunity classifier).
        points += OLD_DOMAIN_BONUS
        reasons.append(
            {
                "label": f"Domain registered ~{domain_age_years:.0f} years ago — likely due a design refresh",
                "points": OLD_DOMAIN_BONUS,
            }
        )

    if (
        facts.get("has_chat_widget")
        and facts.get("has_booking_system")
        and website_quality
        and website_quality.get("overall", 0) >= 80
        and not is_old_domain
    ):
        # Excellent digital presence — de-prioritize per spec section 62.
        # Skipped when the domain is old enough to be a redesign opportunity
        # in its own right regardless of these modern features being present.
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
