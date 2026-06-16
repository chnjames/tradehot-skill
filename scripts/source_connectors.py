#!/usr/bin/env python3
"""Source connectors for tradehot.

The first production-style connector is RSS/Atom. It accepts a URL or local XML
file and returns raw dictionaries that can be normalized by fetch_news.py.
"""

from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Optional

HTML_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def read_text(location: str, timeout: int = 15) -> str:
    """Read text from an HTTP(S) URL or local file path."""
    if location.startswith(("http://", "https://")):
        request = urllib.request.Request(
            location,
            headers={"User-Agent": "tradehot-skill/0.2 (+https://local.agent)"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    path = Path(location)
    if not path.exists() and not path.is_absolute():
        script_dir = Path(__file__).resolve().parent
        candidates = [
            Path.cwd() / location,
            script_dir / location,
            script_dir.parent / location,
        ]
        path = next((candidate for candidate in candidates if candidate.exists()), path)
    return path.read_text(encoding="utf-8")


def clean_text(value: Optional[str]) -> str:
    """Remove common HTML markup and normalize whitespace."""
    text = HTML_RE.sub(" ", value or "")
    return SPACE_RE.sub(" ", text).strip()


def normalize_feed_date(value: Optional[str]) -> str:
    """Convert RSS/Atom dates to YYYY-MM-DD when possible."""
    if not value:
        return str(date.today())
    text = value.strip()
    try:
        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    if len(text) >= 10:
        return text[:10]
    return str(date.today())


def _find_text(node: ET.Element, names: List[str]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return clean_text(found.text)
    for child in node:
        local_name = child.tag.split("}", 1)[-1]
        if local_name in names and child.text:
            return clean_text(child.text)
    return ""


def _find_link(node: ET.Element) -> str:
    direct = _find_text(node, ["link"])
    if direct:
        return direct
    for child in node:
        local_name = child.tag.split("}", 1)[-1]
        if local_name == "link":
            href = child.attrib.get("href")
            if href:
                return href
    return ""


def _rss_channel_title(root: ET.Element) -> str:
    channel = root.find("channel")
    if channel is not None:
        return _find_text(channel, ["title"])
    return _find_text(root, ["title"])


def parse_feed_items(
    location: str,
    source_name: Optional[str] = None,
    source_tier: str = "news",
) -> List[Dict[str, object]]:
    """Parse RSS or Atom feed items from a URL or local XML file."""
    xml_text = read_text(location)
    root = ET.fromstring(xml_text)
    source = source_name or _rss_channel_title(root) or location

    nodes = root.findall("./channel/item")
    if not nodes:
        nodes = [
            child for child in root
            if child.tag.split("}", 1)[-1] == "entry"
        ]

    items: List[Dict[str, object]] = []
    for node in nodes:
        title = _find_text(node, ["title"])
        summary = _find_text(node, ["description", "summary", "content"])
        url = _find_link(node)
        published = _find_text(node, ["pubDate", "published", "updated"])
        published_date = normalize_feed_date(published)
        if not title:
            continue
        items.append(
            {
                "title": title,
                "summary": summary or title,
                "url": url,
                "source_url": url,
                "source_name": source,
                "source": source_tier,
                "source_tier": source_tier,
                "published_date": published_date,
                "published_at": published or published_date,
                "retrieved_at": str(date.today()),
                "confidence": 55 if source_tier in {"news", "industry_media", "logistics_media"} else 70,
                "evidence": summary or title,
            }
        )
    return items


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Parse RSS/Atom into raw tradehot items.")
    parser.add_argument("location")
    parser.add_argument("--source-name")
    parser.add_argument("--source-tier", default="news")
    args = parser.parse_args()
    print(json.dumps(parse_feed_items(args.location, args.source_name, args.source_tier), ensure_ascii=False, indent=2))
