from app.models.business import OpportunityType, WebsiteStatus
from app.services.opportunity.classifier import classify_opportunity


def test_no_website_maps_to_new_website():
    result = classify_opportunity(
        website_status=WebsiteStatus.NO_WEBSITE_FOUND, website_quality=None, facts={}
    )
    assert result["type"] == OpportunityType.NEW_WEBSITE
    assert result["recommended_service"] == "Website Package"


def test_poor_quality_maps_to_redesign():
    quality = {"overall": 25, "categories": {"conversion": 20, "automation_readiness": 10, "seo_basics": 30}}
    result = classify_opportunity(
        website_status=WebsiteStatus.WEBSITE_FOUND, website_quality=quality, facts={}
    )
    assert result["type"] == OpportunityType.WEBSITE_REDESIGN


def test_excellent_site_maps_to_ignore():
    quality = {
        "overall": 90,
        "categories": {"conversion": 85, "automation_readiness": 80, "seo_basics": 90},
    }
    result = classify_opportunity(
        website_status=WebsiteStatus.WEBSITE_FOUND, website_quality=quality, facts={}
    )
    assert result["type"] == OpportunityType.IGNORE


def test_weak_conversion_maps_to_lead_conversion():
    quality = {
        "overall": 70,
        "categories": {"conversion": 30, "automation_readiness": 80, "seo_basics": 80},
    }
    result = classify_opportunity(
        website_status=WebsiteStatus.WEBSITE_FOUND, website_quality=quality, facts={}
    )
    assert result["type"] == OpportunityType.LEAD_CONVERSION


def test_excellent_but_old_domain_maps_to_redesign_not_ignore():
    """Regression: deterministic checks measure technical health, never
    visual/design staleness -- a site can pass every technical check and
    still be a decade+ old. Without this override, a technically-excellent
    old site was classified IGNORE, missing a real opportunity."""
    quality = {
        "overall": 90,
        "categories": {"conversion": 85, "automation_readiness": 80, "seo_basics": 90},
    }
    result = classify_opportunity(
        website_status=WebsiteStatus.WEBSITE_FOUND,
        website_quality=quality,
        facts={"domain_age_years": 14.2},
    )
    assert result["type"] == OpportunityType.WEBSITE_REDESIGN
    assert any("14" in r for r in result["reasons"])


def test_excellent_and_young_domain_still_maps_to_ignore():
    quality = {
        "overall": 90,
        "categories": {"conversion": 85, "automation_readiness": 80, "seo_basics": 90},
    }
    result = classify_opportunity(
        website_status=WebsiteStatus.WEBSITE_FOUND,
        website_quality=quality,
        facts={"domain_age_years": 2.0},
    )
    assert result["type"] == OpportunityType.IGNORE


def test_excellent_site_with_unknown_domain_age_still_maps_to_ignore():
    quality = {
        "overall": 90,
        "categories": {"conversion": 85, "automation_readiness": 80, "seo_basics": 90},
    }
    result = classify_opportunity(
        website_status=WebsiteStatus.WEBSITE_FOUND,
        website_quality=quality,
        facts={"domain_age_years": None},
    )
    assert result["type"] == OpportunityType.IGNORE
