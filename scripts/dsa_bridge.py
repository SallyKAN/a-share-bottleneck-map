#!/usr/bin/env python3
"""Bridge to the local daily_stock_analysis checkout."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


DSA_ROOT = Path(os.environ.get("DSA_ROOT", "/home/snape/github/daily_stock_analysis"))
STOCK_INDEX_FILE = DSA_ROOT / "apps" / "dsa-web" / "public" / "stocks.index.json"


def ensure_dsa_importable() -> None:
    if not DSA_ROOT.exists():
        raise RuntimeError(f"daily_stock_analysis not found: {DSA_ROOT}")
    dsa_path = str(DSA_ROOT)
    if dsa_path not in sys.path:
        sys.path.insert(0, dsa_path)


def get_data_fetcher_manager() -> Any:
    ensure_dsa_importable()
    from data_provider import DataFetcherManager

    return DataFetcherManager()


def get_search_service() -> Any:
    ensure_dsa_importable()
    from src.search_service import get_search_service as _get_search_service

    return _get_search_service()


def load_stock_index() -> list[dict[str, Any]]:
    if not STOCK_INDEX_FILE.exists():
        raise RuntimeError(f"DSA stock index not found: {STOCK_INDEX_FILE}")
    with STOCK_INDEX_FILE.open("r", encoding="utf-8") as fp:
        rows = json.load(fp)

    items: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            item = row
        elif isinstance(row, list) and len(row) >= 9:
            item = {
                "canonicalCode": row[0],
                "displayCode": row[1],
                "nameZh": row[2],
                "pinyinFull": row[3],
                "pinyinAbbr": row[4],
                "aliases": row[5] if isinstance(row[5], list) else [],
                "market": row[6],
                "assetType": row[7],
                "active": row[8],
                "popularity": row[9] if len(row) > 9 else 0,
            }
        else:
            continue
        items.append(item)
    return items


def health() -> dict[str, Any]:
    payload = {
        "dsaRoot": str(DSA_ROOT),
        "dsaRootExists": DSA_ROOT.exists(),
        "stockIndexPath": str(STOCK_INDEX_FILE),
        "stockIndexExists": STOCK_INDEX_FILE.exists(),
        "stockIndexCount": 0,
        "importsOk": False,
        "searchAvailable": False,
        "errors": [],
    }
    try:
        payload["stockIndexCount"] = len(load_stock_index())
    except Exception as exc:  # noqa: BLE001 - health endpoint should be diagnostic
        payload["errors"].append(f"stock_index: {exc}")
    try:
        ensure_dsa_importable()
        payload["importsOk"] = True
    except Exception as exc:  # noqa: BLE001
        payload["errors"].append(f"imports: {exc}")
    try:
        service = get_search_service()
        payload["searchAvailable"] = bool(getattr(service, "is_available", False))
    except Exception as exc:  # noqa: BLE001
        payload["errors"].append(f"search: {exc}")
    return payload
