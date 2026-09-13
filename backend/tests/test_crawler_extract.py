"""Regression test for the crawler's page extraction.

Guards against a real bug found during manual end-to-end testing: using
page.get_attribute(selector, ...) for an element that may not exist causes
Playwright to auto-wait the full navigation timeout and then raise, instead
of returning None immediately. Most real-world pages lack a meta description
(example.com does), so this silently broke every crawl of such a site.
"""
import pytest
from playwright.async_api import async_playwright

from app.services.crawler.playwright_crawler import WebsiteCrawler

NO_META_DESCRIPTION_HTML = """
<html>
<head><title>No Meta Description</title></head>
<body><h1>Hello</h1></body>
</html>
"""

HAS_META_DESCRIPTION_HTML = """
<html>
<head>
  <title>Has Meta Description</title>
  <meta name="description" content="A test description">
  <meta name="viewport" content="width=device-width">
</head>
<body><h1>Hello</h1></body>
</html>
"""


@pytest.mark.asyncio
async def test_extract_handles_missing_meta_description_without_hanging():
    crawler = WebsiteCrawler()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(NO_META_DESCRIPTION_HTML)
        snapshot = await crawler._extract(page, "https://example.com/", 200)
        await browser.close()

    assert snapshot.meta_description is None
    assert snapshot.title == "No Meta Description"


@pytest.mark.asyncio
async def test_extract_reads_meta_description_when_present():
    crawler = WebsiteCrawler()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HAS_META_DESCRIPTION_HTML)
        snapshot = await crawler._extract(page, "https://example.com/", 200)
        await browser.close()

    assert snapshot.meta_description == "A test description"
    assert snapshot.has_viewport_meta is True
