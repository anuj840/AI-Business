"""Domain age via RDAP (Registration Data Access Protocol).

Business rationale: our deterministic checks (HTTPS, forms, meta tags...)
measure technical health, but nothing measures visual/design staleness --
a site can pass every technical check and still look and feel like it was
built in 2010. Domain age is a strong, free, legitimate proxy for that: a
business that registered its domain 10-20 years ago and never re-platformed
is a strong redesign candidate even when the technical score looks fine.

RDAP (not WHOIS) is the modern, IANA-standardized protocol for this --
structured JSON over HTTPS, not scraping, not a ToS violation. We use the
free public bootstrap/proxy at rdap.org, which redirects to the domain's
actual registry RDAP server based on its TLD (e.g. Verisign for .com).
This is a fixed, trusted third-party API endpoint -- the business's domain
name becomes a path segment in a request to that trusted host, which is a
different (much narrower) trust boundary than the crawler's SSRF concern
(which navigates a browser to an arbitrary user-supplied URL); we still
validate the domain looks like a plausible hostname before using it.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

RDAP_BOOTSTRAP_URL = "https://rdap.org/domain/{domain}"
USER_AGENT = "AIBusinessGrowthPlatform/0.1 (domain-age-lookup; contact: internal-tool)"

_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9-]+)+$")


def _extract_registrable_domain(website_url: str) -> str | None:
    """Best-effort: strips a leading 'www.' and returns the hostname.
    Doesn't attempt full public-suffix-list parsing (e.g. 'foo.co.uk' vs
    'shop.foo.co.uk') -- good enough for the common case, not perfect for
    every multi-level ccTLD."""
    hostname = urlparse(website_url).netloc.lower()
    hostname = hostname.split(":")[0]  # drop a port if present
    hostname = hostname.removeprefix("www.")
    if not hostname or not _HOSTNAME_RE.match(hostname):
        return None
    return hostname


async def get_domain_age(website_url: str) -> dict:
    """Returns {"domain", "registered_date", "age_years", "error"}. Never
    raises -- a lookup failure just means we don't have this signal,
    consistent with the never-crash-a-job rule (spec section 66)."""
    domain = _extract_registrable_domain(website_url)
    if not domain:
        return {"domain": None, "registered_date": None, "age_years": None, "error": None}

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                RDAP_BOOTSTRAP_URL.format(domain=domain),
                headers={"User-Agent": USER_AGENT, "Accept": "application/rdap+json"},
            )
        if resp.status_code == 404:
            return {"domain": domain, "registered_date": None, "age_years": None, "error": None}
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 - never crash the caller/job
        logger.warning("domain_age.lookup_failed", domain=domain, error=str(exc))
        return {"domain": domain, "registered_date": None, "age_years": None, "error": str(exc)}

    registered_date = None
    for event in data.get("events", []):
        if event.get("eventAction") == "registration":
            registered_date = event.get("eventDate")
            break

    age_years = None
    if registered_date:
        try:
            registered_dt = datetime.fromisoformat(registered_date.replace("Z", "+00:00"))
            age_years = round((datetime.now(timezone.utc) - registered_dt).days / 365.25, 1)
        except ValueError:
            logger.warning("domain_age.unparseable_date", domain=domain, raw=registered_date)

    return {
        "domain": domain,
        "registered_date": registered_date,
        "age_years": age_years,
        "error": None,
    }
