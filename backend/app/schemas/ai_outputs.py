"""Pydantic schemas that validate structured AI (LLM) output (spec section 18).

If the model returns invalid JSON or a shape mismatch, callers catch the
ValidationError, log it, and fall back gracefully — a bad AI response must
never crash a job or corrupt a prospect record (spec section 66).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AuditAIOutput(BaseModel):
    summary: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    ai_recommendations: list[str] = Field(default_factory=list)
    priority_next_steps: list[str] = Field(default_factory=list)


class OutreachAIOutput(BaseModel):
    subject: str
    body: str
