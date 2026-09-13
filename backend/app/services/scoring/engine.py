"""Configurable website quality scoring engine (spec section 12).

Weights live in weights.json, not scattered through the code, so the
scoring model can be tuned without a redeploy of business logic.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


@lru_cache
def _load_weights() -> dict:
    settings = get_settings()
    path = Path(settings.SCORING_CONFIG_PATH)
    if not path.is_absolute():
        # Resolve relative to the backend/ directory (repo layout assumption).
        path = Path(__file__).resolve().parents[3] / settings.SCORING_CONFIG_PATH
    with open(path) as f:
        return json.load(f)


def score_website(facts: dict) -> dict:
    """Returns {"overall": int, "categories": {name: int}, "reasons": [...]}."""
    config = _load_weights()

    if not facts.get("reachable"):
        return {
            "overall": 0,
            "categories": {cat: 0 for cat in config["categories"]},
            "reasons": [{"label": "Website unreachable or not found", "points": 0}],
        }

    category_scores: dict[str, int] = {}
    reasons: list[dict] = []
    weighted_total = 0.0
    total_weight = 0

    no_http_errors = not facts.get("http_error_pages")
    pages_crawled_meets_minimum = facts.get("pages_crawled", 0) >= config.get(
        "min_pages_for_full_content_score", 3
    )
    derived = {
        **facts,
        "no_http_errors": no_http_errors,
        "pages_crawled_meets_minimum": pages_crawled_meets_minimum,
    }

    for category_name, category_cfg in config["categories"].items():
        checks = category_cfg["checks"]
        category_points = 0
        for check_name, points in checks.items():
            if derived.get(check_name):
                category_points += points
                reasons.append(
                    {"label": f"{category_name}: {check_name} present", "points": points}
                )
        category_points = min(category_points, 100)
        category_scores[category_name] = category_points
        weighted_total += category_points * category_cfg["weight"]
        total_weight += category_cfg["weight"]

    overall = round(weighted_total / total_weight) if total_weight else 0

    return {
        "overall": overall,
        "categories": category_scores,
        "reasons": reasons,
    }
