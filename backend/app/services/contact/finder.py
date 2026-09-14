"""Fast, AI-free contact-info-only check.

Business rationale: outreach can only ever reach a lead through a phone
number or email address, and the full pipeline (crawl + two AI calls) can
take 45 seconds to several minutes. There's no reason to pay that cost
before knowing whether a business is even reachable at all -- this answers
that one question in a few seconds: a bounded 2-page crawl (homepage +
whatever it links to), pure regex extraction already built into the
crawler, no AI, no deterministic analysis, no audit.

Used both on-demand (an explicit "check contact info" action) and
automatically right after a business is created with a website but no
known phone/email yet -- see app/api/routes/businesses.py and
app/services/discovery/service.py.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.services.crawler.playwright_crawler import WebsiteCrawler
from app.services.crawler.ssrf import UnsafeURLError, validate_public_url
from app.services.pipeline import pick_best_email

logger = get_logger(__name__)

QUICK_CHECK_MAX_PAGES = 2


async def quick_contact_check(website_url: str) -> dict:
    """Returns {"phone", "email", "pages_checked", "reachable"}. Never
    raises -- an unreachable/blocked site just means nothing was found,
    consistent with the never-crash-a-job rule (spec section 66)."""
    try:
        validate_public_url(website_url)
    except UnsafeURLError as exc:
        logger.warning("contact_check.blocked_unsafe_url", url=website_url, reason=str(exc))
        return {"phone": None, "email": None, "pages_checked": 0, "reachable": False}

    crawler = WebsiteCrawler(max_pages=QUICK_CHECK_MAX_PAGES)
    result = await crawler.crawl(website_url)

    if not result.reachable:
        return {"phone": None, "email": None, "pages_checked": 0, "reachable": False}

    emails = sorted({e for p in result.pages for e in p.emails})
    phones = sorted({ph for p in result.pages for ph in p.phones})

    return {
        "phone": phones[0] if phones else None,
        "email": pick_best_email(website_url, emails),
        "pages_checked": len(result.pages),
        "reachable": True,
    }
