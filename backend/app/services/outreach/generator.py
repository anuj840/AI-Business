"""Personalized outreach draft generator (spec section 26).

Drafts are always personalized off real collected facts and always require
human approval before send (section 29) — this module only ever produces a
DRAFT, it never sends anything.
"""
from __future__ import annotations

from app.models.business import OpportunityType
from app.prompts.loader import render_prompt
from app.schemas.ai_outputs import OutreachAIOutput
from app.services.ai.service import OUTREACH_SYSTEM_PROMPT, generate_structured

PROMPT_VERSION = "v1"

_FALLBACK_SUBJECT = "Quick observation about {business_name}'s online presence"
_FALLBACK_BODY = (
    "Hi {business_name} team,\n\n"
    "I took a look at your business's online presence and had a specific idea "
    "worth sharing — happy to send details if useful.\n\n"
    "No pressure either way, and feel free to reply STOP to opt out.\n\n"
    "Best,\nThe Team"
)


def _summarize_facts(facts: dict) -> str:
    highlights = []
    if facts.get("reachable") is False:
        return "No confirmed website found."
    if not facts.get("has_contact_form"):
        highlights.append("no contact form detected")
    if not facts.get("has_booking_system"):
        highlights.append("no online booking detected")
    if not facts.get("has_chat_widget"):
        highlights.append("no chat/instant-response widget detected")
    if not facts.get("has_meta_description"):
        highlights.append("missing meta description (SEO)")
    if facts.get("has_social_presence"):
        highlights.append("active social presence")
    return "; ".join(highlights) if highlights else "generally solid technical baseline"


async def generate_outreach_draft(
    *,
    business_name: str,
    industry: str | None,
    location: str,
    facts: dict,
    opportunity: dict,
) -> dict:
    opportunity_type = (
        opportunity["type"].value
        if isinstance(opportunity["type"], OpportunityType)
        else opportunity["type"]
    )

    user_prompt = render_prompt(
        "outreach",
        PROMPT_VERSION,
        business_name=business_name,
        industry=industry or "Unknown",
        location=location or "Unknown",
        opportunity_type=opportunity_type,
        opportunity_reasons="; ".join(opportunity.get("reasons", [])),
        recommended_service=opportunity.get("recommended_service") or "N/A",
        facts_summary=_summarize_facts(facts),
    )

    parsed, ai_response = await generate_structured(
        system_prompt=OUTREACH_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=OutreachAIOutput,
        task_type="OUTREACH_DRAFT",
    )

    if parsed is not None:
        assert isinstance(parsed, OutreachAIOutput)
        return {
            "subject": parsed.subject,
            "body": parsed.body,
            "ai_generation_succeeded": True,
            "ai_model": ai_response.model,
            "requires_human_approval": True,
        }

    return {
        "subject": _FALLBACK_SUBJECT.format(business_name=business_name),
        "body": _FALLBACK_BODY.format(business_name=business_name),
        "ai_generation_succeeded": False,
        "ai_model": ai_response.model,
        "requires_human_approval": True,
    }
