#!/usr/bin/env python3
"""Refresh research evidence from daily_stock_analysis search providers."""

from __future__ import annotations

import argparse
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.dsa_bridge import get_search_service
from scripts.json_utils import read_json, write_json_atomic


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPANIES_FILE = PROJECT_ROOT / "data" / "companies.json"
EVIDENCE_FILE = PROJECT_ROOT / "data" / "evidence.json"

DIMENSION_TYPES = {
    "latest_news": "最新消息",
    "announcements": "公司公告",
    "market_analysis": "机构分析",
    "risk_check": "风险排查",
    "earnings": "业绩预期",
    "industry": "行业分析",
}

NEGATIVE_TERMS = (
    "减持",
    "处罚",
    "违规",
    "诉讼",
    "立案",
    "问询",
    "利空",
    "下滑",
    "下降",
    "亏损",
    "风险",
    "终止",
    "撤回",
    "跌",
)
POSITIVE_TERMS = (
    "增长",
    "预增",
    "创新高",
    "订单",
    "中标",
    "突破",
    "合作",
    "扩产",
    "量产",
    "盈利",
    "提升",
    "涨",
)


OFFICIAL_DOMAINS = ("cninfo.com.cn", "sse.com.cn", "szse.cn")
FINANCIAL_TERMS = ("财报", "年报", "半年报", "季报", "业绩预告", "业绩快报", "营收", "净利润")
RESEARCH_TERMS = ("研报", "评级", "目标价", "深度分析", "调研")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now(timezone.utc).astimezone().date().isoformat()


