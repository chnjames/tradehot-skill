#!/usr/bin/env python3
"""Load configured tradehot sources.

This module does not perform network requests. It loads JSON source definitions
so that other scripts can decide what to fetch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT / "sources"


def load_json(filename: str) -> Dict[str, Any]:
    path = SOURCES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_all_sources() -> Dict[str, Any]:
    data = {
        "zh": load_json("sources.zh.json"),
        "en": load_json("sources.en.json"),
        "platforms": load_json("platforms.json"),
        "markets": load_json("markets.json"),
    }
    # Load optional knowledge-base files
    for optional_file in [
        "tariff_reference.json",
        "trade_calendar.json",
        "competitors.json",
        "logistics_hotspots.json",
        "fx_risk.json",
    ]:
        key = optional_file.replace(".json", "")
        path = SOURCES_DIR / optional_file
        if path.exists():
            try:
                data[key] = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data[key] = {}
        else:
            data[key] = {}
    # Optionally load user preferences
    user_config_path = SOURCES_DIR / "user_config.json"
    if user_config_path.exists():
        try:
            data["user_config"] = json.loads(
                user_config_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            data["user_config"] = {}
    else:
        data["user_config"] = {}
    return data


def flatten_sources() -> List[Dict[str, Any]]:
    data = load_all_sources()
    sources: List[Dict[str, Any]] = []
    sources.extend(data["zh"].get("sources", []))
    sources.extend(data["en"].get("sources", []))
    for platform in data["platforms"].get("platforms", []):
        sources.append(
            {
                "name": platform["name"],
                "url": platform.get("official_url"),
                "type": "platform_official",
                "priority": 5,
                "topics": platform.get("topics", []),
            }
        )
    return sources


if __name__ == "__main__":
    for item in flatten_sources():
        print(f"[{item.get('priority')}] {item.get('name')} - {item.get('url')}")
