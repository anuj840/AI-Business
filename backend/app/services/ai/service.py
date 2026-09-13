"""AI task routing (spec section 17) + structured-output enforcement (section 18).

This is the single place application code calls into AI from. It knows
about task types and prompt templates; it does NOT know which concrete
provider is in use.
"""
from __future__ import annotations

from pydantic import BaseModel, ValidationError

from app.core.logging import get_logger
from app.services.ai.factory import get_ai_provider
from app.services.ai.json_utils import extract_json
from app.services.ai.provider import AIResponse

logger = get_logger(__name__)

AUDIT_SYSTEM_PROMPT = (
    "You are a precise, factual business analyst. You never fabricate information "
    "and always respond with strictly valid JSON when asked to."
)
OUTREACH_SYSTEM_PROMPT = (
    "You are a professional B2B copywriter who writes concise, honest, non-spammy "
    "outreach emails. You never fabricate claims and always respond with strictly "
    "valid JSON when asked to."
)

CORRECTION_SUFFIX = (
    "\n\nYour previous response was not valid JSON matching the required schema. "
    "Respond again with ONLY the corrected valid JSON object, nothing else."
)


async def generate_structured(
    *,
    system_prompt: str,
    user_prompt: str,
    schema: type[BaseModel],
    task_type: str,
) -> tuple[BaseModel | None, AIResponse]:
    """Calls the AI provider and validates the JSON response against `schema`.

    Retries once with a correction prompt if parsing/validation fails. Never
    raises — returns (None, response) on unrecoverable failure so callers can
    degrade gracefully instead of crashing a job.
    """
    provider = get_ai_provider()
    response = await provider.generate(system_prompt=system_prompt, user_prompt=user_prompt)

    parsed = _try_parse(response, schema, task_type)
    if parsed is not None:
        return parsed, response

    if not response.succeeded:
        return None, response

    logger.warning("ai.structured_output_retry", task_type=task_type)
    retry_response = await provider.generate(
        system_prompt=system_prompt, user_prompt=user_prompt + CORRECTION_SUFFIX
    )
    parsed = _try_parse(retry_response, schema, task_type)
    return parsed, retry_response


def _try_parse(response: AIResponse, schema: type[BaseModel], task_type: str) -> BaseModel | None:
    if not response.succeeded:
        logger.error("ai.provider_failed", task_type=task_type, error=response.error)
        return None

    data = extract_json(response.text)
    if data is None:
        logger.error("ai.json_parse_failed", task_type=task_type)
        return None

    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        logger.error("ai.schema_validation_failed", task_type=task_type, error=str(exc))
        return None
