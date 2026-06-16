#!/usr/bin/env python3
"""Generate tradehot report drafts.

This is the report generation engine. It produces structured report skeletons
that the Agent fills with real data from WebSearch / WebFetch.

Usage:
    python generate_report.py --type daily --days 1
    python generate_report.py --type weekly --days 7
    python generate_report.py --type platform --platform amazon
    python generate_report.py --type market --market "United States"
    python generate_report.py --type hs --hs-code 9403
    python generate_report.py --type risk --days 7
    python generate_report.py --type opportunity --days 7
    python generate_report.py --search-queries --type daily
"""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path
from typing import Dict, List

from fetch_news import (
    build_search_queries,
    dedup_items,
    filter_items_by_user_config,
    normalize_external_items,
    sample_items,
)
from item_cluster import cluster_items
from normalize_items import normalize_items
from item_schema import validate_items
from rank_items import rank_items
from report_sections import (
    build_daily_sections,
    build_daily_summary,
    build_hs_context,
    build_market_context,
    build_opportunity_context,
    build_platform_context,
    build_risk_context,
    item_action,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"


def load_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text(encoding="utf-8")


PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def render(template: str, context: Dict[str, str]) -> str:
    output = template
    for key, value in context.items():
        output = output.replace("{{" + key + "}}", value)
    missing = sorted(set(PLACEHOLDER_RE.findall(output)))
    if missing:
        raise ValueError(f"Unresolved template placeholders: {', '.join(missing)}")
    return output


def format_top_items(items: List[Dict[str, object]]) -> str:
    lines = []
    for idx, item in enumerate(items[:10], start=1):
        affected = ", ".join(
            [
                *(str(x) for x in item.get("markets", [])),
                *(str(x) for x in item.get("platforms", [])),
                *(str(x) for x in item.get("categories", [])),
            ]
        ) or "待判断"
        action = suggest_action(item)
        lines.append(
            f"| {idx} | {item.get('title', '')} | {item.get('type', '')} "
            f"| {affected} | {item.get('hot_score', 0)} | {action} |"
        )
    return "\n".join(lines)


def format_source_notes(items: List[Dict[str, object]]) -> str:
    """Return compact source/evidence notes for the ranked items."""
    lines = []
    for idx, item in enumerate(items[:10], start=1):
        source = item.get("source_name") or item.get("source") or "未标注来源"
        tier = item.get("source_tier") or item.get("source") or "unknown"
        confidence = item.get("confidence", 0)
        url = item.get("source_url") or item.get("url") or ""
        evidence = str(item.get("evidence") or item.get("summary") or "").strip()
        evidence = evidence[:80] + ("..." if len(evidence) > 80 else "")
        link = f" - {url}" if url else ""
        lines.append(f"{idx}. {source}（{tier}, confidence {confidence}/100）{link}：{evidence}")
    return "\n".join(lines) if lines else "- 当前没有可用来源。"


def suggest_action(item: Dict[str, object]) -> str:
    return item_action(item)


# ---------------------------------------------------------------------------
# Report generators
# ---------------------------------------------------------------------------
def prepare_report_items(raw_items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Normalize, cluster, validate, rank, and apply user preferences."""
    items = normalize_items(dedup_items(raw_items))
    items = cluster_items(items)
    validation_errors = validate_items(items)
    if validation_errors:
        raise ValueError("Invalid report items:\n" + "\n".join(validation_errors))
    items = rank_items(items)
    return filter_items_by_user_config(items)


def generate_daily(days: int, raw_items: List[Dict[str, object]] | None = None, source_label: str = "样例数据") -> str:
    raw = raw_items if raw_items is not None else sample_items(days=days)
    items = prepare_report_items(raw)
    template = load_template("daily_report.md")

    period = "今日" if days <= 1 else f"近 {days} 天"
    sections = build_daily_sections(items)
    return render(
        template,
        {
            "date": str(date.today()),
            "summary": build_daily_summary(items, period, source_label),
            "top_items": format_top_items(items),
            "policy": sections["policy"],
            "platforms": sections["platforms"],
            "market_data": sections["market_data"],
            "logistics": sections["logistics"],
            "tariff_compliance": sections["tariff_compliance"],
            "product_opportunities": sections["product_opportunities"],
            "risks": sections["risks"],
            "actions": sections["actions"],
            "sources": format_source_notes(items),
        },
    )


def generate_platform(platform: str, raw_items: List[Dict[str, object]] | None = None) -> str:
    template = load_template("platform_report.md")
    items = prepare_report_items(raw_items) if raw_items is not None else []
    dynamic = build_platform_context(platform, items) if items else {}
    return render(
        template,
        {
            "platform": platform,
            "date": str(date.today()),
            "summary": dynamic.get("summary") or (
                f"{platform} 平台简报草稿。接入实时来源后，将输出最新公告和卖家影响。\n\n"
                "**Agent 下一步**：运行 "
                f"`python fetch_news.py --mode queries --type platform --platform {platform}` "
                "获取搜索关键词。"
            ),
            "changes": dynamic.get("changes") or "- 类目规则、费用、履约、内容合规和账号健康是优先关注项。",
            "impact": dynamic.get("impact") or "- 可能影响上架、广告投放、达人合作、订单履约和账号安全。",
            "affected_categories_markets": dynamic.get("affected_categories_markets") or (
                "- 需按具体平台公告判断。高风险品类包括美妆、食品接触、儿童用品、电子产品。"
            ),
            "risk_level": dynamic.get("risk_level") or "中。若涉及资质或账号审核，则为高。",
            "opportunity": dynamic.get("opportunity") or "- 新市场、新类目或平台招商期可能带来流量机会。",
            "actions": dynamic.get("actions") or (
                "1. 查官方公告。\n"
                "2. 检查 SKU 资质。\n"
                "3. 更新 Listing 和内容素材。\n"
                "4. 监控退款率、迟发率和差评。"
            ),
            "sources": format_source_notes(items) if items else "- platforms.json + 平台官方公告。",
        },
    )


def generate_market(market: str, raw_items: List[Dict[str, object]] | None = None) -> str:
    template = load_template("market_report.md")
    items = prepare_report_items(raw_items) if raw_items is not None else []
    dynamic = build_market_context(market, items) if items else {}
    return render(
        template,
        {
            "market": market,
            "date": str(date.today()),
            "summary": dynamic.get("summary") or (
                f"{market} 市场简报草稿。接入贸易数据后，应按品类和 HS Code 细分判断。\n\n"
                "**Agent 下一步**：运行 "
                f"`python fetch_news.py --mode queries --type market --market \"{market}\"` "
                "获取搜索关键词。"
            ),
            "overview": dynamic.get("overview") or "- 查看宏观消费、进口规模、汇率、关税、平台生态和本地渠道。",
            "import_demand": dynamic.get("import_demand") or "- 使用 UN Comtrade、WTO、ITC Trade Map 验证。",
            "growth_categories": dynamic.get("growth_categories") or "- 待接入 HS Code 数据后生成。",
            "competitors": dynamic.get("competitors") or "- 重点比较中国、越南、印度、土耳其、墨西哥、欧盟等供应国。",
            "tariffs_access": dynamic.get("tariffs_access") or "- 使用 ITC Market Access Map 和目标国官方税则验证。",
            "platform_opportunities": dynamic.get("platform_opportunities") or "- 根据该市场主流平台和本地渠道判断。",
            "risks": dynamic.get("risks") or "- 关注关税、认证、物流、支付、汇率和本地法规。",
            "actions": dynamic.get("actions") or (
                "1. 选择 3-5 个 HS Code 验证。\n"
                "2. 找主要进口商。\n"
                "3. 对比竞争国价格和交期。\n"
                "4. 准备本地化开发邮件。"
            ),
            "sources": format_source_notes(items) if items else "- markets.json + WTO/UN Comtrade/ITC/官方市场来源。",
        },
    )


def generate_hs(hs_code: str, raw_items: List[Dict[str, object]] | None = None) -> str:
    template = load_template("hs_code_report.md")
    items = prepare_report_items(raw_items) if raw_items is not None else []
    dynamic = build_hs_context(hs_code, items) if items else {}
    return render(
        template,
        {
            "hs_code_or_category": hs_code,
            "date": str(date.today()),
            "summary": dynamic.get("summary") or (
                f"{hs_code} 机会简报草稿。正式使用时需用目标国税则和贸易数据验证。\n\n"
                "**Agent 下一步**：运行 "
                f"`python fetch_news.py --mode queries --type hs --hs-code {hs_code}` "
                "获取搜索关键词。"
            ),
            "definition": dynamic.get("definition") or "- 根据 HS Code 官方定义确认，必要时细分到 6/8/10 位编码。",
            "top_import_markets": dynamic.get("top_import_markets") or "- 待接入 UN Comtrade / ITC Trade Map 后生成。",
            "fastest_growing_markets": dynamic.get("fastest_growing_markets") or "- 比较最近 12-36 个月进口额、进口量和单价变化。",
            "export_competitors": dynamic.get("export_competitors") or "- 分析主要出口国、市场份额和价格带。",
            "tariffs_access": dynamic.get("tariffs_access") or "- 使用 ITC Market Access Map 和目标国官方税则验证。",
            "platform_opportunities": dynamic.get("platform_opportunities") or (
                "- 判断是否适合 Amazon、TikTok Shop、独立站、B2B 或本地分销。"
            ),
            "buyer_keywords": dynamic.get("buyer_keywords") or "- importer, distributor, wholesaler, buyer, sourcing, supplier。",
            "risks": dynamic.get("risks") or "- 关注认证、材质声明、关税、反倾销、物流成本和售后成本。",
            "actions": dynamic.get("actions") or (
                "1. 拆分具体产品。\n"
                "2. 查进口增长市场。\n"
                "3. 找主要进口商。\n"
                "4. 对比竞争国。\n"
                "5. 制作开发名单。"
            ),
            "sources": format_source_notes(items) if items else "- UN Comtrade / ITC Trade Map / Market Access Map / 目标国官方税则。",
        },
    )


def generate_risk(days: int, raw_items: List[Dict[str, object]] | None = None) -> str:
    template = load_template("risk_report.md")
    items = prepare_report_items(raw_items) if raw_items is not None else []
    dynamic = build_risk_context(items) if items else {}
    return render(
        template,
        {
            "date": str(date.today()),
            "summary": dynamic.get("summary") or (
                "风险雷达草稿。正式使用时应结合最新政策、平台公告、物流和汇率数据。\n\n"
                "**Agent 下一步**：运行 `python fetch_news.py --mode queries --type risk` "
                "获取搜索关键词。"
            ),
            "risk_table": dynamic.get("risk_table") or (
                "| 平台合规 | 中 | 平台卖家 | 检查 SKU 资质和账号健康 |\n"
                "| 关税/认证 | 中 | 出口企业 | 查官方税则和认证要求 |\n"
                "| 物流 | 中 | 所有出口商 | 更新报价有效期 |"
            ),
            "tariff_risks": dynamic.get("tariff_risks") or "- 查目标国关税、贸易救济和原产地规则。",
            "trade_restriction_risks": dynamic.get("trade_restriction_risks") or "- 关注制裁、出口管制、不可靠实体清单等。",
            "platform_compliance_risks": dynamic.get("platform_compliance_risks") or "- 关注资质、Listing、内容宣称、延迟履约和差评。",
            "logistics_risks": dynamic.get("logistics_risks") or "- 关注港口拥堵、空海运价格、海外仓和尾程配送。",
            "fx_risks": dynamic.get("fx_risks") or "- 报价需设置有效期，必要时使用汇率缓冲。",
            "payment_risks": dynamic.get("payment_risks") or "- 新客户建议使用信用保险、信用证、预付款或第三方保障。",
            "certification_risks": dynamic.get("certification_risks") or (
                "- 高风险品类包括电子电器、儿童用品、食品接触、美妆个护、医疗相关。"
            ),
            "geopolitical_risks": dynamic.get("geopolitical_risks") or "- 关注目标市场贸易政策和供应链限制。",
            "business_impact": dynamic.get("business_impact") or "- 可能影响成本、交期、收款、账号安全和客户复购。",
            "actions": dynamic.get("actions") or (
                "1. 建立风险清单。\n"
                "2. 对核心市场做关税和认证复核。\n"
                "3. 更新合同条款。\n"
                "4. 对高风险客户做信用审查。"
            ),
            "sources": format_source_notes(items) if items else "- 官方政策、平台公告、物流媒体、贸易数据工具。",
        },
    )


def generate_opportunity(days: int, raw_items: List[Dict[str, object]] | None = None) -> str:
    template = load_template("product_opportunity.md")
    items = prepare_report_items(raw_items) if raw_items is not None else []
    dynamic = build_opportunity_context(items) if items else {}
    return render(
        template,
        {
            "date": str(date.today()),
            "summary": dynamic.get("summary") or (
                "选品机会雷达草稿。正式使用时应结合 Google Trends、平台搜索数据和行业报告。\n\n"
                "**Agent 下一步**：运行 "
                "`python fetch_news.py --mode queries --type opportunity` "
                "获取搜索关键词。"
            ),
            "opportunity_table": dynamic.get("opportunity_table") or (
                "| 家居收纳 | US, UK, DE | Google Trends 上升 + Amazon 搜索量增长 "
                "| 认证要求 | 查 HS Code 和准入标准 |\n"
                "| 宠物用品 | US, JP, AU | 多平台热搜 + 复购率高 "
                "| 物流成本 | 对比海外仓 vs 直邮成本 |\n"
                "| 户外装备 | US, DE, AU | 季节性需求 + TikTok 种草 "
                "| 退货率 | 评估退货政策和物流成本 |"
            ),
            "platform_heat": dynamic.get("platform_heat") or (
                "- Amazon：关注 Best Sellers 变化、New Releases 和 Movers & Shakers。\n"
                "- TikTok Shop：关注短视频种草趋势和达人带货品类。\n"
                "- Temu/SHEIN：关注平台主推品类和价格带竞争。"
            ),
            "data_validation": dynamic.get("data_validation") or (
                "- 用 Google Trends 验证搜索趋势。\n"
                "- 用 UN Comtrade 验证进口增长。\n"
                "- 用 Marketplace Pulse 或 Similarweb 验证平台流量。"
            ),
            "supply_chain_notes": dynamic.get("supply_chain_notes") or (
                "- 评估 MOQ、交期、认证成本。\n"
                "- 中大件关注海外仓 vs 直邮。\n"
                "- 季节性产品关注备货时间窗口。"
            ),
            "keywords": dynamic.get("keywords") or (
                "- 选品关键词：trending products, best sellers, new arrivals。\n"
                "- 买家关键词：importer, distributor, wholesaler, buyer。\n"
                "- 平台搜索词：按具体品类和目标市场组合。"
            ),
            "sources": format_source_notes(items) if items else "- Google Trends / Amazon BSR / TikTok Trends / UN Comtrade / 行业媒体。",
        },
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Generate tradehot report drafts.")
    parser.add_argument(
        "--type",
        choices=["daily", "weekly", "platform", "market", "hs", "risk", "opportunity"],
        default="daily",
    )
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--platform", default="Amazon")
    parser.add_argument("--market", default="United States")
    parser.add_argument("--hs-code", default="9403")
    parser.add_argument(
        "--search-queries",
        action="store_true",
        help="Output search query suggestions instead of report skeleton.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the generated report instead of only printing it.",
    )
    parser.add_argument(
        "--input",
        help="Optional JSON file of external tradehot items/search results for daily/weekly reports.",
    )
    args = parser.parse_args()

    if args.search_queries:
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
        return

    input_items = normalize_external_items(args.input) if args.input else None

    if args.type in {"daily", "weekly"}:
        source_label = f"外部数据 {args.input}" if args.input else "样例数据"
        report = generate_daily(days=args.days, raw_items=input_items, source_label=source_label)
    elif args.type == "platform":
        report = generate_platform(args.platform, raw_items=input_items)
    elif args.type == "market":
        report = generate_market(args.market, raw_items=input_items)
    elif args.type == "hs":
        report = generate_hs(args.hs_code, raw_items=input_items)
    elif args.type == "risk":
        report = generate_risk(args.days, raw_items=input_items)
    elif args.type == "opportunity":
        report = generate_opportunity(args.days, raw_items=input_items)
    else:
        raise ValueError(f"Unsupported report type: {args.type}")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"Wrote report to {output_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()
