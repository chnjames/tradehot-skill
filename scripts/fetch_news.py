#!/usr/bin/env python3
"""News fetcher for tradehot.

This module provides:
1. `sample_items()` — placeholder items for offline/demo use.
2. `build_search_queries()` — generates search query lists from sources/*.json
   so that an Agent can use them for WebSearch / WebFetch calls.
3. `load_user_config()` — loads optional user preferences from sources/user_config.json.
4. Simple file-based cache to avoid redundant fetches within the same day.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from item_cluster import cluster_items
from item_schema import normalize_items, validate_items
from source_connectors import parse_feed_items

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
SOURCES_DIR = ROOT / "sources"
CACHE_DIR = Path(
    os.environ.get(
        "TRADEHOT_CACHE_DIR",
        str(Path(tempfile.gettempdir()) / "tradehot-skill-cache"),
    )
)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    safe = hashlib.md5(key.encode()).hexdigest()[:12]
    return CACHE_DIR / f"{date.today().isoformat()}_{safe}.json"


def cache_get(key: str) -> Optional[List[Dict[str, object]]]:
    """Return cached items if they exist for today, else None."""
    p = _cache_path(key)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def cache_set(key: str, items: List[Dict[str, object]]) -> None:
    p = _cache_path(key)
    p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# User config
# ---------------------------------------------------------------------------
_user_config_cache: Optional[Dict[str, Any]] = None


def load_user_config() -> Dict[str, Any]:
    """Load user preferences from sources/user_config.json.

    Returns an empty dict if the file does not exist or cannot be parsed.
    The config can include:
      - user: {role, company_type, language}
      - focus_markets: list of market names
      - focus_platforms: list of platform names
      - focus_categories: list of category names
      - focus_hs_codes: list of HS codes
      - report_defaults: {daily_days, weekly_days, risk_days, top_n}
      - notifications: {high_risk_alert, tariff_change_alert, platform_policy_alert}
    """
    global _user_config_cache
    if _user_config_cache is not None:
        return _user_config_cache

    config_path = SOURCES_DIR / "user_config.json"
    if not config_path.exists():
        _user_config_cache = {}
        return _user_config_cache

    try:
        _user_config_cache = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _user_config_cache = {}
    return _user_config_cache


def filter_items_by_user_config(
    items: List[Dict[str, object]],
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, object]]:
    """Filter/rank items based on user_config.json preferences.

    Items matching focus_markets, focus_platforms, or focus_categories
    get a relevance boost. Items not matching any focus area are still
    included but sorted lower.
    """
    if config is None:
        config = load_user_config()

    focus_markets = {m.lower() for m in config.get("focus_markets", [])}
    focus_platforms = {p.lower() for p in config.get("focus_platforms", [])}
    focus_categories = {c.lower() for c in config.get("focus_categories", [])}

    def relevance(item: Dict[str, object]) -> int:
        score = 0
        markets = [str(m).lower() for m in item.get("markets", [])]
        platforms = [str(p).lower() for p in item.get("platforms", [])]
        categories = [str(c).lower() for c in item.get("categories", [])]
        if any(m in focus_markets for m in markets):
            score += 2
        if any(p in focus_platforms for p in platforms):
            score += 2
        if any(c in focus_categories for c in categories):
            score += 1
        return score

    return sorted(items, key=relevance, reverse=True)


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------
def dedup_items(items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Remove duplicate items based on title similarity."""
    seen_titles: set = set()
    result: List[Dict[str, object]] = []
    for item in items:
        title_key = str(item.get("title", "")).strip().lower()
        if title_key and title_key not in seen_titles:
            seen_titles.add(title_key)
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# External item loading / normalization
# ---------------------------------------------------------------------------
def load_items_file(path: str | Path) -> List[Dict[str, object]]:
    """Load tradehot items from a JSON file.

    Accepted formats:
      - [item, item]
      - {"items": [item, item]}
      - {"results": [search_result, search_result]}

    Search-style entries with `name`, `snippet`, and `link` are converted into
    tradehot's item schema so WebSearch/RSS/API exports can be normalized first
    and then passed into `generate_report.py --input`.
    """
    input_path = Path(path)
    if not input_path.exists() and not input_path.is_absolute():
        candidates = [
            Path.cwd() / input_path,
            SCRIPT_DIR / input_path,
            ROOT / input_path,
        ]
        input_path = next((candidate for candidate in candidates if candidate.exists()), input_path)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        raw_items = data
    elif isinstance(data, dict):
        raw_items = data.get("items") or data.get("results") or []
    else:
        raise ValueError(f"Unsupported JSON root in {input_path}")

    if not isinstance(raw_items, list):
        raise ValueError("JSON items/results must be a list")
    return [coerce_external_item(item) for item in raw_items if isinstance(item, dict)]


