"""Tests for the fast, AI-free contact-only check (app/services/contact/finder.py).

WebsiteCrawler.crawl itself is exercised elsewhere (test_crawler_extract.py,
against a real browser); here we mock it to test quick_contact_check's own
aggregation/selection logic and its SSRF guard in isolation.
"""
from unittest.mock import AsyncMock, patch

from app.services.contact.finder import quick_contact_check
from app.services.crawler.playwright_crawler import CrawlResult, PageSnapshot


async def test_returns_not_reachable_for_unsafe_url():
    result = await quick_contact_check("http://localhost/")
    assert result["reachable"] is False
    assert result["phone"] is None
    assert result["email"] is None


async def test_returns_not_reachable_when_crawl_fails():
    fake_result = CrawlResult(root_url="https://example.com", reachable=False, error="timeout")
    with patch(
        "app.services.contact.finder.WebsiteCrawler.crawl",
        AsyncMock(return_value=fake_result),
    ):
        result = await quick_contact_check("https://example.com")

    assert result["reachable"] is False
    assert result["pages_checked"] == 0


async def test_aggregates_phone_and_email_from_pages():
    pages = [
        PageSnapshot(
            url="https://example.com",
            status=200,
            title="Home",
            meta_description=None,
            emails=["info@example.com"],
            phones=["+1 555-0100"],
        ),
        PageSnapshot(
            url="https://example.com/contact",
            status=200,
            title="Contact",
            meta_description=None,
            emails=["bookings@thirdparty.com"],
            phones=[],
        ),
    ]
    fake_result = CrawlResult(root_url="https://example.com", reachable=True, pages=pages)
    with patch(
        "app.services.contact.finder.WebsiteCrawler.crawl",
        AsyncMock(return_value=fake_result),
    ):
        result = await quick_contact_check("https://example.com")

    assert result["reachable"] is True
    assert result["pages_checked"] == 2
    assert result["phone"] == "+1 555-0100"
    # Prefers the domain-matching email over the third-party one, same rule
    # as the full pipeline's backfill (pick_best_email).
    assert result["email"] == "info@example.com"


async def test_returns_none_when_nothing_found():
    pages = [
        PageSnapshot(
            url="https://example.com", status=200, title="Home", meta_description=None
        )
    ]
    fake_result = CrawlResult(root_url="https://example.com", reachable=True, pages=pages)
    with patch(
        "app.services.contact.finder.WebsiteCrawler.crawl",
        AsyncMock(return_value=fake_result),
    ):
        result = await quick_contact_check("https://example.com")

    assert result["phone"] is None
    assert result["email"] is None
    assert result["reachable"] is True
