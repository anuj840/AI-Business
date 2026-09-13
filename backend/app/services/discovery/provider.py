"""Pluggable lead source abstraction (spec section 7).

Application code depends only on this interface, never on a concrete data
source. This keeps the door open to add licensed/paid providers (Google
Places, Yelp Fusion, etc.) later without touching the discovery service or
API routes -- only a new provider class + a config flag.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DiscoveryCriteria:
    country: str
    region: str | None = None
    city: str | None = None
    industry: str = ""
    max_results: int = 20


@dataclass
class DiscoveredBusiness:
    """One candidate business found by a source provider. Deliberately only
    carries publicly-published business contact fields (spec section 32) --
    never personal/private data."""

    name: str
    source_name: str
    source_ref: str
    website_url: str | None = None
    phone: str | None = None
    email: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class LeadSourceProvider(ABC):
    @abstractmethod
    async def discover(self, criteria: DiscoveryCriteria) -> list[DiscoveredBusiness]:
        """Find candidate businesses matching criteria. Must never raise for
        ordinary failures (no results, source unavailable) -- return an
        empty list and let the caller log/report, consistent with the
        never-crash-a-job rule (spec section 66)."""
        raise NotImplementedError
