#!/usr/bin/env python3
"""Ranking helpers for tradehot items.

Scoring model (0-25 total):
  freshness     (0-5) — how recent
  authority     (0-5) — source credibility
  business_impact (0-5) — effect on business
  actionability (0-5) — can the reader act on it
  risk          (0-5) — risk severity
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List

# ---------------------------------------------------------------------------
# Source authority weights (0-5)
# ---------------------------------------------------------------------------
SOURCE_WEIGHT: Dict[str, int] = {
    # Official government / international org
    "official": 5,
    "official_data": 5,
    "official_data_tool": 5,
    "official_finance": 5,
    "official_industry": 4,
    "customs_tax_mofcom": 5,
    # Platform official
    "platform_official": 5,
    # Industry / trade media
    "industry_media": 3,
    "logistics_media": 3,
    # General news
    "news": 3,
    # Social / forum (low trust)
    "social": 1,
    "forum": 1,
}

# ---------------------------------------------------------------------------
# Type → business impact weight (0-5)
# ---------------------------------------------------------------------------
TYPE_IMPACT: Dict[str, int] = {
    "policy": 5,
    "tariff": 5,
    "compliance": 5,
    "platform": 4,
    "logistics": 4,
    "data": 3,
    "market": 3,
    "general": 1,
}

# ---------------------------------------------------------------------------
# Risk level → score (0-5)
# ---------------------------------------------------------------------------
RISK_WEIGHT: Dict[str, int] = {
    "low": 1,
    "medium": 3,
    "high": 5,
}


# ---------------------------------------------------------------------------
# Individual scoring functions — each returns 0-5
# ---------------------------------------------------------------------------
def freshness_score(published_date: str) -> int:
    """0 = no date / very old, 5 = today."""
    if not published_date:
        return 0
    try:
        dt = datetime.fromisoformat(published_date).date()
    except ValueError:
        return 0
    delta = (date.today() - dt).days
    if delta < 0:
        delta = 0
    if delta <= 1:
        return 5
    if delta <= 3:
        return 4
    if delta <= 7:
        return 3
    if delta <= 30:
        return 2
    return 1


def authority_score(source: str) -> int:
    """0 = unknown source, 5 = official / platform official."""
    if not source:
        return 0
    return SOURCE_WEIGHT.get(source, 2)


def business_impact_score(item_type: str) -> int:
    """0 = no type, 5 = critical impact (policy/tariff/compliance)."""
    if not item_type:
        return 0
    return TYPE_IMPACT.get(item_type, 1)


def actionability_score(item: Dict[str, object]) -> int:
    """0-5 based on how many actionable dimensions are present.

    Dimensions: has specific markets, platforms, categories, and a clear type.
    """
    score = 0
    if item.get("markets"):
        score += 1
    if item.get("platforms"):
        score += 1
    if item.get("categories"):
        score += 1
    item_type = str(item.get("type", ""))
    if item_type and item_type != "general":
        score += 1
    if item.get("summary") and len(str(item["summary"])) > 30:
        score += 1
    return min(5, score)


def risk_score(risk_level: str) -> int:
    """0 = no risk info, 5 = high risk."""
    if not risk_level:
        return 0
    return RISK_WEIGHT.get(risk_level, 0)


# ---------------------------------------------------------------------------
# Composite scoring
# ---------------------------------------------------------------------------
def score_item(item: Dict[str, object]) -> int:
    """Calculate total hot score (0-25)."""
    return (
        freshness_score(str(item.get("published_date", "")))
        + authority_score(str(item.get("source", "")))
        + business_impact_score(str(item.get("type", "")))
        + actionability_score(item)
        + risk_score(str(item.get("risk_level", "")))
    )


def rank_items(items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Score and sort items by hot_score descending."""
    ranked = []
    for item in items:
        copied = dict(item)
        copied["hot_score"] = score_item(copied)
        ranked.append(copied)
    return sorted(ranked, key=lambda x: int(x.get("hot_score", 0)), reverse=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from fetch_news import sample_items

    for item in rank_items(sample_items()):
        print(f"[{item['hot_score']:2d}/25] {item['title']}")
