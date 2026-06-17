#!/usr/bin/env python3
"""Comprehensive test suite for tradehot scripts."""
import sys
import json
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, ".")
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
SOURCES_DIR = ROOT_DIR / "sources"

PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}")

print("=" * 60)
print("TRADEHOT TEST SUITE")
print("=" * 60)

# ── Test 1: Scoring model boundaries ──
print("\n## Test 1: Scoring Model")
from rank_items import (
    score_item, freshness_score, authority_score,
    business_impact_score, actionability_score, risk_score, rank_items
)

empty = {"title": "", "type": "", "source": "", "published_date": "",
         "risk_level": "", "markets": [], "platforms": [], "categories": []}
check("Empty item scores 0", score_item(empty) == 0)

perfect = {"title": "X", "type": "policy", "source": "official",
           "published_date": str(date.today()), "risk_level": "high",
           "markets": ["US"], "platforms": ["Amazon"], "categories": ["tech"],
           "summary": "A very detailed summary with more than thirty chars"}
check("Perfect item scores 25", score_item(perfect) == 25)

check("freshness('') == 0", freshness_score("") == 0)
check("freshness(today) == 5", freshness_score(str(date.today())) == 5)
check("freshness(3d ago) == 4", freshness_score(str(date.today() - timedelta(days=3))) == 4)
check("freshness(7d ago) == 3", freshness_score(str(date.today() - timedelta(days=7))) == 3)
check("freshness(30d ago) == 2", freshness_score(str(date.today() - timedelta(days=30))) == 2)
check("freshness(60d ago) == 1", freshness_score(str(date.today() - timedelta(days=60))) == 1)
check("freshness('invalid') == 0", freshness_score("not-a-date") == 0)

check("authority('') == 0", authority_score("") == 0)
check("authority('official') == 5", authority_score("official") == 5)
check("authority('platform_official') == 5", authority_score("platform_official") == 5)
check("authority('industry_media') == 3", authority_score("industry_media") == 3)
check("authority('social') == 1", authority_score("social") == 1)
check("authority('unknown_src') == 2", authority_score("unknown_src") == 2)

check("impact('policy') == 5", business_impact_score("policy") == 5)
check("impact('tariff') == 5", business_impact_score("tariff") == 5)
check("impact('platform') == 4", business_impact_score("platform") == 4)
check("impact('data') == 3", business_impact_score("data") == 3)
check("impact('') == 0", business_impact_score("") == 0)

check("risk('high') == 5", risk_score("high") == 5)
check("risk('medium') == 3", risk_score("medium") == 3)
check("risk('low') == 1", risk_score("low") == 1)
check("risk('') == 0", risk_score("") == 0)

# ── Test 2: Dedup ──
print("\n## Test 2: Dedup")
from fetch_news import dedup_items

dupes = [
    {"title": "Alpha", "type": "x"},
    {"title": "alpha", "type": "y"},
    {"title": "Beta", "type": "z"},
    {"title": "Alpha", "type": "w"},
]
result = dedup_items(dupes)
check("Dedup 4->2 (case-insensitive)", len(result) == 2)
check("Keeps first occurrence", result[0]["type"] == "x")

empty_title = [{"title": "", "type": "a"}, {"title": "", "type": "b"}]
check("Empty titles filtered out", len(dedup_items(empty_title)) == 0)

# ── Test 3: Cache ──
print("\n## Test 3: Cache")
from fetch_news import cache_set, cache_get

cache_set("test_suite", [{"title": "cached_item"}])
got = cache_get("test_suite")
check("Cache set/get works", got is not None and len(got) == 1)
check("Cache returns correct data", got[0]["title"] == "cached_item")

miss = cache_get("nonexistent_key_abc123xyz")
check("Cache miss returns None", miss is None)

# ── Test 4: Normalize ──
print("\n## Test 4: Normalize")
from normalize_items import normalize_item, normalize_items

raw = {"title": "Test", "markets": "US"}
normalized = normalize_item(raw)
check("String market -> list", isinstance(normalized["markets"], list))
check("Default fields filled", "type" in normalized and "source" in normalized)

raw_none = {"title": "T", "platforms": None}
n2 = normalize_item(raw_none)
check("None platforms -> []", n2["platforms"] == [])

batch = normalize_items([{"title": "A"}, {"title": "B"}])
check("Batch normalize", len(batch) == 2)

