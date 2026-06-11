#!/usr/bin/env python3
"""Independent data-provider bridge for snapshot refresh scripts.

The filename is kept for import compatibility with older scripts, but this
module no longer depends on the external daily_stock_analysis repository.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROVIDER_ROOT = PROJECT_ROOT / "skills" / "ai-bottleneck-stock-picker" / "scripts"
if str(PROVIDER_ROOT) not in sys.path:
    sys.path.insert(0, str(PROVIDER_ROOT))

from providers.common import clean, load_companies  # noqa: E402
from providers.financials import eastmoney_sec_id  # noqa: E402
from providers.http import get_json  # noqa: E402
from providers.http import get_text  # noqa: E402
from providers.news import search_bocha, search_brave, search_eastmoney_notice, search_serpapi  # noqa: E402


@dataclass
class Quote:
    code: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    change_amount: float | None = None
    high: float | None = None
    low: float | None = None
    open_price: float | None = None
    pre_close: float | None = None
    volume: float | None = None
    amount: float | None = None
    volume_ratio: float | None = None
    turnover_rate: float | None = None
    amplitude: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    total_mv: float | None = None
    circ_mv: float | None = None
    change_60d: float | None = None
    source: str = "eastmoney_quote"

    def has_basic_data(self) -> bool:
        return self.price is not None and self.change_pct is not None


@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str
    source: str
    published_date: str | None = None


@dataclass
class SearchResponse:
    query: str
    results: list[SearchResult]
    provider: str
    success: bool = True
    error_message: str = ""


class IndependentDataFetcherManager:
    def get_realtime_quote(self, code: str, log_final_failure: bool = False) -> Quote | None:  # noqa: ARG002
        try:
            return self._get_eastmoney_quote(code)
        except Exception:
            return self._get_tencent_quote(code)

    def _get_eastmoney_quote(self, code: str) -> Quote | None:
        payload = get_json(
            "https://push2.eastmoney.com/api/qt/stock/get",
            params={
                "secid": eastmoney_sec_id(code),
                "fields": "f43,f44,f45,f46,f47,f48,f49,f50,f57,f58,f60,f162,f167,f168,f169,f170,f171,f116,f117",
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            },
        )
        data = payload.get("data") or {}
        if not data:
            return None

        def scaled(key: str, scale: float = 100.0) -> float | None:
            value = data.get(key)
            if value in (None, "-", "--"):
                return None
            try:
                return float(value) / scale
            except (TypeError, ValueError):
                return None

        def raw(key: str) -> float | None:
            value = data.get(key)
            if value in (None, "-", "--"):
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        return Quote(
            code=code,
            name=str(data.get("f58") or data.get("f57") or code),
            price=scaled("f43"),
            high=scaled("f44"),
            low=scaled("f45"),
            open_price=scaled("f46"),
            volume=raw("f47"),
            amount=raw("f48"),
            volume_ratio=scaled("f50"),
            pre_close=scaled("f60"),
            pe_ratio=scaled("f162"),
            pb_ratio=scaled("f167"),
            turnover_rate=scaled("f168"),
            change_amount=scaled("f169"),
            change_pct=scaled("f170"),
            amplitude=scaled("f171"),
            total_mv=raw("f116"),
            circ_mv=raw("f117"),
        )

    def _get_tencent_quote(self, code: str) -> Quote | None:
        prefix = "sh" if code.startswith(("6", "5", "9")) else "sz"
        text = get_text(f"https://qt.gtimg.cn/q={prefix}{code}")
        match = re.search(r'="([^"]*)"', text)
        if not match:
            return None
        parts = match.group(1).split("~")

        def at(index: int) -> str:
            return parts[index] if index < len(parts) else ""

        def num(index: int, scale: float = 1.0) -> float | None:
            value = at(index)
            if value in {"", "-", "--"}:
                return None
            try:
                return float(value) * scale
            except ValueError:
                return None

        return Quote(
            code=code,
            name=at(1) or code,
            price=num(3),
            pre_close=num(4),
            open_price=num(5),
            volume=num(36),
            amount=num(37, 10000.0),
            high=num(33),
            low=num(34),
            change_amount=num(31),
            change_pct=num(32),
            turnover_rate=num(38),
            pe_ratio=num(39),
            amplitude=num(43),
            total_mv=num(45, 100000000.0),
            circ_mv=num(44, 100000000.0),
            pb_ratio=num(46),
            volume_ratio=num(49),
            source="tencent_quote",
        )


class IndependentSearchService:
    is_available = True
    _providers = ()

    def _search(self, query: str, code: str = "", name: str = "", max_results: int = 5) -> SearchResponse:
        failures = []
        for provider_name, provider in (
            ("bocha", lambda: search_bocha(query, max_results)),
            ("serpapi", lambda: search_serpapi(query, max_results)),
            ("brave", lambda: search_brave(query, max_results)),
            ("eastmoney_notice", lambda: search_eastmoney_notice(code, name, max_results) if code and name else []),
        ):
            try:
                rows = provider()
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{provider_name}: {exc}")
                continue
            if not rows:
                continue
            return SearchResponse(
                query=query,
                provider=provider_name,
                results=[
                    SearchResult(
                        title=clean(row.get("title"), 180),
                        snippet=clean(row.get("summary"), 500),
                        url=clean(row.get("url"), 700),
                        source=clean(row.get("source") or provider_name, 120),
                        published_date=clean(row.get("publishedAt"), 40),
                    )
                    for row in rows[:max_results]
                ],
            )
        return SearchResponse(query=query, provider="independent_search", results=[], success=False, error_message="; ".join(failures) or "no results")

    def search(self, query: str, max_results: int = 5, days: int = 30) -> SearchResponse:  # noqa: ARG002
        return self._search(query, max_results=max_results)

    def search_stock_news(self, code: str, name: str, max_results: int = 3) -> SearchResponse:
        return self._search(f"{name} {code} 最新 新闻 公告 业绩 风险", code, name, max_results=max_results)

    def search_comprehensive_intel(self, code: str, name: str, max_searches: int = 4) -> dict[str, SearchResponse]:
        dimensions = [
            ("latest_news", f"{name} {code} 最新 新闻 重大 事件"),
            ("announcements", f"{name} {code} 公告 年报 季报 投资者关系"),
            ("risk_check", f"{name} {code} 减持 处罚 违规 诉讼 利空 风险"),
            ("earnings", f"{name} {code} 业绩 营收 净利润 毛利率"),
            ("industry", f"{name} {code} AI 算力 订单 产能 产业链"),
        ][:max(1, max_searches)]
        return {dimension: self._search(query, code, name, max_results=3) for dimension, query in dimensions}


def get_data_fetcher_manager() -> IndependentDataFetcherManager:
    return IndependentDataFetcherManager()


def get_search_service() -> IndependentSearchService:
    return IndependentSearchService()


def load_stock_index() -> list[dict[str, Any]]:
    companies = json.loads((PROJECT_ROOT / "data" / "companies.json").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for company in companies:
        code = str(company.get("code") or "")
        name = str(company.get("name") or "")
        if not code or not name:
            continue
        rows.append(
            {
                "canonicalCode": code,
                "displayCode": code,
                "nameZh": name,
                "aliases": [],
                "market": "CN",
                "assetType": "stock",
                "active": True,
                "popularity": 0,
            }
        )
    return rows


def health() -> dict[str, Any]:
    errors: list[str] = []
    stock_count = 0
    try:
        stock_count = len(load_stock_index())
    except Exception as exc:  # noqa: BLE001
        errors.append(f"stock_index: {exc}")
    return {
        "provider": "independent",
        "externalRepositoryRequired": False,
        "stockIndexSource": "data/companies.json",
        "stockIndexCount": stock_count,
        "importsOk": True,
        "searchAvailable": True,
        "errors": errors,
    }
