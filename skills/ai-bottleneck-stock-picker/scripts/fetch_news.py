#!/usr/bin/env python3
"""Fetch live news via daily_stock_analysis SearchService."""

from __future__ import annotations

import argparse
import hashlib
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


def clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").split())[:limit]


def stable_id(symbol: str, title: str, url: str) -> str:
    return hashlib.sha1(f"{symbol}|{title}|{url}".encode("utf-8")).hexdigest()[:16]


def signal_type(title: str, summary: str) -> str:
    text = f"{title} {summary}"
    if any(term in text for term in ("减持", "处罚", "诉讼", "立案", "亏损", "下滑", "风险")):
        return "risk"
    if any(term in text for term in ("订单", "中标", "客户", "供应商", "认证")):
        return "customer"
    if any(term in text for term in ("扩产", "产能", "满产", "交付")):
        return "capacity"
    if any(term in text for term in ("业绩", "营收", "净利润", "毛利率", "财报")):
        return "earnings"
    if any(term in text for term in ("涨价", "价格", "供不应求")):
        return "price"
    return "industry"


def sentiment(title: str, summary: str) -> str:
    text = f"{title} {summary}"
    if any(term in text for term in ("减持", "处罚", "诉讼", "亏损", "下滑", "风险", "利空")):
        return "negative"
    if any(term in text for term in ("增长", "预增", "订单", "中标", "扩产", "满产", "突破", "涨价")):
        return "positive"
    return "neutral"


def load_companies(repo_root: Path, symbols: set[str], limit: int) -> list[dict[str, Any]]:
    companies = json.loads((repo_root / "data" / "companies.json").read_text(encoding="utf-8"))
    if symbols:
        return [c for c in companies if str(c.get("code")) in symbols]
    ranking = json.loads((repo_root / "data" / "ranking.json").read_text(encoding="utf-8"))
    top_codes = [str(row.get("code")) for row in ranking.get("rows", [])[:limit]]
    by_code = {str(c.get("code")): c for c in companies}
    return [by_code[code] for code in top_codes if code in by_code]


def fetch(repo_root: Path, symbols: set[str], limit: int, results_per_company: int) -> dict[str, Any]:
    add_dsa_path()
    from src.search_service import get_search_service

    service = get_search_service()
    if not getattr(service, "is_available", False):
        raise RuntimeError("SearchService is not available")

    items = []
    failures = []
    for company in load_companies(repo_root, symbols, limit):
        code = str(company.get("code"))
        name = str(company.get("name"))
        try:
            response = service.search_stock_news(code, name, max_results=max(1, results_per_company))
        except Exception as exc:  # noqa: BLE001
            failures.append({"symbol": code, "name": name, "error": str(exc)})
            continue
        if not getattr(response, "success", False):
            failures.append({"symbol": code, "name": name, "error": getattr(response, "error_message", "search failed")})
            continue
        for result in getattr(response, "results", [])[:results_per_company]:
            title = clean(getattr(result, "title", ""), 160)
            summary = clean(getattr(result, "snippet", ""), 500)
            url = clean(getattr(result, "url", ""), 600)
            items.append(
                {
                    "id": stable_id(code, title, url),
                    "symbol": code,
                    "name": name,
                    "title": title,
                    "url": url,
                    "source": clean(getattr(result, "source", "") or getattr(response, "provider", ""), 120),
                    "publishedAt": clean(getattr(result, "published_date", ""), 40),
                    "summary": summary,
                    "signalType": signal_type(title, summary),
                    "sentiment": sentiment(title, summary),
                    "confidence": 0.68,
                    "provider": getattr(response, "provider", ""),
                    "query": getattr(response, "query", ""),
                }
            )
    payload = {
        "source": "daily_stock_analysis.SearchService",
        "updatedAt": now_iso(),
        "cacheName": "live_news",
        "items": items,
        "failureCount": len(failures),
        "failures": failures,
        "warnings": [],
    }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch live news cache.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--symbols", default="")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--results-per-company", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    symbols = {s.strip() for s in args.symbols.split(",") if s.strip()}
    try:
        payload = fetch(repo_root, symbols, args.limit, args.results_per_company)
        payload = write_non_empty_cache(repo_root, "live_news", payload)
    except Exception as exc:  # noqa: BLE001
        payload = read_cache(repo_root, "live_news")
        payload = dict(payload)
        payload["warnings"] = list(payload.get("warnings", [])) + [f"live_news refresh failed: {exc}"]
        write_cache(repo_root, "live_news", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