# ── Test 5: Fetch sources ──
print("\n## Test 5: Fetch Sources")
from fetch_sources import load_all_sources, flatten_sources

sources = load_all_sources()
check("Has zh sources", "zh" in sources and len(sources["zh"]["sources"]) > 0)
check("Has en sources", "en" in sources and len(sources["en"]["sources"]) > 0)
check("Has platforms", "platforms" in sources and len(sources["platforms"]["platforms"]) == 11)
check("Has markets", "markets" in sources and len(sources["markets"]["markets"]) >= 36)

flat = flatten_sources()
check("Flatten includes all sources", len(flat) > 20)
check("Platforms are in flatten", any(s["type"] == "platform_official" for s in flat))

# Knowledge-base files
check("Has tariff_reference", "tariff_reference" in sources and len(sources["tariff_reference"].get("entries", [])) > 0)
check("Has trade_calendar", "trade_calendar" in sources and len(sources["trade_calendar"].get("events", [])) > 0)
check("Has competitors", "competitors" in sources and len(sources["competitors"].get("competitors", [])) > 0)
check("Has logistics_hotspots", "logistics_hotspots" in sources and len(sources["logistics_hotspots"].get("hotspots", [])) > 0)
check("Has fx_risk", "fx_risk" in sources and len(sources["fx_risk"].get("high_volatility_currencies", [])) > 0)
check("tariff entries have markets", all("markets" in e for e in sources["tariff_reference"]["entries"][:3]))
check("calendar events have date", all("date" in e for e in sources["trade_calendar"]["events"][:3]))
check("competitors have country", all("country" in c for c in sources["competitors"]["competitors"][:3]))

# ── Test 6: Build search queries ──
print("\n## Test 6: Search Queries")
from fetch_news import build_search_queries

q_daily = build_search_queries("daily")
check("Daily has sections", len(q_daily) >= 4)
check("Daily has policy queries", "政策与监管" in q_daily)

q_platform = build_search_queries("platform", platform="TikTok Shop")
check("Platform queries generated", len(q_platform) > 0)

q_market = build_search_queries("market", market="India")
check("Market queries generated", len(q_market) > 0)
check("Market queries contain market name",
      any("India" in q for qs in q_market.values() for q in qs))

q_hs = build_search_queries("hs", hs_code="4202")
check("HS queries contain code", any("4202" in q for qs in q_hs.values() for q in qs))

q_risk = build_search_queries("risk")
check("Risk queries generated", len(q_risk) > 0)

q_opp = build_search_queries("opportunity")
check("Opportunity queries generated", len(q_opp) > 0)

# Tariff queries
q_tariff = build_search_queries("tariff", market="US", category="furniture")
check("Tariff queries generated", len(q_tariff) > 0)
check("Tariff has tariff section", "关税查询" in q_tariff)
check("Tariff has trade remedy section", "贸易救济" in q_tariff)
check("Tariff queries contain category", any("furniture" in q for qs in q_tariff.values() for q in qs))

# Calendar queries
q_cal = build_search_queries("calendar")
check("Calendar queries generated", len(q_cal) > 0)
check("Calendar has exhibition section", "展会信息" in q_cal)
check("Calendar has promo section", "大促日历" in q_cal)

# Competitor monitoring in daily
check("Daily has competitor section", "竞争国动态" in q_daily)

# ── Test 7: Report generation ──
print("\n## Test 7: Report Generation")
from generate_report import (
    generate_daily, generate_platform, generate_market,
    generate_hs, generate_risk, generate_opportunity, prepare_report_items,
    generate_tariff, generate_calendar,
)

r1 = generate_daily(1)
check("Daily report has date", str(date.today()) in r1)
check("Daily report has top_items table", "| 1 |" in r1)
check("Daily report has dynamic summary", "共处理" in r1 and "数据来源" in r1)
check("Daily report has template sections", "## 政策与监管" in r1)
check("Daily report has dynamic platform section", "平台规则更新" in r1)
check("Daily report has dynamic logistics section", "国际物流" in r1)
check("Daily report has dynamic risk section", "风险 high" in r1 or "风险 medium" in r1)

r2 = generate_daily(7)
check("Weekly uses '近 7 天'", "近 7 天" in r2)

r3 = generate_platform("Shopee")
check("Platform report has platform name", "Shopee" in r3)
check("Platform report has Agent hint", "Agent" in r3)

