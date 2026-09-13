"""Business deduplication (spec section 8).

Single-source for now (OpenStreetMap only), so this compares discovered
candidates against existing Business rows using normalized name + city, or
an exact phone match. When a second source is added, this is the place to
also cross-reference by source_ref/domain per business_sources -- deferred
until there's a second source to actually dedupe against.
"""
from __future__ import annotations

import re

_SUFFIX_RE = re.compile(
    r"\b(llc|inc|co|corp|company|ltd|limited)\b\.?", flags=re.IGNORECASE
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str) -> str:
    stripped = _SUFFIX_RE.sub("", name.lower())
    return _NON_ALNUM_RE.sub("", stripped).strip()


def is_duplicate(
    candidate_name: str,
    candidate_city: str | None,
    candidate_phone: str | None,
    existing: list[tuple[str, str | None, str | None]],
) -> bool:
    """`existing` is a list of (name, city, phone) tuples already in the DB."""
    norm_candidate = normalize_name(candidate_name)

    for existing_name, existing_city, existing_phone in existing:
        if candidate_phone and existing_phone and candidate_phone == existing_phone:
            return True
        if normalize_name(existing_name) == norm_candidate and (
            not candidate_city or not existing_city or candidate_city == existing_city
        ):
            return True

    return False
