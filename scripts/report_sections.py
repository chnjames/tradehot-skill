#!/usr/bin/env python3
"""Build dynamic report sections from normalized tradehot items."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
SOURCES_DIR = ROOT / "sources"


def _load_source_json(filename: str) -> Dict[str, Any]:
    path = SOURCES_DIR / filename
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def join_dimensions(item: Dict[str, object]) -> str:
    values: List[str] = []
    for field in ["markets", "platforms", "categories", "hs_codes"]:
        values.extend(str(x) for x in item.get(field, []) if str(x).strip())
    return ", ".join(dict.fromkeys(values)) or "待判断"


def item_action(item: Dict[str, object]) -> str:
    if item.get("recommended_action"):
        return str(item["recommended_action"])
    item_type = str(item.get("type", "general"))
    if item_type in {"policy", "tariff", "compliance"}:
        return "核查官方文件，更新报关/认证/税务资料"
    if item_type == "platform":
        return "检查 SKU、Listing、账号健康和平台公告"
    if item_type == "logistics":
        return "更新报价有效期和运输条款"
    if item_type == "data":
        return "用 HS Code 验证目标市场和竞争国"
    return "加入业务跟进清单"


def bullet_for_item(item: Dict[str, object]) -> str:
    title = str(item.get("title", "")).strip()
    summary = str(item.get("summary", "")).strip()
    risk = str(item.get("risk_level", "low"))
    affected = join_dimensions(item)
    action = item_action(item)
    score = item.get("hot_score", 0)
    return (
        f"- **{title}**（热度 {score}/25，风险 {risk}）：{summary} "
        f"影响对象：{affected}。建议：{action}。"
    )


def filter_by_types(items: Iterable[Dict[str, object]], types: set[str]) -> List[Dict[str, object]]:
    return [item for item in items if str(item.get("type", "")) in types]


def filter_by_risk(items: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    return [item for item in items if str(item.get("risk_level", "")) in {"medium", "high"}]


def filter_opportunity_items(items: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    result = []
    for item in items:
        item_type = str(item.get("type", ""))
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        if item_type in {"data", "market"} or any(
            key in text for key in ["trend", "growth", "opportunity", "趋势", "增长", "机会", "选品"]
        ):
            result.append(item)
    return result


def section_from_items(items: List[Dict[str, object]], fallback: str, limit: int = 5) -> str:
    if not items:
        return fallback
    return "\n".join(bullet_for_item(item) for item in items[:limit])


def summarize_top_dimensions(items: Iterable[Dict[str, object]], field: str, limit: int = 3) -> str:
    counter: Counter[str] = Counter()
    for item in items:
        counter.update(str(x) for x in item.get(field, []) if str(x).strip())
    if not counter:
        return "暂无明显集中对象"
    return "、".join(name for name, _ in counter.most_common(limit))


def build_daily_summary(items: List[Dict[str, object]], period: str, source_label: str) -> str:
    if not items:
        return f"{period}未获得可用情报。数据来源：{source_label}。"
    high_risk = sum(1 for item in items if item.get("risk_level") == "high")
    top_types = summarize_top_dimensions(
        [{"type_bucket": [str(item.get("type", "general"))]} for item in items],
        "type_bucket",
    )
    markets = summarize_top_dimensions(items, "markets")
    platforms = summarize_top_dimensions(items, "platforms")
    return (
        f"{period}共处理 {len(items)} 条情报，主要集中在 {top_types}。"
        f"重点市场：{markets}；重点平台：{platforms}。"
        f"高风险事项 {high_risk} 条。数据来源：{source_label}，已通过本地 schema 校验。"
    )


def build_actions(items: List[Dict[str, object]], limit: int = 6) -> str:
    if not items:
        return "1. 补充官方来源或平台公告后再生成行动清单。"
    actions = []
    seen = set()
    for item in items:
        action = item_action(item)
        if action not in seen:
            seen.add(action)
            actions.append(action)
        if len(actions) >= limit:
            break
    return "\n".join(f"{idx}. {action}" for idx, action in enumerate(actions, start=1))


def build_daily_sections(items: List[Dict[str, object]]) -> Dict[str, str]:
    policy_items = filter_by_types(items, {"policy", "compliance"})
    platform_items = filter_by_types(items, {"platform"})
    market_items = filter_by_types(items, {"data", "market"})
    logistics_items = filter_by_types(items, {"logistics"})
    tariff_items = filter_by_types(items, {"tariff", "compliance"})
    opportunity_items = filter_opportunity_items(items)
    risk_items = filter_by_risk(items)

    return {
        "policy": section_from_items(policy_items, "- 暂无新的政策与监管情报；继续关注官方来源。"),
        "platforms": section_from_items(platform_items, "- 暂无新的平台动态；继续关注平台官方公告。"),
        "market_data": section_from_items(market_items, "- 暂无新的市场/数据情报；建议补充 WTO、UN Comtrade、ITC 数据。"),
        "logistics": section_from_items(logistics_items, "- 暂无新的物流情报；报价前仍需复核运价和船期。"),
        "tariff_compliance": section_from_items(tariff_items, "- 暂无新的关税/合规情报；高风险品类仍需复核目标市场规则。"),
        "product_opportunities": section_from_items(opportunity_items, "- 暂无明确选品机会；建议补充趋势数据和平台榜单。"),
        "risks": section_from_items(risk_items, "- 暂无中高风险情报；仍需持续监控关税、认证、物流和平台合规。"),
        "calendar": build_calendar_section(),
        "competitors": build_competitor_news_section(items),
        "logistics_alerts": build_logistics_alert_section(),
        "fx_alerts": build_fx_alert_section(),
        "actions": build_actions(items),
    }


def _contains_dimension(item: Dict[str, object], field: str, target: str) -> bool:
    target_norm = target.lower().replace("_", " ")
    values = [str(x).lower().replace("_", " ") for x in item.get(field, [])]
    return any(target_norm in value or value in target_norm for value in values)


def filter_for_platform(items: List[Dict[str, object]], platform: str) -> List[Dict[str, object]]:
    return [
        item for item in items
        if _contains_dimension(item, "platforms", platform)
        or platform.lower().replace("_", " ") in f"{item.get('title', '')} {item.get('summary', '')}".lower()
    ]


def filter_for_market(items: List[Dict[str, object]], market: str) -> List[Dict[str, object]]:
    return [
        item for item in items
        if _contains_dimension(item, "markets", market)
        or market.lower().replace("_", " ") in f"{item.get('title', '')} {item.get('summary', '')}".lower()
    ]


def filter_for_hs(items: List[Dict[str, object]], hs_code: str) -> List[Dict[str, object]]:
    return [
        item for item in items
        if hs_code in [str(x) for x in item.get("hs_codes", [])]
        or hs_code in f"{item.get('title', '')} {item.get('summary', '')}"
    ]


def strongest_risk_level(items: List[Dict[str, object]]) -> str:
    if any(item.get("risk_level") == "high" for item in items):
        return "高"
    if any(item.get("risk_level") == "medium" for item in items):
        return "中"
    return "低"


def build_platform_context(platform: str, items: List[Dict[str, object]]) -> Dict[str, str]:
    scoped = filter_for_platform(items, platform) or filter_by_types(items, {"platform"})
    return {
        "summary": f"{platform} 简报基于 {len(scoped)} 条相关情报生成。风险等级：{strongest_risk_level(scoped)}。",
        "changes": section_from_items(scoped, "- 暂无可用平台动态；请补充平台官方公告或行业来源。"),
        "impact": section_from_items(scoped, "- 暂无明确卖家影响；需继续核实类目、费用、履约和账号规则。"),
        "affected_categories_markets": summarize_top_dimensions(scoped, "categories") + "；" + summarize_top_dimensions(scoped, "markets"),
        "risk_level": strongest_risk_level(scoped),
        "opportunity": section_from_items(filter_opportunity_items(scoped), "- 暂无明确平台机会；关注新类目、新市场和平台招商期。"),
        "actions": build_actions(scoped),
    }


def build_market_context(market: str, items: List[Dict[str, object]]) -> Dict[str, str]:
    scoped = filter_for_market(items, market)
    return {
        "summary": f"{market} 市场简报基于 {len(scoped)} 条相关情报生成。风险等级：{strongest_risk_level(scoped)}。",
        "overview": section_from_items(scoped, "- 暂无可用市场情报；建议补充官方统计、贸易数据和本地渠道信息。"),
        "import_demand": section_from_items(filter_by_types(scoped, {"data", "market"}), "- 暂无进口需求数据；建议接入 UN Comtrade / ITC Trade Map。"),
        "growth_categories": summarize_top_dimensions(scoped, "categories"),
        "competitors": "- 需结合贸易数据比较主要出口国、价格带和份额变化。",
        "competitor_dynamics": build_competitor_news_section(scoped),
        "tariffs_access": section_from_items(filter_by_types(scoped, {"tariff", "compliance", "policy"}), "- 暂无关税/准入情报；需查询目标国官方税则。"),
        "platform_opportunities": summarize_top_dimensions(scoped, "platforms"),
        "fx_risk_market": build_fx_market_risk(market),
        "risks": section_from_items(filter_by_risk(scoped), "- 暂无中高风险情报。"),
        "actions": build_actions(scoped),
    }


def build_hs_context(hs_code: str, items: List[Dict[str, object]]) -> Dict[str, str]:
    scoped = filter_for_hs(items, hs_code)
    return {
        "summary": f"{hs_code} 简报基于 {len(scoped)} 条相关情报生成；仍需用官方税则和贸易数据复核。",
        "definition": f"- 当前按 `{hs_code}` 识别相关情报；正式使用时需确认 6/8/10 位编码定义。",
        "top_import_markets": summarize_top_dimensions(scoped, "markets"),
        "fastest_growing_markets": section_from_items(filter_by_types(scoped, {"data", "market"}), "- 暂无增长市场数据；需接入贸易数据。"),
        "export_competitors": "- 需用 UN Comtrade / ITC Trade Map 对比主要出口国。",
        "tariffs_access": section_from_items(filter_by_types(scoped, {"tariff", "policy", "compliance"}), "- 暂无关税/准入情报；需核查目标国税则。"),
        "platform_opportunities": summarize_top_dimensions(scoped, "platforms"),
        "buyer_keywords": "- importer, distributor, wholesaler, buyer, sourcing, supplier。",
        "risks": section_from_items(filter_by_risk(scoped), "- 暂无中高风险情报。"),
        "actions": build_actions(scoped),
    }


def build_risk_context(items: List[Dict[str, object]]) -> Dict[str, str]:
    risk_items = filter_by_risk(items)
    rows = []
    for item in risk_items[:10]:
        rows.append(
            f"| {item.get('type', 'general')} | {item.get('risk_level', 'low')} | "
            f"{join_dimensions(item)} | {item_action(item)} |"
        )
    return {
        "summary": f"风险雷达基于 {len(risk_items)} 条中高风险情报生成。最高风险等级：{strongest_risk_level(risk_items)}。",
        "risk_table": "\n".join(rows) if rows else "| 暂无 | 低 | 暂无 | 持续监控 |",
        "tariff_risks": section_from_items(filter_by_types(risk_items, {"tariff"}), "- 暂无关税风险情报。"),
        "trade_restriction_risks": section_from_items(filter_by_types(risk_items, {"policy", "compliance"}), "- 暂无贸易限制风险情报。"),
        "platform_compliance_risks": section_from_items(filter_by_types(risk_items, {"platform"}), "- 暂无平台合规风险情报。"),
        "logistics_risks": section_from_items(filter_by_types(risk_items, {"logistics"}), "- 暂无物流风险情报。"),
        "logistics_hotspots": build_logistics_alert_section(),
        "fx_risks": section_from_items(
            [i for i in risk_items if any(k in str(i.get('summary', '')).lower() for k in ['fx', 'exchange', '汇率', 'currency', '货币'])],
            "- 暂无汇率风险情报。"
        ),
        "fx_risk_countries": build_fx_alert_section(),
        "payment_risks": "- 暂无收款风险情报；新客户仍建议做信用审查。",
        "certification_risks": section_from_items([i for i in risk_items if "certification" in str(i.get("summary", "")).lower() or "认证" in str(i.get("summary", ""))], "- 暂无认证风险情报。"),
        "geopolitical_risks": section_from_items([i for i in risk_items if "sanction" in str(i.get("summary", "")).lower() or "制裁" in str(i.get("summary", ""))], "- 暂无地缘政治风险情报。"),
        "business_impact": section_from_items(risk_items, "- 暂无明确业务影响。"),
        "actions": build_actions(risk_items),
    }


def build_opportunity_context(items: List[Dict[str, object]]) -> Dict[str, str]:
    scoped = filter_opportunity_items(items)
    rows = []
    for item in scoped[:8]:
        rows.append(
            f"| {summarize_top_dimensions([item], 'categories')} | "
            f"{summarize_top_dimensions([item], 'markets')} | {item.get('summary', '')} | "
            f"{item.get('risk_level', 'low')} | {item_action(item)} |"
        )
    return {
        "summary": f"选品机会雷达基于 {len(scoped)} 条趋势/市场情报生成。",
        "opportunity_table": "\n".join(rows) if rows else "| 暂无 | 暂无 | 需补充趋势和贸易数据 | 待判断 | 补充数据源 |",
        "platform_heat": summarize_top_dimensions(scoped, "platforms"),
        "data_validation": section_from_items(filter_by_types(scoped, {"data", "market"}), "- 需补充 Google Trends、平台榜单和贸易数据验证。"),
        "supply_chain_notes": "- 对高潜力品类评估 MOQ、交期、认证、海外仓和售后成本。\n" + build_seasonal_demand_section(scoped),
        "keywords": "- importer, distributor, wholesaler, buyer, sourcing, supplier。",
    }


# ---------------------------------------------------------------------------
# New intelligence dimension builders
# ---------------------------------------------------------------------------
def build_calendar_section(days_ahead: int = 30) -> str:
    """Return upcoming trade events within `days_ahead` days."""
    data = _load_source_json("trade_calendar.json")
    events = data.get("events", [])
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    upcoming = []
    for ev in events:
        try:
            ev_date = date.fromisoformat(ev["date"])
        except (KeyError, ValueError):
            continue
        if today <= ev_date <= cutoff:
            markets = ", ".join(ev.get("markets", []))
            categories = ", ".join(ev.get("categories", []))
            lead = ev.get("prep_lead_days", "")
            lead_note = f"（建议提前 {lead} 天准备）" if lead else ""
            upcoming.append(
                f"- **{ev_date.isoformat()}** {ev['name']}"
                f"｜{markets}｜{categories}{lead_note}"
            )
    if not upcoming:
        return f"- 未来 {days_ahead} 天暂无重大贸易日历事件；建议持续关注广交会、CES、Prime Day 等节点。"
    return "\n".join(upcoming)


def build_seasonal_demand_section(items: List[Dict[str, object]]) -> str:
    """Return seasonal demand notes for categories found in items."""
    data = _load_source_json("trade_calendar.json")
    curves = data.get("seasonal_demand_curves", [])
    if not curves:
        return ""
    found_categories: set = set()
    for item in items:
        found_categories.update(str(c) for c in item.get("categories", []) if str(c).strip())
    notes = []
    current_month = date.today().month
    for curve in curves:
        cat = curve.get("category", "")
        if cat in found_categories or "all" in found_categories:
            for market, months in curve.get("peak_months", {}).items():
                if current_month in months:
                    notes.append(f"- {cat} 在 {market} 当前处于需求旺季（{months} 月）")
                elif (current_month % 12 + 1) in months:
                    notes.append(f"- {cat} 在 {market} 下月进入旺季，建议现在开始备货")
    return "\n".join(notes) if notes else ""


def build_logistics_alert_section() -> str:
    """Return current logistics hotspot status from config."""
    data = _load_source_json("logistics_hotspots.json")
    hotspots = data.get("hotspots", [])
    high_risk = [h for h in hotspots if h.get("risk_level") == "high"]
    medium_risk = [h for h in hotspots if h.get("risk_level") == "medium"]
    lines = []
    for h in high_risk:
        routes = ", ".join(h.get("affected_routes", []))
        lines.append(f"- **🔴 高风险：{h.get('name_zh', h['name'])}**｜影响航线：{routes}｜{h.get('impact_description', '')}。替代方案：{h.get('alternative', '暂无')}。")
    for h in medium_risk:
        routes = ", ".join(h.get("affected_routes", []))
        lines.append(f"- **🟡 中风险：{h.get('name_zh', h['name'])}**｜影响航线：{routes}｜{h.get('impact_description', '')}。")
    if not lines:
        return "- 暂无活跃物流中断事件；仍需持续监控主要港口和运河状态。"
    indices = data.get("freight_indices", [])
    if indices:
        idx_lines = [f"  - [{idx['name']}]({idx['url']})" for idx in indices]
        lines.append("- 运价指数参考：\n" + "\n".join(idx_lines))
    return "\n".join(lines)


def build_fx_alert_section() -> str:
    """Return high-volatility currency and payment risk summary."""
    data = _load_source_json("fx_risk.json")
    high_currencies = [c for c in data.get("high_volatility_currencies", []) if c.get("risk_level") == "high"]
    high_payment = [p for p in data.get("payment_risk_countries", []) if p.get("risk_level") == "high"]
    lines = []
    if high_currencies:
        names = "、".join(f"{c['zh_name']}（{c['country']}）" for c in high_currencies[:6])
        lines.append(f"- **高波动货币**：{names}。报价时建议加 3-5% 汇率缓冲并设置短报价有效期。")
    if high_payment:
        names = "、".join(f"{p['zh_name']}" for p in high_payment[:6])
        lines.append(f"- **高支付风险国家**：{names}。建议使用预付款或即期信用证，并做好制裁筛查。")
    notes = data.get("cross_border_payment_notes", [])
    for note in notes[:2]:
        lines.append(f"- **{note['topic']}**：{note['description']}。")
    if not lines:
        return "- 暂无汇率/支付风险提醒。"
    return "\n".join(lines)


def build_competitor_news_section(items: List[Dict[str, object]]) -> str:
    """Return competitor-related items from the intelligence feed."""
    data = _load_source_json("competitors.json")
    competitors = data.get("competitors", [])
    country_names = set()
    for c in competitors:
        country_names.add(c.get("country", "").lower())
        country_names.add(c.get("zh_name", "").lower())
    related = []
    for item in items:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        if any(name in text for name in country_names if name):
            related.append(item)
    if related:
        return section_from_items(related, "- 暂无竞争国相关情报。", limit=5)
    return "- 暂无竞争国相关情报；持续关注越南、印度、墨西哥、孟加拉的出口动态。"


def build_fx_market_risk(market: str) -> str:
    """Return FX/payment risk info for a specific market."""
    data = _load_source_json("fx_risk.json")
    market_lower = market.lower()
    for c in data.get("high_volatility_currencies", []):
        if c.get("country", "").lower() == market_lower:
            return f"- **{c['zh_name']}（{c['currency']}）**：风险等级 {c['risk_level']}。{c.get('notes', '')}"
    for p in data.get("payment_risk_countries", []):
        if p.get("country", "").lower() == market_lower:
            return f"- **支付风险：{p['risk_level']}**。{p.get('payment_advice', '')}"
    return "- 该市场暂无特别汇率/支付风险提醒；报价仍建议设置有效期。"


def build_tariff_context(category: str, market: str) -> Dict[str, str]:
    """Build tariff/access context for a given category and market."""
    data = _load_source_json("tariff_reference.json")
    entries = data.get("entries", [])
    lookup = category.lower().strip()
    lookup_digits = "".join(ch for ch in lookup if ch.isdigit())
    matched = None
    for entry in entries:
        if entry.get("category", "").lower() == lookup:
            matched = entry
            break
    if not matched:
        # Try partial match
        for entry in entries:
            if lookup and lookup in entry.get("category", "").lower():
                matched = entry
                break
    if not matched and lookup_digits:
        for entry in entries:
            prefixes = str(entry.get("hs_prefix", "")).split("/")
            if any(lookup_digits.startswith(prefix.strip()) for prefix in prefixes if prefix.strip()):
                matched = entry
                break
    market_data = matched.get("markets", {}).get(market, {}) if matched else {}
    summary = f"{category} 在 {market} 的关税与准入参考。数据日期：{data.get('reference_date', '待更新')}。正式使用时请以官方税则为准。"
    mfn = market_data.get("mfn_rate", "暂无数据")
    section_301 = market_data.get("section_301", "")
    rcep = market_data.get("rcep_rate", "")
    tariff_lines = [f"- MFN 税率：{mfn}"]
    if section_301:
        tariff_lines.append(f"- Section 301 加征：{section_301}")
    if rcep:
        tariff_lines.append(f"- RCEP 优惠税率：{rcep}")
    certs = market_data.get("certifications", [])
    cert_text = "\n".join(f"- {c}" for c in certs) if certs else "- 暂无强制认证数据；需核实目标市场法规。"
    labels = market_data.get("labeling", [])
    label_text = "\n".join(f"- {l}" for l in labels) if labels else "- 暂无标签要求数据；需核实目标市场法规。"
    tr = market_data.get("trade_remedy", {})
    tr_lines = []
    ad = tr.get("anti_dumping", False)
    cv = tr.get("countervailing", False)
    if ad:
        tr_lines.append(f"- 反倾销：{ad}")
    if cv:
        tr_lines.append(f"- 反补贴：{cv}")
    tr_text = "\n".join(tr_lines) if tr_lines else "- 暂无活跃贸易救济措施。"
    notes = market_data.get("notes", "")
    # FTA reference
    fta_text = "- 暂无 FTA 优惠税率数据；建议查询中国商务部 FTA 服务网（fta.mofcom.gov.cn）。"
    if rcep:
        fta_text = f"- RCEP：{rcep}（需提供原产地证书）\n- 更多 FTA 优惠请查询中国商务部 FTA 服务网。"
    # Official sources
    official = data.get("official_sources", [])
    src_lines = [f"- [{s['name']}]({s['url']})：{s['description']}" for s in official]
    src_text = "\n".join(src_lines) if src_lines else "- ITC Market Access Map / 目标国官方税则。"
    risk_level = "high" if ad and ad != False else ("medium" if section_301 else "low")
    return {
        "summary": summary,
        "tariff_reference": "\n".join(tariff_lines),
        "fta_rates": fta_text,
        "certifications": cert_text,
        "labeling": label_text,
        "trade_remedy": tr_text,
        "recent_changes": f"- {notes}" if notes else "- 暂无近期变化；建议定期复核官方税则。",
        "competitor_tariffs": "- 需对比越南/印度/墨西哥等竞争国在目标市场的关税优势（如 EVFTA/USMCA）。",
        "risks": f"- 风险等级：{risk_level}。{notes}" if notes else f"- 风险等级：{risk_level}。",
        "actions": (
            "1. 确认 HS Code 6/8/10 位编码。\n"
            "2. 用 ITC Market Access Map 复核税率。\n"
            "3. 检查是否需要 FTA 原产地证书。\n"
            "4. 评估认证和标签合规要求。\n"
            "5. 对比竞争国关税优势。"
        ),
        "official_sources": src_text,
    }
