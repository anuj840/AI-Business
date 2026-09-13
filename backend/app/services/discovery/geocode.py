"""Geocodes a country/region/city into a bounding box using Nominatim
(OpenStreetMap's free geocoder). No API key required, but usage policy
requires a descriptive User-Agent and a light request rate -- see
https://operations.osmfoundation.org/policies/nominatim/.
"""
from __future__ import annotations

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "AIBusinessGrowthPlatform/0.1 (lead-discovery; contact: internal-tool)"


class GeocodeError(Exception):
    pass


async def geocode_bounding_box(
    *, country: str, region: str | None, city: str | None
) -> tuple[float, float, float, float]:
    """Returns (south, west, north, east) for the given location.

    Raises GeocodeError if the location can't be resolved -- callers should
    treat this as "no results" rather than crash the request.
    """
    query = ", ".join(part for part in (city, region, country) if part)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        results = resp.json()

    if not results:
        raise GeocodeError(f"Could not geocode location: {query!r}")

    bbox = results[0].get("boundingbox")
    if not bbox or len(bbox) != 4:
        raise GeocodeError(f"Nominatim returned no bounding box for: {query!r}")

    south, north, west, east = (float(v) for v in bbox)
    return south, west, north, east