r4 = generate_market("India")
check("Market report has market name", "India" in r4)

r5 = generate_hs("4202")
check("HS report has code", "4202" in r5)

r6 = generate_risk(7)
check("Risk report has risk_table", "平台合规" in r6)

r7 = generate_opportunity(7)
check("Opportunity report has table", "家居收纳" in r7)

external_raw = [
    {
        "title": "Amazon seller policy update on product compliance",
        "summary": "Amazon announced updated product compliance checks.",
        "url": "https://example.com/a",
        "source": "platform_official",
        "published_date": str(date.today()),
        "markets": ["US"],
        "platforms": ["Amazon"],
        "categories": ["electronics"],
        "risk_level": "medium",
    },
    {
        "title": "Amazon seller policy update product compliance",
        "summary": "A similar report from another source.",
        "url": "https://example.com/b",
        "source": "industry_media",
        "published_date": str(date.today()),
        "markets": ["US"],
        "platforms": ["Amazon"],
        "categories": ["electronics"],
        "risk_level": "medium",
    },
]
prepared = prepare_report_items(external_raw)
check("prepare_report_items clusters similar external items", len(prepared) == 1)
custom_daily = generate_daily(1, raw_items=external_raw, source_label="外部测试数据")
check("Daily report can use external raw items", "外部测试数据" in custom_daily)
dynamic_platform = generate_platform("Amazon", raw_items=external_raw)
check("Platform report can use external items", "基于 1 条相关情报生成" in dynamic_platform)
dynamic_market = generate_market("US", raw_items=external_raw)
check("Market report can use external items", "US 市场简报基于" in dynamic_market)
dynamic_hs = generate_hs("8516", raw_items=[
    {
        "title": "HS Code 8516 tariff change for US consumer electronics",
        "summary": "New tariff exposure requires review.",
        "source": "official",
        "published_date": str(date.today()),
        "risk_level": "high",
    }
])
check("HS report can use external items", "8516 简报基于 1 条" in dynamic_hs)
dynamic_risk = generate_risk(7, raw_items=external_raw)
check("Risk report can use external items", "风险雷达基于" in dynamic_risk)
dynamic_opp = generate_opportunity(7, raw_items=[
    {
        "title": "Pet products trend growth in US ecommerce",
        "summary": "Trend data shows growth opportunity for pet products.",
        "source": "industry_media",
        "published_date": str(date.today()),
        "risk_level": "low",
    }
])
check("Opportunity report can use external items", "选品机会雷达基于 1 条" in dynamic_opp)

# Tariff report
r_tariff = generate_tariff(category="furniture", market="US")
check("Tariff report has category", "furniture" in r_tariff)
check("Tariff report has market", "US" in r_tariff)
check("Tariff report has tariff reference", "MFN" in r_tariff)
check("Tariff report has certifications", "certification" in r_tariff.lower() or "认证" in r_tariff or "暂无" in r_tariff)
check("Tariff report has actions", "HS Code" in r_tariff)

r_tariff_hs = generate_tariff(hs_code="9403", market="EU")
check("Tariff report by HS code", "9403" in r_tariff_hs)
check("Tariff HS prefix matches category reference", "0-5.6%" in r_tariff_hs or "REACH" in r_tariff_hs)

# Calendar report
r_cal = generate_calendar(days=365)
check("Calendar report has title", "外贸日历" in r_cal)
check("Calendar report has suggestions", "建议" in r_cal)
check("Calendar report has date", str(date.today()) in r_cal)

# ── Test 8: Sample items ──
print("\n## Test 8: Sample Items")
from fetch_news import sample_items

items = sample_items(days=1)
check("Sample returns 6 items", len(items) == 6)
check("Items have required fields",
      all(k in items[0] for k in ["title", "type", "source", "published_date", "risk_level"]))

filtered = sample_items(days=1, query="关税")
check("Query filter works", len(filtered) < len(items))
check("Filtered items match query", all("关税" in i["title"] or "关税" in i["summary"] for i in filtered))

# ── Test 9: Template files exist ──
print("\n## Test 9: Templates")
templates_dir = ROOT_DIR / "templates"
expected = ["daily_report.md", "platform_report.md", "market_report.md",
            "hs_code_report.md", "risk_report.md", "product_opportunity.md",
            "tariff_report.md"]
