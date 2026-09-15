"""API request/response schemas for the business/pipeline endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BusinessCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    website_url: str | None = Field(None, description="Business website URL, if known")
    country: str | None = None
    region: str | None = None
    city: str | None = None
    industry: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


class BusinessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    country: str | None
    region: str | None
    city: str | None
    industry: str | None
    phone: str | None
    email: str | None
    notes: str | None = None
    submitted_website_url: str | None
    created_at: datetime
    source_name: str | None = None
    discovered_at: datetime | None = None
    deal_status: str = "NEW"
    deal_status_updated_at: datetime | None = None


class DealStatusUpdate(BaseModel):
    status: str = Field(..., description="One of DealStatus's values, e.g. 'CONTACTED'")


class DealActivityCreate(BaseModel):
    note: str | None = Field(None, max_length=4000)
    status: str | None = Field(
        None, description="Optional -- set this alongside a note to also change status"
    )


class DealActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str | None
    note: str | None
    created_at: datetime


class BusinessListItemOut(BusinessOut):
    """BusinessOut plus a couple of fields worth showing at a glance in a
    list without opening each business -- kept separate from BusinessOut
    itself since those come from a plain Business row with no Website join
    (see GET /api/businesses/{id})."""

    domain_age_years: float | None = None


class PaginatedBusinessesOut(BaseModel):
    items: list[BusinessListItemOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class PipelineResultOut(BaseModel):
    business: BusinessOut
    website_status: str
    pages_crawled: int
    facts: dict
    quality_score: dict
    opportunity: dict
    lead_score: dict
    audit: dict
    outreach_draft: dict | None
