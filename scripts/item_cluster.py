#!/usr/bin/env python3
"""Lightweight event deduplication and clustering for tradehot items."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Set

TOKEN_RE = re.compile(r"[a-zA-Z0-9\u4e00-\u9fff]+")


def title_tokens(title: object) -> Set[str]:
    """Tokenize Chinese/English titles into a small comparable set."""
    text = str(title or "").lower()
    return {token for token in TOKEN_RE.findall(text) if len(token) > 1}


def title_similarity(a: object, b: object) -> float:
    """Return Jaccard similarity between two titles."""
    left = title_tokens(a)
    right = title_tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _merge_list_values(primary: Dict[str, object], secondary: Dict[str, object], field: str) -> None:
    seen = {str(x) for x in primary.get(field, [])}
    merged = list(primary.get(field, []))
    for value in secondary.get(field, []):
        text = str(value)
        if text not in seen:
            seen.add(text)
            merged.append(text)
    primary[field] = merged


def merge_items(primary: Dict[str, object], secondary: Dict[str, object]) -> Dict[str, object]:
    """Merge two likely duplicate event items, preserving the stronger fields."""
    merged = dict(primary)
    for field in ["markets", "platforms", "categories", "hs_codes"]:
        _merge_list_values(merged, secondary, field)

    primary_conf = int(merged.get("confidence", 0) or 0)
    secondary_conf = int(secondary.get("confidence", 0) or 0)
    if secondary_conf > primary_conf:
        for field in [
            "source",
            "source_name",
            "source_url",
            "source_tier",
            "url",
            "published_date",
            "published_at",
            "retrieved_at",
            "confidence",
        ]:
            if secondary.get(field):
                merged[field] = secondary[field]

    evidence_parts = [
        str(merged.get("evidence") or merged.get("summary") or "").strip(),
        str(secondary.get("evidence") or secondary.get("summary") or "").strip(),
    ]
    merged["evidence"] = " / ".join(dict.fromkeys(part for part in evidence_parts if part))
    if not merged.get("summary") and secondary.get("summary"):
        merged["summary"] = secondary["summary"]
    return merged


def cluster_items(
    items: Iterable[Dict[str, object]],
    threshold: float = 0.82,
) -> List[Dict[str, object]]:
    """Merge items with identical URLs or very similar titles."""
    clustered: List[Dict[str, object]] = []
    seen_urls: Dict[str, int] = {}

    for item in items:
        url = str(item.get("source_url") or item.get("url") or "").strip().lower()
        if url and url in seen_urls:
            idx = seen_urls[url]
            clustered[idx] = merge_items(clustered[idx], item)
            continue

        matched_idx = None
        for idx, existing in enumerate(clustered):
            if title_similarity(existing.get("title"), item.get("title")) >= threshold:
                matched_idx = idx
                break

        if matched_idx is None:
            if url:
                seen_urls[url] = len(clustered)
            clustered.append(dict(item))
        else:
            clustered[matched_idx] = merge_items(clustered[matched_idx], item)
            if url:
                seen_urls[url] = matched_idx

    return clustered


if __name__ == "__main__":
    demo = [
        {"title": "Amazon seller policy update for fees", "url": "https://example.com/a"},
        {"title": "Amazon seller policy update fees", "url": "https://example.com/b"},
    ]
    print(cluster_items(demo))
