#!/usr/bin/env python3
"""Shared item schema and validation helpers for tradehot.

The scripts keep backwards compatibility with the first prototype fields while
adding evidence and confidence fields needed for source-traceable reports.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Iterable, List, Tuple

from entity_extractor import enrich_item

LIST_FIELDS = ["markets", "platforms", "categories", "hs_codes"]
VALID_RISK_LEVELS = {"low", "medium", "high"}
VALID_SOURCE_TIERS = {
    "official",
    "platform_official",
    "official_data",
    "official_data_tool",
    "official_finance",
    "official_industry",
    "media",
    "industry_media",
    "logistics_media",
    "news",
    "social",
    "forum",
    "unknown",
}


DEFAULT_ITEM = {
    "title": "",
    "summary": "",
    "type": "general",
    "source": "",
    "source_name": "",
    "source_url": "",
    "source_tier": "unknown",
    "url": "",
    "published_date": str(date.today()),
    "published_at": "",
    "retrieved_at": "",
    "markets": [],
    "platforms": [],
    "categories": [],
    "hs_codes": [],
    "risk_level": "low",
    "confidence": 0,
    "evidence": "",
    "recommended_action": "",
}


def _as_list(value: object) -> List[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, str):
        return [value] if value else []
    return [value]


def normalize_item(raw: Dict[str, object]) -> Dict[str, object]:
    """Return an item with all schema fields present.

    Old fields are preserved. `source`, `url`, and `published_date` remain the
    compatibility fields used by the original scoring model.
    """
    item = dict(DEFAULT_ITEM)
    item.update({k: v for k, v in raw.items() if v is not None})

    for field in LIST_FIELDS:
        item[field] = [str(x) for x in _as_list(item.get(field))]

    source = str(item.get("source") or "")
    source_tier = str(item.get("source_tier") or "")
    if source and source_tier == "unknown":
        item["source_tier"] = source
    if not item.get("source") and item.get("source_tier"):
        item["source"] = item["source_tier"]

    if item.get("source_url") and not item.get("url"):
        item["url"] = item["source_url"]
    if item.get("url") and not item.get("source_url"):
        item["source_url"] = item["url"]

    if item.get("published_at") and not item.get("published_date"):
        item["published_date"] = str(item["published_at"])[:10]
    if item.get("published_date") and not item.get("published_at"):
        item["published_at"] = str(item["published_date"])

    if not item.get("retrieved_at"):
        item["retrieved_at"] = str(date.today())

    try:
        confidence = int(item.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0
    item["confidence"] = max(0, min(100, confidence))

    risk_level = str(item.get("risk_level", "low")).lower()
    item["risk_level"] = risk_level if risk_level in VALID_RISK_LEVELS else "low"

    source_tier = str(item.get("source_tier", "unknown")).lower()
    item["source_tier"] = source_tier if source_tier in VALID_SOURCE_TIERS else "unknown"
    return enrich_item(item)


def normalize_items(raw_items: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    return [normalize_item(item) for item in raw_items]


def _valid_iso_date(value: object) -> bool:
    if not value:
        return False
    try:
        datetime.fromisoformat(str(value)[:10])
    except ValueError:
        return False
    return True


def validate_item(item: Dict[str, object]) -> Tuple[bool, List[str]]:
    """Validate one normalized item and return `(ok, errors)`."""
    errors: List[str] = []
    if not str(item.get("title", "")).strip():
        errors.append("title is required")
    if not str(item.get("summary", "")).strip():
        errors.append("summary is required")
    if not str(item.get("type", "")).strip():
        errors.append("type is required")
    if not str(item.get("source", "")).strip():
        errors.append("source is required")
    if not _valid_iso_date(item.get("published_date")):
        errors.append("published_date must be ISO-like YYYY-MM-DD")
    if item.get("risk_level") not in VALID_RISK_LEVELS:
        errors.append("risk_level must be low, medium, or high")
    if item.get("source_tier") not in VALID_SOURCE_TIERS:
        errors.append("source_tier is unknown")
    if not isinstance(item.get("confidence"), int):
        errors.append("confidence must be an integer from 0 to 100")
    for field in LIST_FIELDS:
        if not isinstance(item.get(field), list):
            errors.append(f"{field} must be a list")
    return not errors, errors


def validate_items(items: Iterable[Dict[str, object]]) -> List[str]:
    """Return validation errors for a list of items."""
    errors: List[str] = []
    for idx, item in enumerate(items, start=1):
        ok, item_errors = validate_item(item)
        if not ok:
            errors.extend(f"item {idx}: {error}" for error in item_errors)
    return errors