for t in expected:
    check(f"Template {t} exists", (templates_dir / t).exists())

# ── Test 10: Source weight coverage ──
print("\n## Test 10: Source Weight Coverage")
from rank_items import SOURCE_WEIGHT
from fetch_news import sample_items as si
all_sources = set(i["source"] for i in si())
for src in all_sources:
    check(f"Source '{src}' in SOURCE_WEIGHT", src in SOURCE_WEIGHT)

# ── Test 11: User config ──
print("\n## Test 11: User Config")
from fetch_news import load_user_config, filter_items_by_user_config

config = load_user_config()
check("Config loads successfully", isinstance(config, dict))
check("Config has focus_markets", "focus_markets" in config and len(config["focus_markets"]) > 0)
check("Config has focus_platforms", "focus_platforms" in config and len(config["focus_platforms"]) > 0)

# Test filter_items_by_user_config
test_items = [
    {"title": "US item", "markets": ["US"], "platforms": ["Amazon"], "categories": ["home"]},
    {"title": "BR item", "markets": ["Brazil"], "platforms": [], "categories": ["general"]},
]
filtered = filter_items_by_user_config(test_items, config)
check("Filter boosts matching items", filtered[0]["title"] == "US item")

# Test with empty config
filtered_empty = filter_items_by_user_config(test_items, {})
check("Empty config preserves order", len(filtered_empty) == 2)

# ── Test 12: fetch_sources user_config integration ──
print("\n## Test 12: Fetch Sources with user_config")
sources_with_config = load_all_sources()
check("load_all_sources includes user_config", "user_config" in sources_with_config)
check("user_config is dict", isinstance(sources_with_config["user_config"], dict))

# ── Test 13: External item normalization / clustering ──
print("\n## Test 13: External Items")
from fetch_news import load_items_file, normalize_external_items, coerce_external_item
from fetch_news import normalize_feed_source, load_rss_sources, collect_rss_sources
from item_cluster import cluster_items, title_similarity
from item_schema import validate_items
from source_connectors import parse_feed_items, clean_text, normalize_feed_date
from entity_extractor import enrich_item, extract_hs_codes, extract_markets, extract_platforms, extract_competitors
from report_sections import (
    build_daily_sections, build_daily_summary, build_actions,
    build_calendar_section, build_logistics_alert_section, build_fx_alert_section,
    build_tariff_context, build_fx_market_risk, build_competitor_news_section,
    build_seasonal_demand_section,
)
from run_pipeline import generate_report_from_items

sample_path = ROOT_DIR / "examples" / "external_items_sample.json"
loaded = load_items_file(sample_path)
check("External sample loads", len(loaded) == 3)
check("Search-style result coerces title", loaded[0]["title"].startswith("Amazon"))
normalized_external = normalize_external_items(sample_path)
check("External sample clusters 3->2", len(normalized_external) == 2)
check("External sample validates", validate_items(normalized_external) == [])
check("Title similarity detects duplicate", title_similarity(loaded[0]["title"], loaded[1]["title"]) >= 0.5)

coerced = coerce_external_item({"name": "Tariff update", "snippet": "new tariff rule", "link": "https://x.test"})
check("Coerce infers tariff type", coerced["type"] == "tariff")
platform_coerced = coerce_external_item({"name": "Amazon seller policy update", "snippet": "new seller rule"})
check("Coerce prefers platform over generic policy", platform_coerced["type"] == "platform")

# ── Test 14: RSS / Atom connector ──
print("\n## Test 14: RSS Connector")
rss_path = ROOT_DIR / "examples" / "rss_feed_sample.xml"
raw_feed_items = parse_feed_items(str(rss_path), source_tier="industry_media")
check("RSS parser reads items", len(raw_feed_items) == 2)
check("RSS parser uses channel title", raw_feed_items[0]["source_name"] == "Tradehot Sample Feed")
check("RSS parser normalizes date", raw_feed_items[0]["published_date"] == "2026-06-16")
check("clean_text removes HTML", clean_text("<p>Hello<br/>world</p>") == "Hello world")
check("normalize_feed_date handles RFC date", normalize_feed_date("Tue, 16 Jun 2026 08:00:00 GMT") == "2026-06-16")

