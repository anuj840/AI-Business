"""OpenStreetMap-based LeadSourceProvider (spec section 7).

Free, keyless, no signup -- appropriate for an MVP with "low initial cost"
as a design goal (spec section 74). Coverage is uneven (depends on how well
mapped an area is) and weaker than a paid provider like Google Places or
Yelp Fusion; those remain natural additions later behind this same
LeadSourceProvider interface, per spec section 7's "licensed data providers
later" note.

Respects OSM's usage policy: descriptive User-Agent, a bounded/light query
(capped result count, single request per discovery run), and the public
Overpass instance's documented interpreter endpoint. This is a small,
bounded lookup -- not a bulk-scraping operation (spec section 58 explicitly
rules out building "huge scraping infrastructure" for the MVP) -- but the
bounding box can span an entire region/state (omit `city`) and a single
call can search several industries at once (comma-separated), both of
which multiply how many real businesses one free, keyless run returns.
"""
from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.services.discovery.geocode import GeocodeError, geocode_bounding_box
from app.services.discovery.industry_map import label_from_osm_tags, resolve_tags, split_industries
from app.services.discovery.provider import (
    DiscoveredBusiness,
    DiscoveryCriteria,
    LeadSourceProvider,
)

logger = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "AIBusinessGrowthPlatform/0.1 (lead-discovery; contact: internal-tool)"

# Fallback tag keys searched by keyword when the industry has no curated
# mapping (see industry_map.py). Broader = more false positives, so this is
# only used as a last resort.
FALLBACK_KEYS = ("shop", "amenity", "craft", "office")


class OpenStreetMapProvider(LeadSourceProvider):
    def __init__(self) -> None:
        # Set when discover() returns [] because the source itself failed
        # (geocoding or Overpass unavailable/rate-limited), as opposed to a
        # genuine "no matching businesses" result -- callers can surface
        # this distinction to the user instead of a silent empty list.
        self.last_error: str | None = None

    async def discover(self, criteria: DiscoveryCriteria) -> list[DiscoveredBusiness]:
        self.last_error = None
        try:
            south, west, north, east = await geocode_bounding_box(
                country=criteria.country, region=criteria.region, city=criteria.city
            )
        except GeocodeError as exc:
            logger.warning("discovery.geocode_failed", error=str(exc))
            self.last_error = f"Could not resolve that location: {exc}"
            return []
        except Exception as exc:  # noqa: BLE001 - never crash the caller
            logger.error("discovery.geocode_unexpected_error", error=str(exc))
            self.last_error = "Geocoding service is currently unavailable."
            return []

        bbox = f"{south},{west},{north},{east}"
        industries = split_industries(criteria.industry) or [criteria.industry]
        limit = max(1, min(criteria.max_results, 200))

        query = self._build_query(bbox=bbox, industries=industries, limit=limit)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    OVERPASS_URL,
                    data={"data": query},
                    headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001 - never crash the caller/job
            logger.error("discovery.overpass_request_failed", error=str(exc))
            self.last_error = (
                "The OpenStreetMap search service is temporarily unavailable or "
                "rate-limited. Please wait a moment and try again."
            )
            return []

        elements = data.get("elements", [])
        # Same element can match more than one requested industry's clause
        # (Overpass unions results); dedupe by (type, id) before parsing.
        seen_refs: set[tuple[str, int]] = set()
        results = []
        for el in elements:
            ref = (el.get("type"), el.get("id"))
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            parsed = self._parse_element(el, criteria)
            if parsed:
                results.append(parsed)

        return results[: criteria.max_results]

    def _build_query(self, *, bbox: str, industries: list[str], limit: int) -> str:
        clause_blocks: list[str] = []

        for industry in industries:
            tags = resolve_tags(industry)
            if tags:
                for k, v in tags:
                    clause_blocks.append(f'  node["{k}"="{v}"]({bbox});')
                    clause_blocks.append(f'  way["{k}"="{v}"]({bbox});')
            else:
                # No curated mapping: fall back to a keyword match against
                # the name tag, restricted to plausible business tag keys
                # so we don't pull in unrelated points (rivers, admin
                # boundaries...).
                safe_keyword = industry.replace('"', "")
                key_regex = "|".join(FALLBACK_KEYS)
                clause_blocks.append(
                    f'  node["name"~"{safe_keyword}",i][~"^({key_regex})$"~"."]({bbox});'
                )
                clause_blocks.append(
                    f'  way["name"~"{safe_keyword}",i][~"^({key_regex})$"~"."]({bbox});'
                )

        clauses = "\n".join(clause_blocks)

        return f"""[out:json][timeout:25];
(
{clauses}
);
out center tags {limit};
"""

    def _parse_element(self, el: dict, criteria: DiscoveryCriteria) -> DiscoveredBusiness | None:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            return None

        website = tags.get("website") or tags.get("contact:website")
        phone = tags.get("phone") or tags.get("contact:phone")
        email = tags.get("email") or tags.get("contact:email")

        center = el.get("center") or {}
        lat = el.get("lat", center.get("lat"))
        lon = el.get("lon", center.get("lon"))

        address_parts = [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
        ]
        address = " ".join(p for p in address_parts if p) or None

        return DiscoveredBusiness(
            name=name,
            source_name="openstreetmap",
            source_ref=f"{el.get('type')}/{el.get('id')}",
            matched_industry=label_from_osm_tags(tags),
            website_url=website,
            phone=phone,
            email=email,
            country=criteria.country,
            region=criteria.region,
            city=tags.get("addr:city") or criteria.city,
            address=address,
            latitude=lat,
            longitude=lon,
        )
