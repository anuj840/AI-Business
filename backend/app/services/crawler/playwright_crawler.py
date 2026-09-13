"""Modular Playwright-based website crawler.

Responsibilities (spec section 10): open the site, follow a bounded number
of internal links, and extract raw signals for the deterministic analyzer
to interpret. This module does NOT decide what any of it *means* — that is
the analyzer's job (section 11).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.crawler.ssrf import UnsafeURLError, validate_public_url

logger = get_logger(__name__)

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")

SOCIAL_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "tiktok.com",
)

BOOKING_HINTS = ("calendly.com", "acuityscheduling.com", "book", "appointment", "schedule")
CHAT_WIDGET_HINTS = (
    "intercom",
    "drift.com",
    "tawk.to",
    "livechat",
    "crisp.chat",
    "zendesk",
    "hubspot",
)
ANALYTICS_HINTS = ("google-analytics.com", "googletagmanager.com", "gtag(", "hotjar")


@dataclass
class PageSnapshot:
    url: str
    status: int | None
    title: str | None
    meta_description: str | None
    h1: list[str] = field(default_factory=list)
    text_excerpt: str = ""
    forms_count: int = 0
    links: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    social_links: list[str] = field(default_factory=list)
    has_viewport_meta: bool = False
    external_scripts: list[str] = field(default_factory=list)


@dataclass
class CrawlResult:
    root_url: str
    reachable: bool
    pages: list[PageSnapshot] = field(default_factory=list)
    error: str | None = None
    has_sitemap: bool = False
    has_robots_txt: bool = False
    uses_https: bool = False


class WebsiteCrawler:
    """Crawls a business website within a bounded page budget."""

    def __init__(self, max_pages: int | None = None, timeout_ms: int | None = None):
        settings = get_settings()
        self.max_pages = max_pages or settings.CRAWLER_MAX_PAGES
        self.timeout_ms = timeout_ms or settings.CRAWLER_TIMEOUT_MS
        self.user_agent = settings.CRAWLER_USER_AGENT

    async def crawl(self, start_url: str) -> CrawlResult:
        try:
            validated_url = validate_public_url(start_url)
        except UnsafeURLError as exc:
            logger.warning("crawler.blocked_unsafe_url", url=start_url, reason=str(exc))
            return CrawlResult(root_url=start_url, reachable=False, error=f"blocked: {exc}")

        parsed_root = urlparse(validated_url)
        uses_https = parsed_root.scheme == "https"
        root_domain = parsed_root.netloc.lower()

        result = CrawlResult(root_url=validated_url, reachable=False, uses_https=uses_https)

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=self.user_agent)
                page = await context.new_page()

                visited: set[str] = set()
                queue: list[str] = [validated_url]

                # Check robots.txt / sitemap presence (best-effort, non-fatal).
                result.has_robots_txt = await self._path_exists(context, validated_url, "/robots.txt")
                result.has_sitemap = await self._path_exists(context, validated_url, "/sitemap.xml")

                while queue and len(visited) < self.max_pages:
                    url = queue.pop(0)
                    if url in visited:
                        continue

                    try:
                        # Re-validate each hop — a redirect or internal link could
                        # point somewhere unsafe.
                        validate_public_url(url)
                    except UnsafeURLError:
                        continue

                    try:
                        response = await page.goto(
                            url, timeout=self.timeout_ms, wait_until="domcontentloaded"
                        )
                    except Exception as exc:  # noqa: BLE001 - crawler must never crash the job
                        logger.info("crawler.page_failed", url=url, error=str(exc))
                        visited.add(url)
                        continue

                    visited.add(url)
                    snapshot = await self._extract(page, url, response.status if response else None)
                    result.pages.append(snapshot)
                    result.reachable = True

                    for link in snapshot.links:
                        parsed_link = urlparse(link)
                        if parsed_link.netloc.lower() == root_domain and link not in visited:
                            if len(visited) + len(queue) < self.max_pages:
                                queue.append(link)

                await browser.close()
        except Exception as exc:  # noqa: BLE001
            logger.error("crawler.fatal_error", url=validated_url, error=str(exc))
            result.error = str(exc)

        return result

    async def _path_exists(self, context, base_url: str, path: str) -> bool:
        try:
            probe_url = urljoin(base_url, path)
            validate_public_url(probe_url)
            probe_page = await context.new_page()
            resp = await probe_page.goto(probe_url, timeout=self.timeout_ms)
            ok = bool(resp and resp.status < 400)
            await probe_page.close()
            return ok
        except Exception:  # noqa: BLE001
            return False

    async def _extract(self, page, url: str, status: int | None) -> PageSnapshot:
        title = await page.title()
        html = await page.content()
        text = await page.inner_text("body") if await page.query_selector("body") else ""

        # Use query_selector (returns None immediately if absent) rather than
        # page.get_attribute(selector, ...), which auto-waits the full
        # navigation timeout for the element to appear and throws if it never
        # does — most pages simply don't have a meta description at all.
        meta_description_el = await page.query_selector('meta[name="description"]')
        meta_description = (
            await meta_description_el.get_attribute("content") if meta_description_el else None
        )
        has_viewport = await page.query_selector('meta[name="viewport"]') is not None

        h1_elements = await page.query_selector_all("h1")
        h1_texts = [(await el.inner_text()).strip() for el in h1_elements[:5]]

        forms_count = len(await page.query_selector_all("form"))

        anchors = await page.query_selector_all("a[href]")
        links: list[str] = []
        social_links: list[str] = []
        for a in anchors:
            href = await a.get_attribute("href")
            if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            absolute = urljoin(url, href)
            if absolute.startswith(("http://", "https://")):
                links.append(absolute)
                if any(domain in absolute for domain in SOCIAL_DOMAINS):
                    social_links.append(absolute)

        emails = list(dict.fromkeys(EMAIL_RE.findall(text)))
        phones = list(dict.fromkeys(PHONE_RE.findall(text)))[:5]

        script_srcs: list[str] = []
        script_elements = await page.query_selector_all("script[src]")
        for s in script_elements:
            src = await s.get_attribute("src")
            if src:
                script_srcs.append(src)
        # inline scripts matter for analytics/chat detection too
        if any(hint in html.lower() for hint in ANALYTICS_HINTS):
            script_srcs.append("(inline-analytics-detected)")
        if any(hint in html.lower() for hint in CHAT_WIDGET_HINTS):
            script_srcs.append("(inline-chat-widget-detected)")
        if any(hint in html.lower() for hint in BOOKING_HINTS):
            script_srcs.append("(booking-hint-detected)")

        return PageSnapshot(
            url=url,
            status=status,
            title=title,
            meta_description=meta_description,
            h1=h1_texts,
            text_excerpt=text[:3000],
            forms_count=forms_count,
            links=links,
            emails=emails,
            phones=phones,
            social_links=list(dict.fromkeys(social_links)),
            has_viewport_meta=has_viewport,
            external_scripts=script_srcs,
        )
