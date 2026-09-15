"""Discovery orchestrator: run a LeadSourceProvider, dedupe against the
existing database, and persist new Business rows.

Deliberately does NOT run the full analysis pipeline (crawl + AI) on
discovered businesses -- that stays a separate, explicit per-business
action, since it's slow and costs real AI compute per spec section 39's
async-job direction. It DOES run the fast, AI-free contact-only check
(app/services/contact/finder.py) for results that have a website but no
phone/email from the source -- knowing whether a lead is reachable at all
is cheap and worth doing eagerly, unlike the full audit.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.business import Business
from app.services.contact.finder import quick_contact_check
from app.services.discovery.dedup import is_duplicate
from app.services.discovery.osm_provider import OpenStreetMapProvider
from app.services.discovery.provider import (
    DiscoveredBusiness,
    DiscoveryCriteria,
    LeadSourceProvider,
)
from app.services.discovery.utils import parse_csv_list

logger = get_logger(__name__)

CONTACT_CHECK_CONCURRENCY = 5
CONTACT_CHECK_MAX_PER_RUN = 30
"""Caps worst-case added latency for a single discovery run -- if more than
this many results need a check, the rest are left for an on-demand or
future run rather than making one discovery call even longer."""

MAX_CITIES_PER_RUN = 10
"""Bounds worst-case duration: each city is a separate geocode + Overpass
call, run sequentially against the same free/keyless source that has real
rate limits (see osm_provider.py's last_error handling)."""


async def _discover_across_cities(
    provider: LeadSourceProvider, criteria: DiscoveryCriteria
) -> tuple[list[DiscoveredBusiness], list[str]]:
    """Targeting several cities in one discovery run: 'Houston, Austin,
    Dallas' becomes one candidate list, one dedup pass, one persist -- the
    same "several targets, one call" idea as the existing multi-industry
    support, just across the other axis (place instead of category).
    `max_results` applies per city, not to the combined total (documented
    in the API request schema) -- keeping each city's own Overpass query
    the same size as a single-city request, rather than silently shrinking
    per-city results as more cities are added.
    """
    cities = parse_csv_list(criteria.city or "")[:MAX_CITIES_PER_RUN] or [None]

    all_candidates: list[DiscoveredBusiness] = []
    errors: list[str] = []

    for city in cities:
        city_criteria = DiscoveryCriteria(
            country=criteria.country,
            region=criteria.region,
            city=city,
            industry=criteria.industry,
            max_results=criteria.max_results,
        )
        results = await provider.discover(city_criteria)
        all_candidates.extend(results)
        if provider.last_error:
            errors.append(f"{city or criteria.region or criteria.country}: {provider.last_error}")

    return all_candidates, errors


async def run_discovery(db: AsyncSession, criteria: DiscoveryCriteria) -> dict:
    provider = OpenStreetMapProvider()
    candidates, source_errors = await _discover_across_cities(provider, criteria)

    existing_rows = await db.execute(select(Business.name, Business.city, Business.phone))
    existing = [(row.name, row.city, row.phone) for row in existing_rows]

    created: list[Business] = []
    skipped_duplicates = 0

    for candidate in candidates:
        if is_duplicate(candidate.name, candidate.city, candidate.phone, existing):
            skipped_duplicates += 1
            continue

        business = Business(
            name=candidate.name,
            country=candidate.country,
            region=candidate.region,
            city=candidate.city,
            industry=candidate.matched_industry or criteria.industry or None,
            phone=candidate.phone,
            email=candidate.email,
            submitted_website_url=candidate.website_url,
            notes=_format_notes(candidate),
            source_name=candidate.source_name,
            source_ref=candidate.source_ref,
            discovered_at=datetime.now(timezone.utc),
        )
        db.add(business)
        created.append(business)
        existing.append((candidate.name, candidate.city, candidate.phone))

    await db.commit()
    for business in created:
        await db.refresh(business)

    contact_checked = await _check_contacts_for_missing(db, created)

    combined_error = "; ".join(source_errors) if source_errors else None

    logger.info(
        "discovery.run_complete",
        found=len(candidates),
        created=len(created),
        skipped_duplicates=skipped_duplicates,
        contact_checked=contact_checked,
        source_error=combined_error,
    )

    return {
        "found": len(candidates),
        "created": len(created),
        "skipped_duplicates": skipped_duplicates,
        "businesses": created,
        "source_error": combined_error,
    }


async def _check_contacts_for_missing(db: AsyncSession, created: list[Business]) -> int:
    """Runs the fast contact-only check, bounded concurrency, for newly
    discovered businesses that have a website but no phone/email from the
    source. Returns how many were actually checked."""
    candidates = [
        b for b in created if b.submitted_website_url and not (b.phone and b.email)
    ][:CONTACT_CHECK_MAX_PER_RUN]
    if not candidates:
        return 0

    semaphore = asyncio.Semaphore(CONTACT_CHECK_CONCURRENCY)

    async def _check_one(business: Business) -> None:
        async with semaphore:
            try:
                found = await quick_contact_check(business.submitted_website_url)
            except Exception as exc:  # noqa: BLE001 - one failure must not sink the batch
                logger.warning(
                    "discovery.contact_check_failed", business_id=str(business.id), error=str(exc)
                )
                return
            if found["reachable"]:
                business.phone = business.phone or found["phone"]
                business.email = business.email or found["email"]
                db.add(business)

    await asyncio.gather(*(_check_one(b) for b in candidates))
    await db.commit()
    return len(candidates)


def _format_notes(candidate: DiscoveredBusiness) -> str | None:
    parts = []
    if candidate.address:
        parts.append(f"Address: {candidate.address}")
    if candidate.latitude is not None and candidate.longitude is not None:
        parts.append(f"Location: {candidate.latitude:.5f}, {candidate.longitude:.5f}")
    return "; ".join(parts) if parts else None
