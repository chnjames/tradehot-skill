#!/usr/bin/env python3
"""Rule-based entity extraction for tradehot items.

This module enriches raw news/search/RSS items with business dimensions:
platforms, markets, categories, HS codes, item type, and risk level.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
SOURCES_DIR = ROOT / "sources"

HS_RE = re.compile(r"(?:\bHS(?:\s*Code)?\s*|税则号\s*)([0-9]{4,10})\b", re.IGNORECASE)

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "consumer electronics": ["consumer electronics", "electronics", "电子", "电器", "小家电"],
    "furniture": ["furniture", "家具", "家居", "home furniture", "office furniture"],
    "home storage": ["storage", "收纳", "home storage"],
    "pet products": ["pet", "pets", "宠物"],
    "beauty": ["beauty", "cosmetic", "cosmetics", "美妆", "个护"],
    "children products": ["children", "kids", "toy", "toys", "儿童", "玩具"],
    "textiles": ["textile", "textiles", "apparel", "garment", "服装", "纺织"],
    "outdoor": ["outdoor", "camping", "户外", "露营"],
    "food contact": ["food contact", "食品接触"],
}

MARKET_ALIASES: Dict[str, List[str]] = {
    "US": ["us", "u.s.", "usa", "united states", "america", "美国"],
    "EU": ["eu", "european union", "欧盟"],
    "UK": ["uk", "u.k.", "united kingdom", "britain", "英国"],
    "Southeast Asia": ["southeast asia", "东南亚"],
}

HIGH_RISK_KEYWORDS = [
    "sanction",
    "export control",
    "ban",
    "blocked",
    "seizure",
    "fine",
    "制裁",
    "出口管制",
    "封号",
    "扣货",
    "罚款",
    "禁令",
]
MEDIUM_RISK_KEYWORDS = [
    "tariff",
    "compliance",
    "certification",
    "delay",
    "freight rates",
    "关税",
    "合规",
    "认证",
    "延误",
    "运价",
]


def _load_json(filename: str) -> Dict[str, Any]:
    path = SOURCES_DIR / filename
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _append_unique(values: Iterable[str], additions: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen: Set[str] = set()
    for value in [*values, *additions]:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _text_for_item(item: Dict[str, object]) -> str:
    return " ".join(
        str(item.get(field, ""))
        for field in ["title", "summary", "evidence", "source_name"]
    ).lower()


def extract_platforms(text: str) -> List[str]:
    data = _load_json("platforms.json")
    platforms = []
    for platform in data.get("platforms", []):
        name = str(platform.get("name", ""))
        pid = str(platform.get("id", "")).replace("_", " ")
        aliases = {name.lower(), pid.lower()}
        if "shein" in name.lower():
            aliases.add("shein")
        if "walmart" in name.lower():
            aliases.add("walmart")
        if any(alias and alias in text for alias in aliases):
            platforms.append(name)
    return platforms


def extract_markets(text: str) -> List[str]:
    data = _load_json("markets.json")
    markets: List[str] = []
    for canonical, aliases in MARKET_ALIASES.items():
        if any(alias in text for alias in aliases):
            markets.append(canonical)
    for market in data.get("markets", []):
        name = str(market.get("name", ""))
        zh_name = str(market.get("zh_name", ""))
        aliases = [name.lower(), zh_name.lower()]
        if any(alias and alias in text for alias in aliases):
            markets.append(name)
    return _append_unique([], markets)


def extract_categories(text: str) -> List[str]:
    categories = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            categories.append(category)
    return categories


def extract_hs_codes(text: str) -> List[str]:
    codes = []
    for match in HS_RE.finditer(text):
        code = match.group(1)
        if len(code) >= 4:
            codes.append(code)
    return _append_unique([], codes)


def infer_type_from_entities(text: str, current_type: str = "general") -> str:
    if current_type and current_type != "general":
        return current_type
    if any(keyword in text for keyword in ["amazon", "tiktok", "shopee", "seller", "平台", "卖家"]):
        return "platform"
    if any(keyword in text for keyword in ["tariff", "关税", "anti-dumping", "反倾销"]):
        return "tariff"
    if any(keyword in text for keyword in ["freight", "shipping", "logistics", "物流", "运价", "港口"]):
        return "logistics"
    if any(keyword in text for keyword in ["policy", "regulation", "监管", "政策", "出口管制"]):
        return "policy"
    if any(keyword in text for keyword in ["data", "statistics", "trend", "数据", "趋势"]):
        return "data"
    return current_type or "general"


def infer_risk_from_entities(text: str, current_risk: str = "low") -> str:
    if any(keyword in text for keyword in HIGH_RISK_KEYWORDS):
        return "high"
    if any(keyword in text for keyword in MEDIUM_RISK_KEYWORDS):
        return "medium" if current_risk != "high" else current_risk
    return current_risk or "low"


def enrich_item(item: Dict[str, object]) -> Dict[str, object]:
    """Return a copy of item enriched with extracted entities."""
    enriched = dict(item)
    text = _text_for_item(enriched)
    enriched["platforms"] = _append_unique(enriched.get("platforms", []), extract_platforms(text))
    enriched["markets"] = _append_unique(enriched.get("markets", []), extract_markets(text))
    enriched["categories"] = _append_unique(enriched.get("categories", []), extract_categories(text))
    enriched["hs_codes"] = _append_unique(enriched.get("hs_codes", []), extract_hs_codes(text))
    enriched["type"] = infer_type_from_entities(text, str(enriched.get("type", "general")))
    enriched["risk_level"] = infer_risk_from_entities(text, str(enriched.get("risk_level", "low")))
    return enriched


def enrich_items(items: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    return [enrich_item(item) for item in items]


if __name__ == "__main__":
    sample = {
        "title": "TikTok Shop seller compliance update in the US for consumer electronics HS 8516",
        "summary": "Sellers should review certification requirements.",
    }
    print(json.dumps(enrich_item(sample), ensure_ascii=False, indent=2))