def _clean_text(value: Any, *, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _stable_id(company_id: str, dimension: str, title: str, url: str) -> str:
    digest = hashlib.sha1(f"{company_id}|{dimension}|{title}|{url}".encode("utf-8")).hexdigest()[:10]
    return f"ev-{company_id}-{dimension}-{digest}"


def _dedupe_key(company_id: str, title: str, url: str, date: str) -> str:
    normalized = " ".join(title.lower().split())[:80]
    raw = url or f"{company_id}|{date}|{normalized}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _source_tier(source: str, url: str, title: str, snippet: str) -> str:
    text = f"{source} {url} {title} {snippet}".lower()
    if any(domain in text for domain in OFFICIAL_DOMAINS):
        return "official"
    if any(term in f"{title} {snippet}" for term in FINANCIAL_TERMS):
        return "financial"
    if any(term in f"{title} {snippet}" for term in RESEARCH_TERMS):
        return "research"
    if source:
        return "reputable_media"
    return "search_web"


def _evidence_kind(dimension: str, title: str, snippet: str, source_tier: str) -> str:
    text = f"{title} {snippet}"
    if source_tier == "official" or dimension == "announcements":
        return "announcement"
    if dimension == "earnings" or any(term in text for term in FINANCIAL_TERMS):
        return "financial_report"
    if dimension == "risk_check":
        return "risk"
    if dimension == "market_analysis" or any(term in text for term in RESEARCH_TERMS):
        return "research_note"
    return "news"


def _classify_sentiment(dimension: str, title: str, snippet: str) -> tuple[str, float]:
    text = f"{title} {snippet}"
    if dimension == "risk_check" or any(term in text for term in NEGATIVE_TERMS):
        return "negative", 0.72
    if dimension in {"earnings", "latest_news", "announcements"} and any(term in text for term in POSITIVE_TERMS):
        return "positive", 0.68
    return "neutral", 0.58


def _result_date(value: Any) -> str:
    if not value:
        return _today()
    text = str(value).strip()
    if len(text) >= 10:
        return text[:10]
    return _today()


def _result_to_evidence(company: dict[str, Any], dimension: str, response: Any, result: Any) -> dict[str, Any]:
    title = _clean_text(getattr(result, "title", ""), limit=120)
    snippet = _clean_text(getattr(result, "snippet", ""), limit=260)
    url = _clean_text(getattr(result, "url", ""), limit=500)
    source = _clean_text(getattr(result, "source", "") or getattr(response, "provider", ""), limit=120)
    sentiment, confidence = _classify_sentiment(dimension, title, snippet)
    sector_id = (company.get("sectorIds") or ["unknown"])[0]
    date = _result_date(getattr(result, "published_date", None))
    tier = _source_tier(source, url, title, snippet)
    kind = _evidence_kind(dimension, title, snippet, tier)

    return {
        "id": _stable_id(str(company["id"]), dimension, title, url),
        "companyId": company["id"],
        "sectorId": sector_id,
        "date": date,
        "type": DIMENSION_TYPES.get(dimension, dimension),
        "evidenceKind": kind,
        "sourceTier": tier,
        "sentiment": sentiment,
        "confidence": confidence,
        "title": title or "未命名搜索结果",
        "summary": snippet or "搜索结果未返回摘要，需打开来源核验。",
        "source": source or getattr(response, "provider", "search"),
        "url": url,
        "provider": getattr(response, "provider", ""),
        "query": getattr(response, "query", ""),
        "dedupeKey": _dedupe_key(str(company["id"]), title, url, date),
        "needsReview": tier not in {"official", "financial"},
        "usedForAdmission": tier in {"official", "financial"},
        "fetchedAt": _now_iso(),
    }


def refresh_evidence_once(
    *,
    max_companies: int = 0,
    max_searches: int = 4,
    results_per_dimension: int = 2,
    sleep_seconds: float = 0.2,
) -> dict[str, Any]:
    companies = read_json(COMPANIES_FILE)
    selected = companies if max_companies <= 0 else companies[:max_companies]
    service = get_search_service()
    if not service.is_available:
        raise RuntimeError(
            "daily_stock_analysis 搜索服务不可用：未配置 Bocha/Tavily/Brave/SerpAPI/MiniMax/SearXNG。"
        )

    items: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    seen_keys: set[str] = set()

    for company in selected:
        code = str(company["code"])
        name = str(company["name"])
        try:
            intel = service.search_comprehensive_intel(code, name, max_searches=max_searches)
        except Exception as exc:  # noqa: BLE001 - report per-company search failures
            failures.append({"code": code, "name": name, "error": str(exc)})
            continue

        for dimension, response in intel.items():
            if not getattr(response, "success", False):
                failures.append(
                    {
                        "code": code,
                        "name": name,
                        "error": f"{dimension}: {getattr(response, 'error_message', 'search failed')}",
                    }
                )
                continue

            for result in getattr(response, "results", [])[: max(1, results_per_dimension)]:
                evidence = _result_to_evidence(company, dimension, response, result)
                if evidence["dedupeKey"] in seen_keys:
                    continue
                seen_keys.add(evidence["dedupeKey"])
                items.append(evidence)

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    items.sort(key=lambda item: (item["date"], item["companyId"], item["type"]), reverse=True)
    if not items:
        failure_preview = "; ".join(
            f"{failure['code']} {failure['name']}: {failure['error']}" for failure in failures[:5]
        )
        detail = f" First failures: {failure_preview}" if failure_preview else ""
        raise RuntimeError(
            "Evidence refresh returned 0 items; keeping the previous evidence snapshot instead of overwriting it."
            + detail
        )

    write_json_atomic(EVIDENCE_FILE, items)
    return {
        "source": "daily_stock_analysis.SearchService",
        "updatedAt": _now_iso(),
        "companyCount": len(selected),
        "itemCount": len(items),
        "failureCount": len(failures),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh evidence feed for A股AI扩张瓶颈地图.")
    parser.add_argument("--max-companies", type=int, default=0, help="Company count to search. Default: 0 means all.")
    parser.add_argument("--max-searches", type=int, default=4, help="Search dimensions per company. Default: 4.")
    parser.add_argument("--results-per-dimension", type=int, default=2, help="Results kept per dimension. Default: 2.")
    parser.add_argument("--sleep-seconds", type=float, default=0.2, help="Delay between company searches.")
    args = parser.parse_args()

    payload = refresh_evidence_once(
        max_companies=args.max_companies,
        max_searches=args.max_searches,
        results_per_dimension=args.results_per_dimension,
        sleep_seconds=args.sleep_seconds,
    )
    print(
        f"Refreshed {payload['itemCount']} evidence items from {payload['companyCount']} companies "
        f"at {payload['updatedAt']} ({payload['failureCount']} failures)."
    )
    if payload["failureCount"]:
        for failure in payload["failures"]:
            print(f"- {failure['code']} {failure['name']}: {failure['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