def coerce_external_item(raw: Dict[str, object]) -> Dict[str, object]:
    """Convert a generic search/API result into a tradehot item."""
    title = raw.get("title") or raw.get("name") or raw.get("headline") or ""
    summary = raw.get("summary") or raw.get("snippet") or raw.get("description") or ""
    url = raw.get("source_url") or raw.get("url") or raw.get("link") or ""
    source_name = raw.get("source_name") or raw.get("source") or raw.get("publisher") or ""
    published = raw.get("published_date") or raw.get("published_at") or raw.get("date") or str(date.today())

    item = dict(raw)
    item.update(
        {
            "title": title,
            "summary": summary,
            "url": url,
            "source_url": raw.get("source_url") or url,
            "source_name": source_name,
            "source": raw.get("source_tier") or raw.get("source") or "news",
            "source_tier": raw.get("source_tier") or raw.get("source") or "news",
            "published_date": str(published)[:10],
            "published_at": str(published),
            "retrieved_at": raw.get("retrieved_at") or str(date.today()),
            "type": raw.get("type") or infer_item_type(str(title), str(summary)),
            "risk_level": raw.get("risk_level") or infer_risk_level(str(title), str(summary)),
            "confidence": raw.get("confidence") or infer_confidence(raw),
            "evidence": raw.get("evidence") or summary,
        }
    )
    return item


