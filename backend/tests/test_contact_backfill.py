"""Regression coverage for backfilling Business.email/phone from crawled
facts -- previously an email found on the crawled site sat unused in the
audit's raw facts and never became the business's actual contact address,
even though outreach depends on it.
"""
from app.services.pipeline import pick_best_email


def test_prefers_email_on_the_business_own_domain():
    emails = ["bookings@thirdpartyplatform.com", "info@acmeroofing.com"]
    assert pick_best_email("https://acmeroofing.com", emails) == "info@acmeroofing.com"


def test_falls_back_to_first_email_when_no_domain_match():
    emails = ["contact@example.org", "sales@example.org"]
    assert pick_best_email("https://acmeroofing.com", emails) == "contact@example.org"


def test_falls_back_to_first_email_when_no_website():
    emails = ["info@acmeroofing.com"]
    assert pick_best_email(None, emails) == "info@acmeroofing.com"


def test_returns_none_for_no_emails():
    assert pick_best_email("https://acmeroofing.com", []) is None


def test_matches_ignoring_www_prefix_on_either_side():
    emails = ["info@acmeroofing.com"]
    assert pick_best_email("https://www.acmeroofing.com", emails) == "info@acmeroofing.com"
