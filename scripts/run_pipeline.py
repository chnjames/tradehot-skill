#!/usr/bin/env python3
"""One-command tradehot pipeline.

Collect RSS/Atom sources, normalize/cluster/validate items, and generate a
Markdown report from the same data.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Dict, List

from fetch_news import collect_rss_sources
from generate_report import (
    generate_daily,
    generate_hs,
    generate_market,
    generate_opportunity,
    generate_platform,
    generate_risk,
)

ROOT = Path(__file__).resolve().parents[1]


def default_items_path(report_type: str) -> Path:
    return ROOT / "examples" / f"pipeline_{report_type}_{date.today().isoformat()}_items.json"


def default_report_path(report_type: str) -> Path:
    return ROOT / "examples" / f"pipeline_{report_type}_{date.today().isoformat()}_report.md"


def generate_report_from_items(
    report_type: str,
    items: List[Dict[str, object]],
    days: int,
    platform: str,
    market: str,
    hs_code: str,
    source_label: str,
) -> str:
    if report_type in {"daily", "weekly"}:
        return generate_daily(days=days, raw_items=items, source_label=source_label)
    if report_type == "platform":
        return generate_platform(platform, raw_items=items)
    if report_type == "market":
        return generate_market(market, raw_items=items)
    if report_type == "hs":
        return generate_hs(hs_code, raw_items=items)
    if report_type == "risk":
        return generate_risk(days=days, raw_items=items)
    if report_type == "opportunity":
        return generate_opportunity(days=days, raw_items=items)
    raise ValueError(f"Unsupported report type: {report_type}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full tradehot RSS-to-report pipeline.")
    parser.add_argument(
        "--type",
        choices=["daily", "weekly", "platform", "market", "hs", "risk", "opportunity"],
        default="daily",
    )
    parser.add_argument("--config", default=str(ROOT / "sources" / "rss_sources.json"))
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--platform", default="Amazon")
    parser.add_argument("--market", default="United States")
    parser.add_argument("--hs-code", default="9403")
    parser.add_argument("--items-output")
    parser.add_argument("--report-output")
    args = parser.parse_args()

    collected = collect_rss_sources(args.config)
    items = collected["items"]
    items_path = Path(args.items_output) if args.items_output else default_items_path(args.type)
    report_path = Path(args.report_output) if args.report_output else default_report_path(args.type)

    items_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    items_path.write_text(json.dumps(collected, ensure_ascii=False, indent=2), encoding="utf-8")

    report = generate_report_from_items(
        report_type=args.type,
        items=items,
        days=args.days,
        platform=args.platform,
        market=args.market,
        hs_code=args.hs_code,
        source_label=f"RSS批量采集 {args.config}",
    )
    report_path.write_text(report, encoding="utf-8")

    print(f"Wrote items to {items_path}")
    print(f"Wrote report to {report_path}")
    print(f"Stats: {collected['stats']}")


if __name__ == "__main__":
    main()
