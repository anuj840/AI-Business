"""Discovery orchestrator: run a LeadSourceProvider, dedupe against the
existing database, and persist new Business rows.

Deliberately does NOT run the analysis pipeline (crawl + AI) on discovered
businesses -- discovery is meant to be fast and cheap; analysis stays a
separate, explicit per-business (or later, batch) action, since it's slow
and costs real AI compute per spec section 39's async-job direction.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.business import Business
from app.services.discovery.dedup import is_duplicate
from app.services.discovery.osm_provider import OpenStreetMapProvider
from app.services.discovery.provider import DiscoveredBusiness, DiscoveryCriteria

logger = get_logger(__name__)


async def run_discovery(db: AsyncSession, criteria: DiscoveryCriteria) -> dict:
    provider = OpenStreetMapProvider()
    candidates = await provider.discover(criteria)

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
            industry=criteria.industry or None,
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

    logger.info(
        "discovery.run_complete",
        found=len(candidates),
        created=len(created),
        skipped_duplicates=skipped_duplicates,
        source_error=provider.last_error,
    )

    return {
        "found": len(candidates),
        "created": len(created),
        "skipped_duplicates": skipped_duplicates,
        "businesses": created,
        "source_error": provider.last_error,
    }


def _format_notes(candidate: DiscoveredBusiness) -> str | None:
    parts = []
    if candidate.address:
        parts.append(f"Address: {candidate.address}")
    if candidate.latitude is not None and candidate.longitude is not None:
        parts.append(f"Location: {candidate.latitude:.5f}, {candidate.longitude:.5f}")
    return "; ".join(parts) if parts else None
