from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.business import BusinessOut


class DiscoveryRequest(BaseModel):
    country: str = Field(..., min_length=1)
    region: str | None = None
    city: str | None = Field(
        None,
        description=(
            "One or more cities, comma-separated, e.g. 'Houston' or "
            "'Houston, Austin, Dallas' (max 10 per run). Omit entirely to "
            "search the whole region/state at once for more volume per run."
        ),
    )
    industry: str = Field(
        ...,
        min_length=1,
        description=(
            "One or more industries, comma-separated, e.g. 'Roofing' or "
            "'Roofing, Plumbing, HVAC'."
        ),
    )
    max_results: int = Field(
        20, ge=1, le=200, description="Applies per city, not to the combined total."
    )


class DiscoveryResultOut(BaseModel):
    found: int
    created: int
    skipped_duplicates: int
    businesses: list[BusinessOut]
    source_error: str | None = None
