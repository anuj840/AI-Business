from app.services.scoring.engine import score_website


def test_unreachable_site_scores_zero():
    result = score_website({"reachable": False})
    assert result["overall"] == 0


def test_strong_site_scores_high():
    facts = {
        "reachable": True,
        "uses_https": True,
        "has_sitemap": True,
        "has_robots_txt": True,
        "http_error_pages": [],
        "has_viewport_meta": True,
        "has_title": True,
        "has_meta_description": True,
        "has_h1": True,
        "has_service_pages": True,
        "has_contact_page": True,
        "has_phone": True,
        "has_email": True,
        "has_social_presence": True,
        "has_contact_form": True,
        "has_booking_system": True,
        "has_location_page": True,
        "has_chat_widget": True,
        "has_analytics": True,
        "pages_crawled": 5,
    }
    result = score_website(facts)
    assert result["overall"] >= 90


def test_weak_site_scores_low():
    facts = {
        "reachable": True,
        "uses_https": False,
        "has_sitemap": False,
        "has_robots_txt": False,
        "http_error_pages": ["https://example.com/broken"],
        "has_viewport_meta": False,
        "has_title": False,
        "has_meta_description": False,
        "has_h1": False,
        "has_service_pages": False,
        "has_contact_page": False,
        "has_phone": False,
        "has_email": False,
        "has_social_presence": False,
        "has_contact_form": False,
        "has_booking_system": False,
        "has_location_page": False,
        "has_chat_widget": False,
        "has_analytics": False,
        "pages_crawled": 1,
    }
    result = score_website(facts)
    assert result["overall"] < 20
