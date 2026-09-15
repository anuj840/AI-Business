"""Small shared helpers for the discovery module."""
from __future__ import annotations


def parse_csv_list(field: str) -> list[str]:
    """Splits a comma-separated field into individual trimmed terms, e.g.
    "Roofing, Plumbing, HVAC" -> ["Roofing", "Plumbing", "HVAC"], or
    "Houston, Austin" -> ["Houston", "Austin"]. Used for both multi-industry
    and multi-city discovery requests."""
    return [term.strip() for term in field.split(",") if term.strip()]
