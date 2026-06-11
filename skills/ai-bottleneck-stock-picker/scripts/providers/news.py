"""Independent news providers."""

from __future__ import annotations

import hashlib
import os
from typing import Any

from .common import clean, load_companies
from .http import get_json


def stable_id(symbol: str, title: str, url: str) -> str:
    return hashlib.sha1(f"{symbol}|{title}|{url}".encode("utf-8")).hexdigest()[:16]


def signal_type(title: str, summary: str) -> str:
    text = f"{title} {summary}"
    if any(term in text for term in ("减持", "处罚", "诉讼", "立案", "亏损", "下滑", "风险", "问询")):
        return "risk"
    if any(term in text for term in ("订单", "中标", "客户", "供应商", "认证")):
        return "customer"
    if any(term in text for term in ("扩产", "产能", "满产", "交付")):
        return "capacity"
    if any(term in text for term in ("业绩", "营收", "净利润", "毛利率", "财报", "一季报", "半年报", "年报")):
        return "earnings"
    if any(term in text for term in ("涨价", "价格", "供不应求")):
        return "price"
    return "industry"


def sentiment(title: str, summary: str) -> str:
    text = f"{title} {summary}"
    if any(term in text for term in ("减持", "处罚", "诉讼", "亏损", "下滑", "风险", "利空", "问询")):
        return "negative"
    if any(term in text for term in ("增长", "预增", "订单", "中标", "扩产", "满产", "突破", "涨价", "同比增加")):
        return "positive"
    return "neutral"


def normalize_item(symbol: str, name: str, title: Any, summary: Any, url: Any, source: str, published_at: Any, provider: str, query: str) -> dict[str, Any]:
    title_text = clean(title, 180)
    summary_text = clean(summary, 500)
    url_text = clean(url, 700)
    return {
        "id": stable_id(symbol, title_text, url_text),
        "symbol": symbol,
        "name": name,
        "title": title_text,
        "url": url_text,
        "source": clean(source or provider, 120),
        "publishedAt": clean(published_at, 40),
        "summary": summary_text,
        "signalType": signal_type(title_text, summary_text),
        "sentiment": sentiment(title_text, summary_text),
        "confidence": 0.62 if provider.endswith("_fallback") else 0.7,
        "provider": provider,
        "query": query,
    }


def env_keys(*names: str) -> list[str]:
    keys: list[str] = []
    for name in names:
        for value in os.environ.get(name, "").split(","):
            key = value.strip()
            if key and key not in keys:
                keys.append(key)
    return keys


def search_bocha(query: str, limit: int) -> list[dict[str, Any]]:
    keys = env_keys("AI_PICKER_BOCHA_API_KEYS", "AI_PICKER_BOCHA_API_KEY", "BOCHA_API_KEYS", "BOCHA_API_KEY")
    if not keys:
        return []
    import requests

    last_error: Exception | None = None
    for api_key in keys:
        try:
            response = requests.post(
                "https://api.bochaai.com/v1/web-search",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"query": query, "summary": True, "count": limit},
                timeout=12,
            )
            response.raise_for_status()
            results = response.json().get("webPages", {}).get("value", [])
            return [
                {
                    "title": item.get("name"),
                    "summary": item.get("summary") or item.get("snippet"),
                    "url": item.get("url"),
                    "source": item.get("siteName") or "bocha",
                    "publishedAt": item.get("datePublished") or item.get("dateLastCrawled"),
                }
                for item in results[:limit]
            ]
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    if last_error:
        raise last_error
    return []


def search_serpapi(query: str, limit: int) -> list[dict[str, Any]]:
    keys = env_keys("AI_PICKER_SERPAPI_API_KEYS", "AI_PICKER_SERPAPI_API_KEY", "SERPAPI_API_KEYS", "SERPAPI_API_KEY")
    if not keys:
        return []
    last_error: Exception | None = None
    for api_key in keys:
        try:
            payload = get_json(
                "https://serpapi.com/search.json",
                params={"engine": "baidu", "q": query, "api_key": api_key, "num": limit},
                timeout=15,
            )
            results = payload.get("organic_results") or []
            return [
                {
                    "title": item.get("title"),
                    "summary": item.get("snippet"),
                    "url": item.get("link"),
                    "source": item.get("displayed_link") or "serpapi",
                    "publishedAt": item.get("date"),
                }
                for item in results[:limit]
            ]
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    if last_error:
        raise last_error
    return []


