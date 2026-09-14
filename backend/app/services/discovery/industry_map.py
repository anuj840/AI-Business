"""Maps a free-text industry label to OpenStreetMap tags.

OSM has no single "industry" field -- businesses are tagged with one of
several keys (shop=, amenity=, craft=, office=, leisure=) depending on
category. This is a curated map for common small-business categories; if
nothing matches, the caller falls back to a generic name-keyword search
(see osm_provider.py) so an unmapped industry still returns *something*
rather than nothing, at the cost of precision.

Extend this dict as real usage reveals more industries worth mapping
precisely -- do not try to enumerate all of OSM's taxonomy up front.
"""
from __future__ import annotations

# label (lowercased, matched by substring) -> list of (osm_key, osm_value)
INDUSTRY_TAG_MAP: dict[str, list[tuple[str, str]]] = {
    "roofing": [("craft", "roofer")],
    "roofer": [("craft", "roofer")],
    "plumbing": [("craft", "plumber")],
    "plumber": [("craft", "plumber")],
    "electrician": [("craft", "electrician")],
    "electrical": [("craft", "electrician")],
    "hvac": [("craft", "hvac")],
    "painter": [("craft", "painter")],
    "painting": [("craft", "painter")],
    "carpenter": [("craft", "carpenter")],
    "landscaping": [("craft", "gardener"), ("shop", "garden_centre")],
    "auto repair": [("shop", "car_repair")],
    "car repair": [("shop", "car_repair")],
    "mechanic": [("shop", "car_repair")],
    "dental": [("amenity", "dentist")],
    "dentist": [("amenity", "dentist")],
    "med spa": [("shop", "beauty"), ("leisure", "spa")],
    "medspa": [("shop", "beauty"), ("leisure", "spa")],
    "spa": [("leisure", "spa"), ("shop", "beauty")],
    "salon": [("shop", "hairdresser"), ("shop", "beauty")],
    "hair": [("shop", "hairdresser")],
    "restaurant": [("amenity", "restaurant")],
    "cafe": [("amenity", "cafe")],
    "coffee": [("amenity", "cafe")],
    "bakery": [("shop", "bakery")],
    "marketing agency": [("office", "advertising_agency")],
    "advertising": [("office", "advertising_agency")],
    "law firm": [("office", "lawyer")],
    "lawyer": [("office", "lawyer")],
    "accounting": [("office", "accountant")],
    "accountant": [("office", "accountant")],
    "real estate": [("office", "estate_agent")],
    "insurance": [("office", "insurance")],
    "gym": [("leisure", "fitness_centre")],
    "fitness": [("leisure", "fitness_centre")],
    "pet grooming": [("shop", "pet_grooming")],
    "veterinary": [("amenity", "veterinary")],
    "vet": [("amenity", "veterinary")],
    "cleaning": [("shop", "laundry")],
    "locksmith": [("craft", "locksmith")],
    "photography": [("craft", "photographer")],
    "photographer": [("craft", "photographer")],
}


def resolve_tags(industry: str) -> list[tuple[str, str]] | None:
    """Returns a list of (key, value) OSM tag pairs for a known industry, or
    None if nothing matches (caller should fall back to keyword search)."""
    industry_lower = industry.strip().lower()
    for label, tags in INDUSTRY_TAG_MAP.items():
        if label in industry_lower or industry_lower in label:
            return tags
    return None


def split_industries(industry_field: str) -> list[str]:
    """Splits a comma-separated industry field into individual terms,
    e.g. "Roofing, Plumbing, HVAC" -> ["Roofing", "Plumbing", "HVAC"]."""
    return [term.strip() for term in industry_field.split(",") if term.strip()]


def label_from_osm_tags(tags: dict) -> str | None:
    """Derives a human-readable category label directly from a result's own
    OSM tags -- e.g. {"craft": "roofer"} -> "Roofer". Used to tag each
    discovered business with the specific category it actually matched,
    which matters once a search can span multiple requested industries at
    once."""
    for key in ("craft", "amenity", "shop", "office", "leisure"):
        value = tags.get(key)
        if value:
            return value.replace("_", " ").title()
    return None
