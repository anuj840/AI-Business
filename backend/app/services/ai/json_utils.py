"""Safe JSON extraction/parsing from raw LLM text output."""
from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict | None:
    """Best-effort extraction of a JSON object from LLM text output."""
    if not text:
        return None

    candidates = []
    fence_match = _FENCE_RE.search(text)
    if fence_match:
        candidates.append(fence_match.group(1))
    candidates.append(text)

    # Fallback: take the substring between the first '{' and the last '}'.
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(text[first_brace : last_brace + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate.strip())
        except (json.JSONDecodeError, AttributeError):
            continue
    return None