def search_brave(query: str, limit: int) -> list[dict[str, Any]]:
    keys = env_keys("AI_PICKER_BRAVE_API_KEYS", "AI_PICKER_BRAVE_API_KEY", "BRAVE_API_KEYS", "BRAVE_API_KEY")
    if not keys:
        return []
    from .http import DEFAULT_HEADERS
    import requests

    last_error: Exception | None = None
    for api_key in keys:
        try:
            headers = dict(DEFAULT_HEADERS)
            headers["X-Subscription-Token"] = api_key
            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": limit, "country": "CN", "search_lang": "zh-hans"},
                headers=headers,
                timeout=8,
            )
            response.raise_for_status()
            results = response.json().get("web", {}).get("results", [])
            return [
                {
                    "title": item.get("title"),
                    "summary": item.get("description"),
                    "url": item.get("url"),
                    "source": item.get("profile", {}).get("name") or "brave",
                    "publishedAt": item.get("age"),
                }
                for item in results[:limit]
            ]
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    if last_error:
        raise last_error
    return []


def search_eastmoney_notice(symbol: str, name: str, limit: int) -> list[dict[str, Any]]:
    payload = get_json(
        "https://np-anotice-stock.eastmoney.com/api/security/ann",
        params={
            "sr": "-1",
            "page_size": limit,
            "page_index": 1,
            "ann_type": "A",
            "client_source": "web",
            "stock_list": symbol,
        },
    )
    rows = payload.get("data", {}).get("list") or payload.get("data") or []
    items = []
    for row in rows[:limit]:
        title = row.get("title") or row.get("notice_title")
        codes = row.get("codes") or []
        date = row.get("notice_date") or row.get("display_time")
        art_code = row.get("art_code") or row.get("notice_id")
        url = row.get("url") or (f"https://data.eastmoney.com/notices/detail/{symbol}/{art_code}.html" if art_code else "")
        summary = f"{name}公告：{title}"
        items.append({"title": title, "summary": summary, "url": url, "source": "eastmoney_notice", "publishedAt": date, "codes": codes})
    return items


def fetch_news(repo_root, symbols: set[str], limit: int, results_per_company: int) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    providers_used: set[str] = set()
    for company in load_companies(repo_root, symbols, limit):
        code = str(company.get("code"))
        name = str(company.get("name"))
        query = f"{name} {code} AI 算力 订单 产能 业绩 风险"
        raw_results: list[dict[str, Any]] = []
        for provider_name, provider in (
            ("bocha", lambda: search_bocha(query, results_per_company)),
            ("serpapi", lambda: search_serpapi(query, results_per_company)),
            ("brave", lambda: search_brave(query, results_per_company)),
            ("eastmoney_notice_fallback", lambda: search_eastmoney_notice(code, name, results_per_company)),
        ):
            try:
                results = provider()
            except Exception as exc:  # noqa: BLE001
                failures.append({"symbol": code, "name": name, "provider": provider_name, "error": str(exc)})
                continue
            if results:
                providers_used.add(provider_name)
                raw_results.extend(results)
                break
        for result in raw_results[:results_per_company]:
            items.append(
                normalize_item(
                    code,
                    name,
                    result.get("title"),
                    result.get("summary"),
                    result.get("url"),
                    result.get("source") or "",
                    result.get("publishedAt"),
                    result.get("source") or next(iter(providers_used), "unknown"),
                    query,
                )
            )
    warnings = []
    if not any(
        os.environ.get(key)
        for key in (
            "AI_PICKER_BOCHA_API_KEYS",
            "AI_PICKER_BOCHA_API_KEY",
            "BOCHA_API_KEYS",
            "BOCHA_API_KEY",
            "AI_PICKER_SERPAPI_API_KEYS",
            "AI_PICKER_SERPAPI_API_KEY",
            "SERPAPI_API_KEYS",
            "SERPAPI_API_KEY",
            "AI_PICKER_BRAVE_API_KEYS",
            "AI_PICKER_BRAVE_API_KEY",
            "BRAVE_API_KEYS",
            "BRAVE_API_KEY",
        )
    ):
        warnings.append("no search API key configured; used exchange/notice fallback only")
    return {
        "source": ",".join(sorted(providers_used)) if providers_used else "independent_news_providers",
        "items": items,
        "failureCount": len(failures),
        "failures": failures,
        "warnings": warnings,
    }
