#!/usr/bin/env python3
"""Build technical live cache from quote snapshots.

This is deliberately conservative: it uses available quote fields and marks
unknown history-derived metrics as null until a historical-data provider is wired.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from live_cache import DEFAULT_REPO_ROOT, now_iso, write_non_empty_cache


def finite(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) else default


def trend_state(change_60d: float | None, turnover: float, volume_ratio: float) -> str:
    change = finite(change_60d)
    if change > 80 or turnover > 12 or volume_ratio > 3:
        return "crowded"
    if change > 25 and volume_ratio >= 1:
        return "momentum"
    if change < -20:
        return "broken"
    return "early"


def crowdedness(change_60d: float | None, turnover: float, volume_ratio: float, pe: float) -> float:
    score = 0.0
    score += max(finite(change_60d), 0) * 0.5
    score += min(turnover, 20) * 2
    score += min(volume_ratio, 5) * 8
    if pe > 100:
        score += 20
    elif pe > 70:
        score += 10
    return max(0.0, min(100.0, score))


def build(repo_root: Path, symbols: set[str], limit: int) -> dict[str, Any]:
    quotes = json.loads((repo_root / "data" / "quotes.json").read_text(encoding="utf-8"))
    items = []
    for quote in quotes.get("items", []):
        code = str(quote.get("code"))
        if symbols and code not in symbols:
            continue
        turnover = finite(quote.get("turnoverRate"))
        volume_ratio = finite(quote.get("volumeRatio"))
        change_60d = quote.get("change60d")
        pe = finite(quote.get("peRatio"))
        state = trend_state(change_60d, turnover, volume_ratio)
        crowd = crowdedness(change_60d, turnover, volume_ratio, pe)
        items.append(
            {
                "symbol": code,
                "name": quote.get("name"),
                "source": quote.get("source"),
                "status": quote.get("status"),
                "price": quote.get("price"),
                "changePercent": quote.get("changePercent"),
                "change20d": None,
                "change60d": change_60d,
                "turnoverRate": quote.get("turnoverRate"),
                "amount": quote.get("amount"),
                "volumeRatio": quote.get("volumeRatio"),
                "newHigh": False,
                "drawdown": None,
                "relativeStrength": None,
                "volatility": None,
                "trendState": state,
                "crowdedness": round(crowd, 2),
            }
        )
        if limit and len(items) >= limit:
            break
    return {
        "source": "quotes.json",
        "updatedAt": now_iso(),
        "cacheName": "technicals",
        "items": items,
        "warnings": ["history-derived metrics are null until daily-history provider is wired"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build technical cache from quote snapshots.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--symbols", default="")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    symbols = {s.strip() for s in args.symbols.split(",") if s.strip()}
    payload = build(Path(args.repo_root).resolve(), symbols, args.limit)
    write_non_empty_cache(Path(args.repo_root).resolve(), "technicals", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
