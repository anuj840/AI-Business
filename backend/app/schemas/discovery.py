from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.business import BusinessOut


class DiscoveryRequest(BaseModel):
    country: str = Field(..., min_length=1)
    region: str | None = None
    city: str | None = None
    industry: str = Field(..., min_length=1, description="e.g. 'Roofing', 'Dental', 'Cafe'")
    max_results: int = Field(20, ge=1, le=50)


class DiscoveryResultOut(BaseModel):
    found: int
    created: int
    skipped_duplicates: int
    businesses: list[BusinessOut]
    source_error: str | None = None