normalized_feed = normalize_feed_source(str(rss_path), source_tier="industry_media")
check("RSS normalized items validate", validate_items(normalized_feed) == [])
check("RSS normalized infers platform", normalized_feed[0]["type"] == "platform")
check("RSS normalized infers logistics", normalized_feed[1]["type"] == "logistics")

rss_sources = load_rss_sources()
check("RSS source config loads", len(rss_sources) >= 1)
batch = collect_rss_sources()
check("RSS batch collects items", batch["stats"]["items"] >= 2)
check("RSS batch has no fixture errors", batch["stats"]["errors"] == 0)
check("RSS batch output has items key", "items" in batch and isinstance(batch["items"], list))

# ── Test 15: Entity extraction ──
print("\n## Test 15: Entity Extraction")
entity_item = enrich_item(
    {
        "title": "TikTok Shop seller compliance update in the US for consumer electronics HS 8516",
        "summary": "Sellers in the United States should review certification requirements and tariff exposure.",
        "type": "general",
        "risk_level": "low",
        "markets": [],
        "platforms": [],
        "categories": [],
        "hs_codes": [],
    }
)
check("Extractor finds platform", "TikTok Shop" in entity_item["platforms"])
check("Extractor finds market", "US" in entity_item["markets"] or "United States" in entity_item["markets"])
check("Extractor finds category", "consumer electronics" in entity_item["categories"])
check("Extractor finds HS code", "8516" in entity_item["hs_codes"])
check("Extractor upgrades type", entity_item["type"] == "platform")
check("Extractor upgrades risk", entity_item["risk_level"] == "medium")
check("Extractor does not treat years as HS codes", extract_hs_codes("policy update 2026") == [])
check("Extractor recognizes explicit HS code", extract_hs_codes("HS Code 9403 furniture") == ["9403"])
check("Extractor platform lookup works", "Amazon" in extract_platforms("amazon seller policy"))
check("Extractor market lookup works", "Germany" in extract_markets("exports to Germany and 德国"))

# Competitor extraction
check("extract_competitors finds Vietnam", "Vietnam" in extract_competitors("越南出口增长"))
check("extract_competitors finds India", "India" in extract_competitors("india textile exports"))
check("extract_competitors finds multiple", len(extract_competitors("越南和印度竞争")) >= 2)
check("extract_competitors empty for unrelated", extract_competitors("domestic policy update") == [])

# enrich_item includes competitors
comp_item = enrich_item({
    "title": "Vietnam furniture exports growing in US market",
    "summary": "越南家具出口美国市场份额持续提升。",
    "type": "general",
    "risk_level": "low",
    "markets": [],
    "platforms": [],
    "categories": [],
    "hs_codes": [],
})
check("enrich_item extracts competitors", "Vietnam" in comp_item.get("competitors", []))

rss_daily = generate_daily(1, raw_items=batch["items"], source_label="RSS测试数据")
check("RSS daily uses extracted platform", "TikTok Shop" in rss_daily)
check("RSS daily has fewer unknown affected fields", "TikTok Shop seller compliance rule update | platform | TikTok Shop" in rss_daily)

# ── Test 16: Dynamic report sections ──
print("\n## Test 16: Dynamic Report Sections")
sections = build_daily_sections(prepared)
check("Dynamic sections include platform item", "Amazon seller policy update" in sections["platforms"])
check("Dynamic actions are generated", build_actions(prepared).startswith("1."))
summary = build_daily_summary(prepared, "今日", "测试数据")
check("Dynamic summary includes item count", "共处理" in summary and "测试数据" in summary)

# New sections in daily
check("Daily sections have calendar key", "calendar" in sections)
check("Daily sections have competitors key", "competitors" in sections)
check("Daily sections have logistics_alerts key", "logistics_alerts" in sections)
check("Daily sections have fx_alerts key", "fx_alerts" in sections)
check("Calendar section is string", isinstance(sections["calendar"], str))
check("Logistics alerts contain risk markers", "风险" in sections["logistics_alerts"] or "🔴" in sections["logistics_alerts"] or "🟡" in sections["logistics_alerts"] or "暂无" in sections["logistics_alerts"])
check("FX alerts section is non-empty", len(sections["fx_alerts"]) > 0)

