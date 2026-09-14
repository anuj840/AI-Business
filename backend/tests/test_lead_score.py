from app.models.business import WebsiteStatus
from app.services.scoring.lead_score import calculate_lead_score


def test_no_website_business_gets_new_website_bonus():
    result = calculate_lead_score(
        website_status=WebsiteStatus.NO_WEBSITE_FOUND, website_quality=None, facts={}
    )
    assert result["overall"] >= 25


def test_contact_bonus_applies_from_known_phone_even_with_no_website():
    """Regression: a no-website business is never crawled, so has_phone/
    has_email (set only by crawling) can never be true for it -- previously
    this meant the contact bonus could NEVER apply to a no-website business
    even when we already had a phone number on file for it (e.g. from the
    discovery engine)."""
    no_contact = calculate_lead_score(
        website_status=WebsiteStatus.NO_WEBSITE_FOUND,
        website_quality=None,
        facts={"reachable": False},
    )
    with_known_phone = calculate_lead_score(
        website_status=WebsiteStatus.NO_WEBSITE_FOUND,
        website_quality=None,
        facts={"reachable": False, "known_phone": "+1 555-0100"},
    )
    assert with_known_phone["overall"] > no_contact["overall"]
    assert any("contact" in r["label"].lower() for r in with_known_phone["reasons"])


def test_contact_bonus_applies_from_known_email_too():
    result = calculate_lead_score(
        website_status=WebsiteStatus.NO_WEBSITE_FOUND,
        website_quality=None,
        facts={"reachable": False, "known_email": "owner@example.com"},
    )
    assert any("contact" in r["label"].lower() for r in result["reasons"])


def test_contact_bonus_still_applies_from_crawled_facts():
    result = calculate_lead_score(
        website_status=WebsiteStatus.WEBSITE_FOUND,
        website_quality={"overall": 50, "categories": {}},
        facts={"has_phone": True},
    )
    assert any("contact" in r["label"].lower() for r in result["reasons"])


def test_weak_existing_website_gets_improvement_room_points():
    result = calculate_lead_score(
        website_status=WebsiteStatus.WEBSITE_FOUND,
        website_quality={"overall": 20, "categories": {}},
        facts={},
    )
    assert result["overall"] > 0


def test_excellent_existing_site_is_capped_low_priority():
    result = calculate_lead_score(
        website_status=WebsiteStatus.WEBSITE_FOUND,
        website_quality={"overall": 90, "categories": {}},
        facts={"has_chat_widget": True, "has_booking_system": True},
    )
    assert result["overall"] <= 32
