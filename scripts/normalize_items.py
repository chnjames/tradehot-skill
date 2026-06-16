#!/usr/bin/env python3
"""Normalize raw tradehot items into the shared tradehot schema."""

from __future__ import annotations

from item_schema import DEFAULT_ITEM, normalize_item, normalize_items


if __name__ == "__main__":
    print(normalize_item({"title": "Demo"}))
