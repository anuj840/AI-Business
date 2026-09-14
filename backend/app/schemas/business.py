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
