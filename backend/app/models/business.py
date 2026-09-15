"""Core models for the vertical slice.

Scope note: this is intentionally the minimal schema needed for
business + website + analysis + score + opportunity + audit + outreach
draft. Multi-tenant tables (organizations, campaigns, etc.) are deferred
to Phase 1/5 per the phased build-out — see ARCHITECTURE.md.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class WebsiteStatus(str, enum.Enum):
    WEBSITE_FOUND = "WEBSITE_FOUND"
    NO_WEBSITE_FOUND = "NO_WEBSITE_FOUND"
    WEBSITE_UNCERTAIN = "WEBSITE_UNCERTAIN"
    WEBSITE_UNAVAILABLE = "WEBSITE_UNAVAILABLE"


class OpportunityType(str, enum.Enum):
    NEW_WEBSITE = "NEW_WEBSITE"
    WEBSITE_REDESIGN = "WEBSITE_REDESIGN"
    WEBSITE_OPTIMIZATION = "WEBSITE_OPTIMIZATION"
    LEAD_CONVERSION = "LEAD_CONVERSION"
    AI_AUTOMATION = "AI_AUTOMATION"
    SEO_GROWTH = "SEO_GROWTH"
    OTHER_SERVICE = "OTHER_SERVICE"
    IGNORE = "IGNORE"


class DealStatus(str, enum.Enum):
    """Adapted from spec section 27's campaign-recipient states, scoped down
    to what makes sense before campaigns/email-sending exist (spec section
    58 explicitly defers those): a manual, per-business status the user
    sets themselves as they work a lead in the real world (sent an email
    through their own client, got a reply, closed the deal), rather than
    something a sending/reply-detection system updates automatically."""

    NEW = "NEW"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    CONVERTED = "CONVERTED"


# Terminal states: a lead here is done, one way or another -- excluded from
# the Hot Deals worklist (app/services/analytics/service.py) regardless of
# score, since there's nothing left to "work."
DEAL_STATUS_TERMINAL = {DealStatus.NOT_INTERESTED, DealStatus.DO_NOT_CONTACT, DealStatus.CONVERTED}


class Business(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Provenance for businesses created via the discovery engine (spec
    # section 8). Null for manually-entered businesses. A full
    # business_sources table (for multi-source provenance per business) is
    # deferred until there's a second source worth cross-referencing --
    # see app/services/discovery/dedup.py.
    source_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    deal_status: Mapped[DealStatus] = mapped_column(
        Enum(DealStatus, name="deal_status"), default=DealStatus.NEW, nullable=False
    )
    deal_status_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    website: Mapped["Website | None"] = relationship(
        back_populates="business", uselist=False, cascade="all, delete-orphan"
    )
    lead_score: Mapped["LeadScore | None"] = relationship(
        back_populates="business", uselist=False, cascade="all, delete-orphan"
    )
    opportunity: Mapped["Opportunity | None"] = relationship(
        back_populates="business", uselist=False, cascade="all, delete-orphan"
    )
    audit: Mapped["Audit | None"] = relationship(
        back_populates="business", uselist=False, cascade="all, delete-orphan"
    )
    outreach_draft: Mapped["OutreachDraft | None"] = relationship(
        back_populates="business", uselist=False, cascade="all, delete-orphan"
    )
    activities: Mapped[list["DealActivity"]] = relationship(
        back_populates="business",
        cascade="all, delete-orphan",
        order_by="DealActivity.created_at.desc()",
    )


class Website(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "websites"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), unique=True
    )
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[WebsiteStatus] = mapped_column(
        Enum(WebsiteStatus, name="website_status"), default=WebsiteStatus.WEBSITE_UNCERTAIN
    )
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)

    # Denormalized from facts.domain_age_years (app/services/domain_age/rdap.py)
    # so the businesses list can show/sort on it cheaply without extracting
    # it from the WebsiteAnalysis.facts JSON blob on every request.
    domain_age_years: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Raw crawl output kept for re-analysis without re-crawling.
    crawl_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    business: Mapped["Business"] = relationship(back_populates="website")
    analysis: Mapped["WebsiteAnalysis | None"] = relationship(
        back_populates="website", uselist=False, cascade="all, delete-orphan"
    )


class WebsiteAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Deterministic, rule-based facts about a website. No AI here — see AI-generated
    interpretation in Audit instead."""

    __tablename__ = "website_analysis"

    website_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id", ondelete="CASCADE"), unique=True
    )

    facts: Mapped[dict] = mapped_column(JSON, default=dict)
    """Structured deterministic facts, e.g. {"https": true, "has_contact_form": false, ...}"""

    website: Mapped["Website"] = relationship(back_populates="analysis")


class LeadScore(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_scores"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), unique=True
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    category_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    """List of {"label": str, "points": int} explaining the score, per spec section 14."""

    business: Mapped["Business"] = relationship(back_populates="lead_score")


class Opportunity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "opportunities"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), unique=True
    )
    opportunity_type: Mapped[OpportunityType] = mapped_column(
        Enum(OpportunityType, name="opportunity_type")
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    recommended_service: Mapped[str | None] = mapped_column(String(150), nullable=True)

    business: Mapped["Business"] = relationship(back_populates="opportunity")


class Audit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audits"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), unique=True
    )
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    """Structured report body. Every item is tagged kind: FACT | AI_INFERENCE | RECOMMENDATION."""
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    business: Mapped["Business"] = relationship(back_populates="audit")


class OutreachDraft(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "outreach_drafts"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), unique=True
    )
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(default=False)
    """Human approval gate per spec section 29 — never auto-sent."""
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    business: Mapped["Business"] = relationship(back_populates="outreach_draft")


class DealActivity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A timeline entry for a business -- a status change, a free-text
    note, or both together (e.g. "left a voicemail" + status -> CONTACTED).
    Spec section 35's "Notes ... Status ... Timeline" for the prospect
    detail page, scoped to manual entries since there's no
    campaigns/conversations system generating these automatically yet."""

    __tablename__ = "deal_activities"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE")
    )
    status: Mapped[DealStatus | None] = mapped_column(
        Enum(DealStatus, name="deal_status"), nullable=True
    )
    """Set only when this entry represents a status change; null for a
    plain note logged without changing the business's current status."""
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    business: Mapped["Business"] = relationship(back_populates="activities")
