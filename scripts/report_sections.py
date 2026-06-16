#!/usr/bin/env python3
"""Build dynamic report sections from normalized tradehot items."""

from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List


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
        "tariffs_access": section_from_items(filter_by_types(scoped, {"tariff", "compliance", "policy"}), "- 暂无关税/准入情报；需查询目标国官方税则。"),
        "platform_opportunities": summarize_top_dimensions(scoped, "platforms"),
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
        "fx_risks": "- 暂无汇率风险情报；报价仍建议设置有效期。",
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
        "supply_chain_notes": "- 对高潜力品类评估 MOQ、交期、认证、海外仓和售后成本。",
        "keywords": "- importer, distributor, wholesaler, buyer, sourcing, supplier。",
    }
