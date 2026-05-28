#!/usr/bin/env python3
"""Refresh A-share quote snapshot from daily_stock_analysis data providers.

This script reads data/companies.json, fetches realtime quotes through
daily_stock_analysis's DataFetcherManager, and atomically rewrites
data/quotes.json for the static frontend.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.dsa_bridge import get_data_fetcher_manager
from scripts.json_utils import read_json, write_json_atomic


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPANIES_FILE = PROJECT_ROOT / "data" / "companies.json"
QUOTES_FILE = PROJECT_ROOT / "data" / "quotes.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_previous_quotes() -> dict[str, dict[str, Any]]:
    if not QUOTES_FILE.exists():
        return {}
    try:
        payload = read_json(QUOTES_FILE)
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(item.get("code")): item
        for item in payload.get("items", [])
        if isinstance(item, dict) and item.get("code")
    }


def _quote_to_payload(company: dict[str, Any], quote: Any, *, stale: bool = False) -> dict[str, Any]:
    source = getattr(quote, "source", None)
    source_value = getattr(source, "value", None) or str(source or "")
    return {
        "code": str(company["code"]),
        "name": getattr(quote, "name", None) or company.get("name") or str(company["code"]),
        "price": getattr(quote, "price", None),
        "changePercent": getattr(quote, "change_pct", None),
        "change": getattr(quote, "change_amount", None),
        "high": getattr(quote, "high", None),
        "low": getattr(quote, "low", None),
        "open": getattr(quote, "open_price", None),
        "previousClose": getattr(quote, "pre_close", None),
        "volume": getattr(quote, "volume", None),
        "amount": getattr(quote, "amount", None),
        "volumeRatio": getattr(quote, "volume_ratio", None),
        "turnoverRate": getattr(quote, "turnover_rate", None),
        "amplitude": getattr(quote, "amplitude", None),
        "peRatio": getattr(quote, "pe_ratio", None),
        "pbRatio": getattr(quote, "pb_ratio", None),
        "marketCap": getattr(quote, "total_mv", None),
        "floatMarketCap": getattr(quote, "circ_mv", None),
        "change60d": getattr(quote, "change_60d", None),
        "source": source_value,
        "updatedAt": _now_iso(),
        "status": "stale" if stale else "ok",
        "stale": stale,
    }


def _fallback_quote(company: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    if previous:
        item = dict(previous)
        item["stale"] = True
        item["status"] = "stale"
        item["error"] = "refresh_failed_using_previous_snapshot"
        return item
    return {
        "code": str(company["code"]),
        "name": company.get("name") or str(company["code"]),
        "price": None,
        "changePercent": None,
        "change": None,
        "high": None,
        "low": None,
        "open": None,
        "previousClose": None,
        "marketCap": None,
        "floatMarketCap": None,
        "source": "unavailable",
        "updatedAt": _now_iso(),
        "status": "unavailable",
        "stale": True,
        "error": "no_quote_available",
    }


def refresh_once(*, sleep_seconds: float = 0.25) -> dict[str, Any]:
    companies = read_json(COMPANIES_FILE)
    previous_quotes = _load_previous_quotes()
    manager = get_data_fetcher_manager()

    items: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for company in companies:
        code = str(company["code"])
        try:
            quote = manager.get_realtime_quote(code, log_final_failure=False)
        except Exception as exc:  # noqa: BLE001 - snapshot refresh must be fail-open
            quote = None
            failures.append({"code": code, "name": company.get("name", code), "error": str(exc)})

        if quote is None or not getattr(quote, "has_basic_data", lambda: False)():
            items.append(_fallback_quote(company, previous_quotes.get(code)))
            if not any(failure["code"] == code for failure in failures):
                failures.append({"code": code, "name": company.get("name", code), "error": "no quote"})
        else:
            items.append(_quote_to_payload(company, quote))

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    payload = {
        "source": "daily_stock_analysis.DataFetcherManager",
        "updatedAt": _now_iso(),
        "refreshIntervalHours": 12,
        "itemCount": len(items),
        "failureCount": len(failures),
        "failures": failures,
        "items": items,
    }
    write_json_atomic(QUOTES_FILE, payload)
    return payload


def run_loop(interval_hours: float, *, sleep_seconds: float) -> None:
    interval_seconds = max(1, int(interval_hours * 3600))
    while True:
        payload = refresh_once(sleep_seconds=sleep_seconds)
        print(
            f"[{payload['updatedAt']}] refreshed {payload['itemCount']} quotes "
            f"({payload['failureCount']} failures); next run in {interval_hours:g}h",
            flush=True,
        )
        time.sleep(interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh quote snapshot for A股AI扩张瓶颈地图.")
    parser.add_argument("--loop", action="store_true", help="Keep running and refresh repeatedly.")
    parser.add_argument("--interval-hours", type=float, default=12.0, help="Loop refresh interval. Default: 12.")
    parser.add_argument("--sleep-seconds", type=float, default=0.25, help="Delay between stock quote requests.")
    args = parser.parse_args()

    if args.loop:
        run_loop(args.interval_hours, sleep_seconds=args.sleep_seconds)
        return 0

    payload = refresh_once(sleep_seconds=args.sleep_seconds)
    print(
        f"Refreshed {payload['itemCount']} quotes at {payload['updatedAt']} "
        f"({payload['failureCount']} failures)."
    )
    if payload["failureCount"]:
        for failure in payload["failures"]:
            print(f"- {failure['code']} {failure['name']}: {failure['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
