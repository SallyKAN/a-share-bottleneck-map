#!/usr/bin/env python3
"""Fetch V2 financial confirmation cache via daily_stock_analysis."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from live_cache import DEFAULT_REPO_ROOT, now_iso, read_cache, write_cache, write_non_empty_cache


def add_dsa_path() -> None:
    dsa_root = Path(os.environ.get("DSA_ROOT", "/home/snape/github/daily_stock_analysis"))
    if str(dsa_root) not in sys.path:
        sys.path.insert(0, str(dsa_root))


def finite(value: Any, default: float | None = None) -> float | None:
    return float(value) if isinstance(value, (int, float)) else default


def load_symbols(repo_root: Path, symbols: set[str], limit: int) -> list[str]:
    if symbols:
        return sorted(symbols)
    ranking = json.loads((repo_root / "data" / "ranking.json").read_text(encoding="utf-8"))
    return [str(row.get("code")) for row in ranking.get("rows", [])[:limit] if row.get("code")]


def confirmation_score(item: dict[str, Any]) -> float:
    score = 50.0
    for key in ("revenueYoY", "netProfitYoY"):
        value = finite(item.get(key))
        if value is not None:
            score += max(min(value, 60), -60) * 0.25
    gross = finite(item.get("grossMargin"))
    if gross is not None:
        score += max(min(gross, 60), 0) * 0.2
    cash = finite(item.get("operatingCashFlow"))
    if cash is not None and cash < 0:
        score -= 8
    return max(0.0, min(100.0, score))


def pick(dct: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in dct:
            return dct.get(key)
    return None


def flatten_context(symbol: str, ctx: dict[str, Any]) -> dict[str, Any]:
    valuation = ctx.get("valuation", {}).get("payload", {}) if isinstance(ctx.get("valuation"), dict) else {}
    earnings = ctx.get("earnings", {}).get("payload", {}) if isinstance(ctx.get("earnings"), dict) else {}
    growth = ctx.get("growth", {}).get("payload", {}) if isinstance(ctx.get("growth"), dict) else {}
    report = earnings.get("financial_report", {}) if isinstance(earnings.get("financial_report"), dict) else {}
    item = {
        "symbol": symbol,
        "period": pick(report, "report_date", "period"),
        "revenueYoY": finite(pick(growth, "revenue_yoy", "revenue_growth_yoy", "revenueYoY")),
        "netProfitYoY": finite(pick(growth, "net_profit_yoy", "net_profit_growth_yoy", "netProfitYoY")),
        "grossMargin": finite(pick(report, "gross_margin", "grossMargin")),
        "operatingCashFlow": finite(pick(report, "operating_cash_flow", "operatingCashFlow")),
        "inventory": finite(pick(report, "inventory")),
        "contractLiabilities": finite(pick(report, "contract_liabilities", "contractLiabilities")),
        "capex": finite(pick(report, "capex")),
        "rdExpense": finite(pick(report, "rd_expense", "rdExpense")),
        "peRatio": finite(pick(valuation, "pe_ratio", "peRatio")),
        "pbRatio": finite(pick(valuation, "pb_ratio", "pbRatio")),
        "marketCap": finite(pick(valuation, "total_mv", "marketCap")),
        "sourceStatus": {
            "valuation": ctx.get("valuation", {}).get("status") if isinstance(ctx.get("valuation"), dict) else None,
            "earnings": ctx.get("earnings", {}).get("status") if isinstance(ctx.get("earnings"), dict) else None,
            "growth": ctx.get("growth", {}).get("status") if isinstance(ctx.get("growth"), dict) else None,
        },
        "errors": ctx.get("errors", []),
    }
    item["financialConfirmation"] = round(confirmation_score(item), 2)
    return item


def fetch(repo_root: Path, symbols: set[str], limit: int) -> dict[str, Any]:
    add_dsa_path()
    from data_provider import DataFetcherManager

    manager = DataFetcherManager()
    items = []
    failures = []
    for symbol in load_symbols(repo_root, symbols, limit):
        try:
            ctx = manager.get_fundamental_context(symbol, budget_seconds=8)
            items.append(flatten_context(symbol, ctx))
        except Exception as exc:  # noqa: BLE001
            failures.append({"symbol": symbol, "error": str(exc)})
    return {
        "source": "daily_stock_analysis.DataFetcherManager.get_fundamental_context",
        "updatedAt": now_iso(),
        "cacheName": "financials",
        "items": items,
        "failureCount": len(failures),
        "failures": failures,
        "warnings": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch financial confirmation cache.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--symbols", default="")
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    symbols = {s.strip() for s in args.symbols.split(",") if s.strip()}
    try:
        payload = fetch(repo_root, symbols, args.limit)
        payload = write_non_empty_cache(repo_root, "financials", payload)
    except Exception as exc:  # noqa: BLE001
        payload = read_cache(repo_root, "financials")
        payload = dict(payload)
        payload["warnings"] = list(payload.get("warnings", [])) + [f"financials refresh failed: {exc}"]
        write_cache(repo_root, "financials", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