# ── Test 17: Full pipeline helper ──
print("\n## Test 17: Full Pipeline")
pipeline_report = generate_report_from_items(
    report_type="daily",
    items=batch["items"],
    days=1,
    platform="TikTok Shop",
    market="US",
    hs_code="9403",
    source_label="pipeline test",
)
check("Pipeline helper generates report", "pipeline test" in pipeline_report and "TikTok Shop" in pipeline_report)
pipeline_platform = generate_report_from_items(
    report_type="platform",
    items=batch["items"],
    days=1,
    platform="TikTok Shop",
    market="US",
    hs_code="9403",
    source_label="pipeline test",
)
check("Pipeline helper supports platform reports", "TikTok Shop 简报基于" in pipeline_platform)

# Pipeline tariff
pipeline_tariff = generate_report_from_items(
    report_type="tariff",
    items=batch["items"],
    days=1,
    platform="",
    market="US",
    hs_code="9403",
    source_label="pipeline test",
    category="furniture",
)
check("Pipeline supports tariff", "furniture" in pipeline_tariff and "US" in pipeline_tariff)

# Pipeline calendar
pipeline_cal = generate_report_from_items(
    report_type="calendar",
    items=batch["items"],
    days=365,
    platform="",
    market="",
    hs_code="",
    source_label="pipeline test",
)
check("Pipeline supports calendar", "外贸日历" in pipeline_cal)

# ── Test 18: Intelligence dimension builders ──
print("\n## Test 18: Intelligence Builders")

# Calendar
cal = build_calendar_section(days_ahead=365)
check("Calendar section returns string", isinstance(cal, str) and len(cal) > 0)
check("Calendar has events or fallback", "**" in cal or "暂无" in cal)

# Logistics alerts
logi = build_logistics_alert_section()
check("Logistics alert returns string", isinstance(logi, str) and len(logi) > 0)
check("Logistics has hotspot data", "高风险" in logi or "🔴" in logi or "运价指数" in logi or "暂无" in logi)

# FX alerts
fx = build_fx_alert_section()
check("FX alert returns string", isinstance(fx, str) and len(fx) > 0)
check("FX has currency or payment data", "高波动" in fx or "支付风险" in fx or "人民币" in fx or "暂无" in fx)

# Tariff context
tariff_ctx = build_tariff_context("furniture", "US")
check("Tariff context is dict", isinstance(tariff_ctx, dict))
check("Tariff context has summary", "summary" in tariff_ctx and "furniture" in tariff_ctx["summary"])
check("Tariff context has tariff_reference", "tariff_reference" in tariff_ctx)
check("Tariff context has certifications", "certifications" in tariff_ctx)
check("Tariff context has actions", "actions" in tariff_ctx)
check("Tariff context has official_sources", "official_sources" in tariff_ctx)

# Tariff context with unknown category
tariff_unknown = build_tariff_context("unknown_cat_xyz", "US")
check("Tariff handles unknown category", "summary" in tariff_unknown)
tariff_hs_prefix = build_tariff_context("9403", "US")
check("Tariff context matches HS prefix", "0-6%" in tariff_hs_prefix.get("tariff_reference", "") or "CARB" in tariff_hs_prefix.get("certifications", ""))

# FX market risk
fx_us = build_fx_market_risk("US")
check("FX market risk US returns string", isinstance(fx_us, str))
fx_in = build_fx_market_risk("India")
check("FX market risk India has data", "卢比" in fx_in or "INR" in fx_in or "支付" in fx_in or "暂无" in fx_in)

# Competitor news section
comp_news = build_competitor_news_section(prepared)
check("Competitor news returns string", isinstance(comp_news, str))

# Seasonal demand
demand = build_seasonal_demand_section(prepared)
check("Seasonal demand returns string", isinstance(demand, str))

# ── Test 19: item_schema competitors field ──
print("\n## Test 19: Schema Competitors")
from item_schema import LIST_FIELDS, DEFAULT_ITEM, normalize_item
check("competitors in LIST_FIELDS", "competitors" in LIST_FIELDS)
check("DEFAULT_ITEM has competitors", "competitors" in DEFAULT_ITEM and DEFAULT_ITEM["competitors"] == [])
n_item = normalize_item({"title": "test", "competitors": "Vietnam"})
check("normalize_item converts competitors to list", isinstance(n_item["competitors"], list))

# ── Summary ──
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} passed, {FAIL} failed")
if FAIL == 0:
    print("ALL TESTS PASSED")
else:
    print(f"WARNING: {FAIL} test(s) failed")
print("=" * 60)
