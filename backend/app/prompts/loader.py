"""Versioned prompt template loader (spec section 19).

Prompts are plain text files under app/prompts/<task_type>/vN.txt so they
can be improved without touching Python code. `{{variable}}` placeholders
are filled with str.format-style substitution (double braces to avoid
clashing with any literal single braces in prompt text).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


@lru_cache
def _read_template(task_type: str, version: str) -> str:
    path = PROMPTS_DIR / task_type / f"{version}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text()


def render_prompt(task_type: str, version: str, **variables: str) -> str:
    template = _read_template(task_type, version)
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered
