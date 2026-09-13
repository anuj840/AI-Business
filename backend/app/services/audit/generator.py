"""Website audit report generator (spec section 20).

Every item in the resulting report is tagged with its kind so the
frontend/report can visually distinguish:

  FACT            -> deterministic, verified by our own tools
  AI_INFERENCE    -> AI-generated interpretation/observation
  RECOMMENDATION  -> AI-generated suggested action

If the AI call fails or returns invalid output, the report still contains
the FACT section (from deterministic analysis) — a failed AI step must
never take down the whole audit (spec section 66).
"""
from __future__ import annotations

import json

from app.models.business import OpportunityType
from app.prompts.loader import render_prompt
from app.schemas.ai_outputs import AuditAIOutput
from app.services.ai.service import AUDIT_SYSTEM_PROMPT, generate_structured

PROMPT_VERSION = "v1"


async def generate_audit(
    *,
    business_name: str,
    industry: str | None,
    location: str,
    facts: dict,
    quality_score: dict,
    opportunity: dict,
) -> dict:
    fact_items = [{"kind": "FACT", "label": k, "value": v} for k, v in facts.items()]

    user_prompt = render_prompt(
        "audit_generation",
        PROMPT_VERSION,
        business_name=business_name,
        industry=industry or "Unknown",
        location=location or "Unknown",
        facts_json=json.dumps(facts, default=str),
        quality_score=quality_score.get("overall", 0),
        category_scores_json=json.dumps(quality_score.get("categories", {})),
        opportunity_type=opportunity["type"].value
        if isinstance(opportunity["type"], OpportunityType)
        else opportunity["type"],
        opportunity_reasons="; ".join(opportunity.get("reasons", [])),
    )

    parsed, ai_response = await generate_structured(
        system_prompt=AUDIT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=AuditAIOutput,
        task_type="AUDIT_GENERATION",
    )

    ai_items: list[dict] = []
    if parsed is not None:
        assert isinstance(parsed, AuditAIOutput)
        ai_items.extend(
            {"kind": "AI_INFERENCE", "label": "strength", "value": s} for s in parsed.strengths
        )
        ai_items.extend(
            {"kind": "AI_INFERENCE", "label": "weakness", "value": w} for w in parsed.weaknesses
        )
        ai_items.extend(
            {"kind": "RECOMMENDATION", "label": "recommendation", "value": r}
            for r in parsed.ai_recommendations
        )
        summary = parsed.summary
        next_steps = parsed.priority_next_steps
    else:
        summary = (
            "AI-generated summary unavailable for this audit. Facts below are "
            "verified and safe to rely on; recommendations require manual review."
        )
        next_steps = []

    return {
        "summary": summary,
        "website_score": quality_score.get("overall", 0),
        "category_scores": quality_score.get("categories", {}),
        "opportunity": {
            "type": opportunity["type"].value
            if isinstance(opportunity["type"], OpportunityType)
            else opportunity["type"],
            "confidence": opportunity.get("confidence"),
            "reasons": opportunity.get("reasons", []),
            "recommended_service": opportunity.get("recommended_service"),
        },
        "items": fact_items + ai_items,
        "priority_next_steps": next_steps,
        "ai_generation_succeeded": parsed is not None,
        "ai_model": ai_response.model,
    }