def infer_item_type(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if any(key in text for key in ["tariff", "关税", "anti-dumping", "反倾销"]):
        return "tariff"
    if any(key in text for key in ["amazon", "tiktok", "shopee", "seller", "平台", "卖家"]):
        return "platform"
    if any(key in text for key in ["policy", "regulation", "监管", "政策", "export control", "出口管制"]):
        return "policy"
    if any(key in text for key in ["freight", "shipping", "logistics", "运价", "物流", "港口"]):
        return "logistics"
    if any(key in text for key in ["data", "statistics", "trend", "数据", "趋势"]):
        return "data"
    return "general"


def infer_risk_level(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if any(key in text for key in ["sanction", "制裁", "ban", "封号", "扣货", "罚款", "出口管制"]):
        return "high"
    if any(key in text for key in ["tariff", "关税", "compliance", "合规", "delay", "延误"]):
        return "medium"
    return "low"


def infer_confidence(raw: Dict[str, object]) -> int:
    tier = str(raw.get("source_tier") or raw.get("source") or "").lower()
    if tier in {"official", "platform_official", "official_data", "official_data_tool"}:
        return 80
    if tier in {"industry_media", "logistics_media", "news"}:
        return 55
    if raw.get("url") or raw.get("link") or raw.get("source_url"):
        return 45
    return 25


def normalize_external_items(path: str | Path) -> List[Dict[str, object]]:
    """Load, normalize, cluster, and validate external items."""
    items = normalize_items(load_items_file(path))
    items = cluster_items(items)
    errors = validate_items(items)
    if errors:
        raise ValueError("Invalid external items:\n" + "\n".join(errors))
    return items


def normalize_feed_source(
    location: str,
    source_name: Optional[str] = None,
    source_tier: str = "news",
) -> List[Dict[str, object]]:
    """Parse RSS/Atom, infer tradehot fields, cluster, and validate."""
    raw_items = [coerce_external_item(item) for item in parse_feed_items(location, source_name, source_tier)]
    items = normalize_items(raw_items)
    items = cluster_items(items)
    errors = validate_items(items)
    if errors:
        raise ValueError("Invalid feed items:\n" + "\n".join(errors))
    return items


def load_rss_sources(config_path: str | Path | None = None) -> List[Dict[str, Any]]:
    """Load enabled RSS/Atom source configs."""
    path = Path(config_path) if config_path else SOURCES_DIR / "rss_sources.json"
    if not path.exists() and not path.is_absolute():
        candidates = [Path.cwd() / path, SCRIPT_DIR / path, ROOT / path]
        path = next((candidate for candidate in candidates if candidate.exists()), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data.get("sources", []) if isinstance(data, dict) else []
    return [source for source in sources if source.get("enabled", True)]


def _resolve_source_location(location: str) -> str:
    """Resolve local feed paths relative to sources/ and project root."""
    if location.startswith(("http://", "https://")):
        return location
    path = Path(location)
    if path.is_absolute():
        return str(path)
    candidates = [
        SOURCES_DIR / path,
        ROOT / path,
        SCRIPT_DIR / path,
        Path.cwd() / path,
    ]
    return str(next((candidate for candidate in candidates if candidate.exists()), ROOT / path))


def collect_rss_sources(config_path: str | Path | None = None) -> Dict[str, object]:
    """Collect items from all enabled RSS/Atom sources in a config file."""
    collected: List[Dict[str, object]] = []
    errors: List[Dict[str, str]] = []
    for source in load_rss_sources(config_path):
        location = _resolve_source_location(str(source.get("url", "")))
        try:
            collected.extend(
                normalize_feed_source(
                    location,
                    source_name=str(source.get("name") or source.get("id") or location),
                    source_tier=str(source.get("source_tier") or source.get("type") or "news"),
                )
            )
        except Exception as exc:
            errors.append(
                {
                    "source": str(source.get("name") or source.get("id") or location),
                    "url": str(source.get("url", "")),
                    "error": str(exc),
                }
            )

    items = cluster_items(collected)
    errors.extend({"source": "validation", "url": "", "error": error} for error in validate_items(items))
    return {
        "items": items,
        "errors": errors,
        "stats": {
            "sources": len(load_rss_sources(config_path)),
            "items": len(items),
            "errors": len(errors),
        },
    }


# ---------------------------------------------------------------------------
# Source-driven search query builder
# ---------------------------------------------------------------------------
def build_search_queries(
    report_type: str = "daily",
    market: Optional[str] = None,
    platform: Optional[str] = None,
    hs_code: Optional[str] = None,
) -> Dict[str, List[str]]:
    """Generate search query suggestions grouped by report section.

    The Agent should use these queries with WebSearch / WebFetch to fill
    the report skeleton produced by generate_report.py.
    """
    from fetch_sources import load_all_sources

    sources = load_all_sources()
    platform_list = [p["name"] for p in sources.get("platforms", {}).get("platforms", [])]
    market_list = [
        m.get("zh_name", m["name"]) for m in sources.get("markets", {}).get("markets", [])[:10]
    ]

    queries: Dict[str, List[str]] = {}

    if report_type in ("daily", "weekly"):
        queries["政策与监管"] = [
            "海关总署 最新政策 外贸",
            "商务部 外贸政策 最新",
            "国家税务总局 出口退税 跨境电商",
            "贸促会 贸易促进 最新",
        ]
        queries["平台动态"] = [
            f"{p} seller policy update {date.today().year}" for p in platform_list[:5]
        ] + [
            "跨境电商 平台政策变化 最新",
        ]
        queries["数据与市场"] = [
            "global trade data latest",
            "外贸出口数据 最新",
            "cross-border ecommerce trends",
        ]
        queries["物流与供应链"] = [
            "国际海运运价 最新",
            "freight rates latest",
            "supply chain disruption",
        ]
        queries["风险预警"] = [
            "外贸风险预警 最新",
            "trade sanctions update",
            "跨境电商 合规风险",
        ]

    elif report_type == "platform" and platform:
        pname = platform.replace("_", " ").title() if "_" in platform else platform
        queries["平台动态"] = [
            f"{pname} seller policy update {date.today().year}",
            f"{pname} seller center announcement",
            f"{pname} 卖家政策 最新",
        ]
        queries["合规要求"] = [
            f"{pname} product compliance requirements",
            f"{pname} listing requirements update",
        ]

    elif report_type == "market" and market:
        queries["市场概况"] = [
            f"{market} import data latest",
            f"{market} 外贸 进口需求",
            f"{market} trade statistics",
        ]
        queries["关税与准入"] = [
            f"{market} tariff schedule",
            f"{market} import regulations",
        ]
        queries["平台机会"] = [
            f"{market} ecommerce market share",
            f"{market} cross-border ecommerce",
        ]

    elif report_type == "hs" and hs_code:
        queries["HS Code 数据"] = [
            f"HS code {hs_code} import data",
            f"HS {hs_code} trade statistics",
            f"UN Comtrade {hs_code}",
        ]
        queries["关税与准入"] = [
            f"HS {hs_code} tariff rates by country",
            f"ITC Market Access Map {hs_code}",
        ]
        queries["买家关键词"] = [
            f"HS {hs_code} importer directory",
            f"HS {hs_code} buyer keywords",
        ]

    elif report_type == "risk":
        queries["关税风险"] = [
            "关税变化 最新 外贸",
            "tariff changes latest trade",
        ]
        queries["贸易限制"] = [
            "trade sanctions update",
            "出口管制 最新",
        ]
        queries["物流风险"] = [
            "shipping disruption latest",
            "国际物流 风险 最新",
        ]

    elif report_type == "opportunity":
        queries["选品机会"] = [
            "外贸选品 热门品类",
            "cross-border ecommerce trending products",
            "Amazon trending products",
            "TikTok Shop trending products",
        ]
        queries["市场增长"] = [
            "fastest growing import categories",
            "emerging market import demand",
        ]

    return queries


# ---------------------------------------------------------------------------
# Sample / placeholder items (offline use)
# ---------------------------------------------------------------------------
def sample_items(days: int = 1, query: Optional[str] = None) -> List[Dict[str, object]]:
    """Return placeholder items for offline/demo use.

    In production, the Agent should replace these with data fetched via
    WebSearch using queries from `build_search_queries()`.
    """
    today = date.today()
    base_items: List[Dict[str, object]] = [
        {
            "title": "平台规则更新：部分类目合规要求变化",
            "summary": "需要检查商品资质、Listing 文案、材质声明和内容宣称。",
            "type": "platform",
            "source": "platform_official",
            "source_name": "平台官方公告",
            "source_tier": "platform_official",
            "source_url": "",
            "url": "",
            "published_date": str(today),
            "published_at": str(today),
            "retrieved_at": str(today),
            "markets": ["US", "EU", "Southeast Asia"],
            "platforms": ["Amazon", "TikTok Shop", "Shopee"],
            "categories": ["beauty", "consumer electronics", "home"],
            "hs_codes": [],
            "risk_level": "medium",
            "confidence": 65,
            "evidence": "平台规则类事件需要以 Seller Center 或官方公告最终核实。",
            "recommended_action": "检查 SKU、Listing、账号健康和平台公告",
        },
        {
            "title": "官方政策信号：跨境电商监管与出口退税需持续关注",
            "summary": "涉及 9610、9710、9810、海外仓、出口退税和申报材料。",
            "type": "policy",
            "source": "official",
            "source_name": "海关/税务/商务官方来源",
            "source_tier": "official",
            "source_url": "",
            "url": "",
            "published_date": str(today - timedelta(days=min(days, 1))),
            "published_at": str(today - timedelta(days=min(days, 1))),
            "retrieved_at": str(today),
            "markets": ["China", "Global"],
            "platforms": [],
            "categories": ["cross-border ecommerce", "overseas warehouse"],
            "hs_codes": [],
            "risk_level": "high",
            "confidence": 70,
            "evidence": "涉及出口退税和跨境监管的事项应以海关、税务、商务部门文件为准。",
            "recommended_action": "核查官方文件，更新报关/认证/税务资料",
        },
        {
            "title": "全球贸易数据：部分品类需求变化需要用 HS Code 验证",
            "summary": "建议用 UN Comtrade、WTO、ITC Trade Map 交叉验证目标市场需求。",
            "type": "data",
            "source": "official_data",
            "source_name": "WTO / UN Comtrade / ITC",
            "source_tier": "official_data",
            "source_url": "",
            "url": "",
            "published_date": str(today),
            "published_at": str(today),
            "retrieved_at": str(today),
            "markets": ["Global"],
            "platforms": [],
            "categories": ["all"],
            "hs_codes": [],
            "risk_level": "low",
            "confidence": 60,
            "evidence": "贸易数据类判断需用 HS Code、目标市场和时间窗口交叉验证。",
            "recommended_action": "用 HS Code 验证目标市场和竞争国",
        },
        {
            "title": "国际物流：部分航线运价波动，需更新报价有效期",
            "summary": "红海航线和跨太平洋航线运价近期波动，影响 FOB/CIF 报价。",
            "type": "logistics",
            "source": "logistics_media",
            "source_name": "物流行业媒体",
            "source_tier": "logistics_media",
            "source_url": "",
            "url": "",
            "published_date": str(today),
            "published_at": str(today),
            "retrieved_at": str(today),
            "markets": ["Global"],
            "platforms": [],
            "categories": ["all"],
            "hs_codes": [],
            "risk_level": "medium",
            "confidence": 55,
            "evidence": "物流价格和航线状态变化较快，报价前需再次确认货代报价和船期。",
            "recommended_action": "更新报价有效期和运输条款",
        },
        {
            "title": "关税变化：部分市场对中国商品加征关税政策持续调整",
            "summary": "美国、欧盟等市场对部分品类关税政策仍在调整中，需关注最新税则。",
            "type": "tariff",
            "source": "official",
            "source_name": "目标市场官方税则/贸易救济来源",
            "source_tier": "official",
            "source_url": "",
            "url": "",
            "published_date": str(today - timedelta(days=1)),
            "published_at": str(today - timedelta(days=1)),
            "retrieved_at": str(today),
            "markets": ["US", "EU"],
            "platforms": [],
            "categories": ["electronics", "furniture", "textiles"],
            "hs_codes": ["9403", "8516"],
            "risk_level": "high",
            "confidence": 70,
            "evidence": "关税变化应按目标国官方税则、贸易救济公告和产品 HS Code 逐项核实。",
            "recommended_action": "核查目标市场税则和客户报价条款",
        },
        {
            "title": "选品趋势：家居收纳和宠物用品在多个市场持续增长",
            "summary": "Google Trends 和平台搜索数据显示，家居收纳、宠物家具、宠物智能用品需求上升。",
            "type": "data",
            "source": "industry_media",
            "source_name": "行业媒体/趋势数据",
            "source_tier": "industry_media",
            "source_url": "",
            "url": "",
            "published_date": str(today),
            "published_at": str(today),
            "retrieved_at": str(today),
            "markets": ["US", "UK", "Germany", "Japan"],
            "platforms": ["Amazon", "TikTok Shop"],
            "categories": ["home storage", "pet products", "pet furniture"],
            "hs_codes": ["9403"],
            "risk_level": "low",
            "confidence": 50,
            "evidence": "选品趋势需用搜索趋势、平台榜单和进口数据共同验证，避免只看媒体热度。",
            "recommended_action": "用趋势数据和贸易数据交叉验证选品机会",
        },
    ]

    # Check cache first
    cache_key = f"sample_v2_{days}_{query or 'all'}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    if query:
        q = query.lower()
        result = [
            item for item in base_items
            if q in item["title"].lower() or q in item["summary"].lower()
        ]
    else:
        result = base_items

    cache_set(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    def emit_json(payload: object, output_path: str | None = None) -> None:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"Wrote items to {path}")
        else:
            print(text)

    parser = argparse.ArgumentParser(description="Fetch or query tradehot news.")
    parser.add_argument("--mode", choices=["items", "queries", "normalize", "rss", "rss-batch"], default="items")
    parser.add_argument("--type", default="daily")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--platform", default=None)
    parser.add_argument("--market", default=None)
    parser.add_argument("--hs-code", default=None)
    parser.add_argument("--query", default=None)
    parser.add_argument("--input", help="JSON file containing external items/search results.")
    parser.add_argument("--source-name", help="Source name for RSS/Atom mode.")
    parser.add_argument("--source-tier", default="news", help="Source tier for RSS/Atom mode.")
    parser.add_argument("--config", help="RSS/Atom source config path for rss-batch mode.")
    parser.add_argument("--output", help="Write JSON output to a file for normalize/rss/rss-batch modes.")
    args = parser.parse_args()

    if args.mode == "queries":
        queries = build_search_queries(
            report_type=args.type,
            market=args.market,
            platform=args.platform,
            hs_code=args.hs_code,
        )
        for section, qs in queries.items():
            print(f"\n## {section}")
            for q in qs:
                print(f"  - {q}")
    elif args.mode == "normalize":
        if not args.input:
            raise SystemExit("--input is required with --mode normalize")
        emit_json(normalize_external_items(args.input), args.output)
    elif args.mode == "rss":
        if not args.input:
            raise SystemExit("--input is required with --mode rss")
        emit_json(normalize_feed_source(args.input, args.source_name, args.source_tier), args.output)
    elif args.mode == "rss-batch":
        emit_json(collect_rss_sources(args.config), args.output)
    else:
        for item in sample_items(days=args.days, query=args.query):
            print(f"- [{item.get('type')}] {item['title']} (hot: pending)")
