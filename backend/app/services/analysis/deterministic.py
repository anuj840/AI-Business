"""Deterministic (non-AI) website fact extraction.

Per spec section 11: do NOT use an LLM for simple, checkable facts. This
module turns raw CrawlResult data into a flat dict of booleans/counts that
the scoring engine and opportunity classifier consume, and that the audit
report can cite verbatim as OBSERVED FACT (never AI inference).
"""
from __future__ import annotations

from app.services.crawler.playwright_crawler import CrawlResult

BOOKING_MARKER = "booking-hint-detected"
CHAT_MARKER = "inline-chat-widget-detected"
ANALYTICS_MARKER = "inline-analytics-detected"


def analyze_crawl(crawl: CrawlResult) -> dict:
    """Produce a flat dict of deterministic facts about the site."""
    if not crawl.reachable or not crawl.pages:
        return {
            "reachable": False,
            "error": crawl.error,
            "pages_crawled": 0,
        }

    home = crawl.pages[0]
    all_text_scripts = [s for p in crawl.pages for s in p.external_scripts]
    all_emails = sorted({e for p in crawl.pages for e in p.emails})
    all_phones = sorted({ph for p in crawl.pages for ph in p.phones})
    all_social = sorted({s for p in crawl.pages for s in p.social_links})
    total_forms = sum(p.forms_count for p in crawl.pages)

    page_titles_lower = " ".join((p.title or "").lower() for p in crawl.pages)
    has_contact_page = "contact" in page_titles_lower or any(
        "contact" in p.url.lower() for p in crawl.pages
    )
    has_service_pages = any(
        kw in p.url.lower() for p in crawl.pages for kw in ("service", "services")
    )
    has_location_page = any(
        kw in p.url.lower() for p in crawl.pages for kw in ("location", "locations", "areas")
    )

    facts = {
        "reachable": True,
        "pages_crawled": len(crawl.pages),
        "uses_https": crawl.uses_https,
        "has_sitemap": crawl.has_sitemap,
        "has_robots_txt": crawl.has_robots_txt,
        "has_title": bool(home.title),
        "title": home.title,
        "has_meta_description": bool(home.meta_description),
        "meta_description": home.meta_description,
        "has_h1": bool(home.h1),
        "h1_count_home": len(home.h1),
        "has_viewport_meta": home.has_viewport_meta,
        "forms_count_total": total_forms,
        "has_contact_form": total_forms > 0,
        "has_contact_page": has_contact_page,
        "has_service_pages": has_service_pages,
        "has_location_page": has_location_page,
        "emails_found": all_emails,
        "has_email": bool(all_emails),
        "phones_found": all_phones,
        "has_phone": bool(all_phones),
        "social_links": all_social,
        "has_social_presence": bool(all_social),
        "has_booking_system": any(BOOKING_MARKER in s for s in all_text_scripts),
        "has_chat_widget": any(CHAT_MARKER in s for s in all_text_scripts),
        "has_analytics": any(ANALYTICS_MARKER in s for s in all_text_scripts),
        "http_error_pages": [p.url for p in crawl.pages if p.status and p.status >= 400],
    }
    return facts
