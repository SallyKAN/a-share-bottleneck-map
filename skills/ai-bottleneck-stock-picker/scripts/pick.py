#!/usr/bin/env python3
"""AI bottleneck stock picker over the a-share-bottleneck-map snapshot.

The script is intentionally deterministic: it reads committed JSON snapshots,
scores companies/candidates, and emits JSON for agents to explain.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO_ROOT = SKILL_ROOT.parents[1]

POSITIVE_TYPES = {"最新消息", "公司公告", "机构分析", "业绩预期", "行业分析"}
RISK_TERMS = ("减持", "处罚", "违规", "诉讼", "立案", "问询", "亏损", "下滑", "风险", "终止")
BOTTLENECK_KEYWORDS = {
    "optical": ("光模块", "光芯片", "高速互联", "1.6T", "800G", "CPO", "硅光"),
    "package": ("先进封装", "Chiplet", "HBM", "测试", "封测", "载板"),
    "pcb": ("PCB", "高速材料", "CCL", "铜箔", "高多层", "Msub"),
    "power": ("电力", "液冷", "数据中心", "变压器", "UPS", "温控"),
    "memory": ("存储", "HBM", "DDR", "NAND", "边缘", "国产替代"),
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def finite(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return default


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class Snapshot:
    def __init__(self, repo_root: Path, *, live: bool = False):
        self.repo_root = repo_root
        self.live_enabled = live
        data_dir = repo_root / "data"
        self.sectors = read_json(data_dir / "sectors.json")
        self.companies = read_json(data_dir / "companies.json")
        self.candidate_pool = read_json(data_dir / "candidate_pool.json")
        self.evidence = read_json(data_dir / "evidence.json")
        self.quotes = read_json(data_dir / "quotes.json")
        self.ranking = read_json(data_dir / "ranking.json")
        self.scoring = read_json(data_dir / "scoring.json")

        self.sectors_by_id = {item["id"]: item for item in self.sectors}
        self.companies_by_id = {item["id"]: item for item in self.companies}
        self.companies_by_code = {str(item["code"]): item for item in self.companies}
        self.quotes_by_code = {str(item["code"]): item for item in self.quotes.get("items", [])}
        self.ranking_by_company = {item["companyId"]: item for item in self.ranking.get("rows", [])}
        self.evidence_by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in self.evidence:
            self.evidence_by_company[str(item.get("companyId"))].append(item)
        for items in self.evidence_by_company.values():
            items.sort(key=lambda item: (str(item.get("date", "")), str(item.get("fetchedAt", ""))), reverse=True)
        self.live = self._load_live_cache() if live else {}
        self.live_news_by_code = self._index_live("live_news", "symbol")
        self.financials_by_code = self._index_live("financials", "symbol")
        self.technicals_by_code = self._index_live("technicals", "symbol")
        self.etf_holdings = self.live.get("etf_holdings", {}).get("items", [])

    def _load_live_cache(self) -> dict[str, dict[str, Any]]:
        live_dir = self.repo_root / ".cache" / "ai-bottleneck-stock-picker"
        payload: dict[str, dict[str, Any]] = {}
        for name in ("live_news", "financials", "etf_holdings", "technicals"):
            path = live_dir / f"{name}.json"
            if path.exists():
                try:
                    payload[name] = read_json(path)
                except Exception:  # noqa: BLE001
                    payload[name] = {"items": [], "warnings": [f"{name} cache unreadable"]}
            else:
                payload[name] = {"items": [], "warnings": [f"{name} cache missing"]}
        return payload

    def _index_live(self, cache_name: str, key: str) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in self.live.get(cache_name, {}).get("items", []):
            out[str(item.get(key, ""))].append(item)
        return out

    def health(self) -> dict[str, Any]:
        fetched = [str(item.get("fetchedAt", "")) for item in self.evidence if item.get("fetchedAt")]
        evidence_dates = [str(item.get("date", "")) for item in self.evidence if item.get("date")]
        return {
            "repoRoot": str(self.repo_root),
            "generatedAt": now_iso(),
            "counts": {
                "sectors": len(self.sectors),
                "companies": len(self.companies),
                "candidates": len(self.candidate_pool.get("items", [])),
                "evidence": len(self.evidence),
                "quotes": len(self.quotes.get("items", [])),
                "rankingRows": len(self.ranking.get("rows", [])),
            },
            "updatedAt": {
                "candidatePool": self.candidate_pool.get("updatedAt"),
                "quotes": self.quotes.get("updatedAt"),
                "ranking": self.ranking.get("asOf"),
                "evidenceMaxFetchedAt": max(fetched) if fetched else None,
                "evidenceMaxDate": max(evidence_dates) if evidence_dates else None,
            },
            "warnings": self.snapshot_warnings(),
            "live": self.live_health(),
        }

    def live_health(self) -> dict[str, Any]:
        if not self.live_enabled:
            return {"enabled": False}
        caches = {
            name: {
                "updatedAt": payload.get("updatedAt"),
                "itemCount": len(payload.get("items", [])),
                "warnings": payload.get("warnings", []),
            }
            for name, payload in self.live.items()
        }
        return {"enabled": True, "caches": caches}

    def snapshot_warnings(self) -> list[str]:
        warnings: list[str] = []
        if not self.evidence:
            warnings.append("evidence snapshot is empty; do not infer absence of catalysts")
        if not self.candidate_pool.get("items"):
            warnings.append("candidate pool is empty; check refresh health before using candidates")
        stale_quotes = [item for item in self.quotes.get("items", []) if item.get("status") != "ok"]
        if stale_quotes:
            warnings.append(f"{len(stale_quotes)} quotes are stale or unavailable")
        return warnings


def metric(company: dict[str, Any], *names: str) -> float:
    metrics = company.get("metrics", {})
    for name in names:
        if name in metrics:
            return finite(metrics.get(name))
    return 50.0


def sector_bottleneck_score(snapshot: Snapshot, sector_ids: list[str]) -> float:
    scores = []
    for sector_id in sector_ids:
        sector = snapshot.sectors_by_id.get(sector_id, {})
        density = len(sector.get("bottlenecks", [])) + len(sector.get("dependencies", []))
        scores.append(clamp(55 + density * 5))
    return max(scores) if scores else 50.0


def evidence_stats(items: list[dict[str, Any]]) -> dict[str, Any]:
    sentiment = Counter(item.get("sentiment") for item in items)
    risk_count = 0
    positive_count = 0
    for item in items:
        text = " ".join(str(item.get(key, "")) for key in ("title", "summary", "type"))
        if item.get("sentiment") == "positive" or item.get("type") in POSITIVE_TYPES:
            positive_count += 1
        if item.get("sentiment") == "negative" or any(term in text for term in RISK_TERMS):
            risk_count += 1
    return {
        "count": len(items),
        "positiveCount": positive_count,
        "riskCount": risk_count,
        "sentiment": dict(sentiment),
        "latest": items[:5],
    }


def live_news_stats(items: list[dict[str, Any]]) -> dict[str, Any]:
    signal_counts = Counter(item.get("signalType") for item in items)
    sentiment_counts = Counter(item.get("sentiment") for item in items)
    risk_count = 0
    positive_count = 0
    for item in items:
        title = str(item.get("title", ""))
        summary = str(item.get("summary", ""))
        if item.get("sentiment") == "positive":
            positive_count += 1
        if item.get("sentiment") == "negative" or item.get("signalType") == "risk" or any(term in f"{title} {summary}" for term in RISK_TERMS):
            risk_count += 1
    return {
        "count": len(items),
        "positiveCount": positive_count,
        "riskCount": risk_count,
        "signalTypes": dict(signal_counts),
        "sentiment": dict(sentiment_counts),
        "latest": items[:5],
    }


def quote_signals(quote: dict[str, Any] | None) -> dict[str, Any]:
    if not quote:
        return {"status": "missing", "liquidityScore": 0, "underpricingScore": 40, "riskPenalty": 15}
    amount = finite(quote.get("amount"))
    change_60d = finite(quote.get("change60d"))
    turnover = finite(quote.get("turnoverRate"))
    pe = finite(quote.get("peRatio"))
    liquidity = clamp(35 + min(amount / 100_000_000, 20) * 3 + min(turnover, 10) * 2)
    underpricing = clamp(72 - max(change_60d, 0) * 0.45)
    risk_penalty = 0.0
    if quote.get("status") != "ok":
        risk_penalty += 12
    if change_60d > 80:
        risk_penalty += 18
    elif change_60d > 45:
        risk_penalty += 10
    if pe > 120:
        risk_penalty += 12
    elif pe > 80:
        risk_penalty += 7
    return {
        "status": quote.get("status", "unknown"),
        "price": quote.get("price"),
        "changePercent": quote.get("changePercent"),
        "change60d": quote.get("change60d"),
        "amount": quote.get("amount"),
        "turnoverRate": quote.get("turnoverRate"),
        "peRatio": quote.get("peRatio"),
        "pbRatio": quote.get("pbRatio"),
        "liquidityScore": round(liquidity, 2),
        "underpricingScore": round(underpricing, 2),
        "riskPenalty": round(risk_penalty, 2),
    }


def financial_signals(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {"status": "missing", "financialConfirmation": 50.0, "riskPenalty": 0.0}
    item = items[0]
    confirmation = finite(item.get("financialConfirmation"), 50.0)
    penalty = 0.0
    revenue_yoy = item.get("revenueYoY")
    profit_yoy = item.get("netProfitYoY")
    cash_flow = item.get("operatingCashFlow")
    if isinstance(revenue_yoy, (int, float)) and revenue_yoy < -10:
        penalty += 8
    if isinstance(profit_yoy, (int, float)) and profit_yoy < -10:
        penalty += 10
    if isinstance(cash_flow, (int, float)) and cash_flow < 0:
        penalty += 6
    return {
        "status": "ok",
        "period": item.get("period"),
        "revenueYoY": item.get("revenueYoY"),
        "netProfitYoY": item.get("netProfitYoY"),
        "grossMargin": item.get("grossMargin"),
        "operatingCashFlow": item.get("operatingCashFlow"),
        "inventory": item.get("inventory"),
        "contractLiabilities": item.get("contractLiabilities"),
        "capex": item.get("capex"),
        "rdExpense": item.get("rdExpense"),
        "peRatio": item.get("peRatio"),
        "pbRatio": item.get("pbRatio"),
        "marketCap": item.get("marketCap"),
        "financialConfirmation": round(confirmation, 2),
        "riskPenalty": round(penalty, 2),
        "sourceStatus": item.get("sourceStatus"),
        "errors": item.get("errors", []),
    }


def technical_signals(items: list[dict[str, Any]], quote_info: dict[str, Any]) -> dict[str, Any]:
    if items:
        item = items[0]
        trend = str(item.get("trendState") or "unknown")
        crowdedness = finite(item.get("crowdedness"))
        change_60d = item.get("change60d")
        turnover = item.get("turnoverRate")
        amount = item.get("amount")
        volume_ratio = item.get("volumeRatio")
    else:
        trend = "unknown"
        crowdedness = finite(quote_info.get("riskPenalty")) * 4
        change_60d = quote_info.get("change60d")
        turnover = quote_info.get("turnoverRate")
        amount = quote_info.get("amount")
        volume_ratio = None

    timing = 55.0
    if trend == "early":
        timing += 14
    elif trend == "momentum":
        timing += 8
    elif trend == "crowded":
        timing -= 16
    elif trend == "broken":
        timing -= 20
    timing -= min(crowdedness, 100) * 0.22
    if isinstance(change_60d, (int, float)) and change_60d < -20:
        timing -= 8
    return {
        "status": "ok" if items else "derived_from_quote",
        "trendState": trend,
        "change20d": items[0].get("change20d") if items else None,
        "change60d": change_60d,
        "turnoverRate": turnover,
        "amount": amount,
        "volumeRatio": volume_ratio,
        "newHigh": items[0].get("newHigh") if items else None,
        "drawdown": items[0].get("drawdown") if items else None,
        "relativeStrength": items[0].get("relativeStrength") if items else None,
        "volatility": items[0].get("volatility") if items else None,
        "crowdedness": round(crowdedness, 2),
        "tradingTimingScore": round(clamp(timing), 2),
    }


def live_score_block(
    base_score: float,
    news: dict[str, Any],
    financials: dict[str, Any],
    technicals: dict[str, Any],
) -> dict[str, Any]:
    news_boost = news["positiveCount"] * 3 + news["count"] * 1.5 - news["riskCount"] * 8
    financial_confirmation = finite(financials.get("financialConfirmation"), 50.0)
    financial_penalty = finite(financials.get("riskPenalty"))
    fundamental = clamp(base_score * 0.72 + financial_confirmation * 0.20 + clamp(50 + news_boost) * 0.08 - financial_penalty)
    timing = finite(technicals.get("tradingTimingScore"), 50.0)
    composite = clamp(fundamental * 0.72 + timing * 0.28)

    if fundamental >= 72 and timing >= 58:
        label = "High Conviction / Good Timing"
    elif fundamental >= 72:
        label = "High Conviction / Bad Timing"
    elif fundamental >= 60 and timing >= 58:
        label = "Developing Thesis / Good Timing"
    elif fundamental >= 60:
        label = "Developing Thesis / Wait"
    else:
        label = "Weak Or Unconfirmed"
    return {
        "fundamentalBottleneckScore": round(fundamental, 2),
        "tradingTimingScore": round(timing, 2),
        "compositeScore": round(composite, 2),
        "finalLabel": label,
    }


def score_company(snapshot: Snapshot, company: dict[str, Any]) -> dict[str, Any]:
    company_id = str(company["id"])
    sector_ids = list(company.get("sectorIds", []))
    ranking = snapshot.ranking_by_company.get(company_id, {})
    quote = snapshot.quotes_by_code.get(str(company["code"]))
    quote_info = quote_signals(quote)
    evidence = snapshot.evidence_by_company.get(company_id, [])
    ev = evidence_stats(evidence)

    bottleneck_leverage = max(metric(company, "bottleneck", "bottleneckStrength"), sector_bottleneck_score(snapshot, sector_ids))
    supply_constraint = metric(company, "supplyConstraint", "scarcity", "certainty")
    purity = metric(company, "purity", "positioning", "certainty")
    evidence_momentum = clamp(45 + ev["positiveCount"] * 8 + ev["count"] * 3 - ev["riskCount"] * 12 + finite(ranking.get("evidenceScore")) * 8)
    underpricing = finite(quote_info["underpricingScore"])
    liquidity = finite(quote_info["liquidityScore"])
    risk_penalty = finite(quote_info["riskPenalty"]) + ev["riskCount"] * 8
    valuation_penalty = 0.0
    if quote:
        pe = finite(quote.get("peRatio"))
        pb = finite(quote.get("pbRatio"))
        if pe > 100:
            valuation_penalty += 12
        if pb > 12:
            valuation_penalty += 8

    raw = (
        bottleneck_leverage * 0.25
        + supply_constraint * 0.20
        + purity * 0.15
        + evidence_momentum * 0.15
        + underpricing * 0.10
        + liquidity * 0.05
        + finite(ranking.get("score")) * 0.10
        - risk_penalty
        - valuation_penalty
    )
    score = clamp(raw)
    flags = []
    if ev["count"] == 0:
        flags.append("no_current_evidence")
    if quote_info["status"] != "ok":
        flags.append("quote_not_ok")
    if valuation_penalty:
        flags.append("valuation_risk")
    if risk_penalty >= 16:
        flags.append("risk_evidence_or_crowding")
    if len(sector_ids) > 1:
        flags.append("multi_bottleneck_exposure")

    if score >= 72 and ev["count"] > 0 and quote_info["status"] == "ok":
        bucket = "core_pick"
    elif score >= 58:
        bucket = "watchlist"
    else:
        bucket = "speculative_or_wait"

    result = {
        "companyId": company_id,
        "name": company.get("name"),
        "code": str(company.get("code")),
        "bucket": bucket,
        "stockPickerScore": round(score, 2),
        "components": {
            "bottleneckLeverage": round(bottleneck_leverage, 2),
            "supplyConstraint": round(supply_constraint, 2),
            "aSharePurity": round(purity, 2),
            "evidenceMomentum": round(evidence_momentum, 2),
            "marketUnderpricing": round(underpricing, 2),
            "liquidity": round(liquidity, 2),
            "riskPenalty": round(risk_penalty, 2),
            "valuationPenalty": round(valuation_penalty, 2),
        },
        "sectors": [
            {"id": sid, "title": snapshot.sectors_by_id.get(sid, {}).get("title", sid)}
            for sid in sector_ids
        ],
        "role": company.get("role"),
        "ranking": {
            "score": ranking.get("score"),
            "sectorCount": ranking.get("sectorCount"),
            "appearances": ranking.get("appearances"),
            "evidenceScore": ranking.get("evidenceScore"),
            "evidenceCount": ranking.get("evidenceCount"),
        },
        "quote": quote_info,
        "evidence": ev,
        "riskFlags": flags,
        "nextVerification": verification_questions(snapshot, company, flags),
    }
    if snapshot.live_enabled:
        code = str(company.get("code"))
        live_news = live_news_stats(snapshot.live_news_by_code.get(code, []))
        live_financials = financial_signals(snapshot.financials_by_code.get(code, []))
        live_technicals = technical_signals(snapshot.technicals_by_code.get(code, []), quote_info)
        result["live"] = {
            "news": live_news,
            "financials": live_financials,
            "technicals": live_technicals,
        }
        result["liveScores"] = live_score_block(score, live_news, live_financials, live_technicals)
        if live_news["riskCount"]:
            result["riskFlags"].append("live_risk_news")
        if live_financials.get("status") == "missing":
            result["riskFlags"].append("live_financials_missing")
    return result


def verification_questions(snapshot: Snapshot, company: dict[str, Any], flags: list[str]) -> list[str]:
    questions = [
        "Verify whether recent orders, capacity expansion, customer certification, or pricing power directly tie to the bottleneck.",
        "Check the latest quarterly report for revenue growth, margin change, inventory, cash flow, and contract liabilities.",
    ]
    if "valuation_risk" in flags:
        questions.append("Test whether valuation has already priced in the AI bottleneck thesis.")
    if "no_current_evidence" in flags:
        questions.append("Refresh or externally verify evidence before treating this as an active catalyst.")
    if "multi_bottleneck_exposure" in flags:
        questions.append("Separate which bottleneck contributes most to revenue/profit exposure.")
    sector_ids = company.get("sectorIds", [])
    for sector_id in sector_ids[:2]:
        checks = snapshot.sectors_by_id.get(sector_id, {}).get("checks", [])
        questions.extend(str(item) for item in checks[:1])
    return questions[:5]


def score_candidate(snapshot: Snapshot, candidate: dict[str, Any]) -> dict[str, Any]:
    source_tiers = candidate.get("sourceTiers", {})
    evidence_counts = candidate.get("evidenceCounts", {})
    admission = finite(candidate.get("admissionScore"))
    tier_bonus = 0
    for tier, count in source_tiers.items():
        if tier in {"official", "financial"}:
            tier_bonus += int(count) * 8
        elif tier in {"research", "reputable_media"}:
            tier_bonus += int(count) * 5
        else:
            tier_bonus += int(count) * 2
    score = clamp(admission * 0.7 + tier_bonus + finite(evidence_counts.get("total")) * 2)
    return {
        "id": candidate.get("id"),
        "name": candidate.get("name"),
        "code": str(candidate.get("code")),
        "bucket": "speculative_candidate" if score >= 55 else "low_confidence_candidate",
        "candidateScore": round(score, 2),
        "admissionScore": candidate.get("admissionScore"),
        "status": candidate.get("status"),
        "matchedSectors": [
            {"id": sid, "title": snapshot.sectors_by_id.get(sid, {}).get("title", sid)}
            for sid in candidate.get("matchedSectors", [])
        ],
        "matchedKeywords": candidate.get("matchedKeywords", []),
        "sourceTiers": source_tiers,
        "evidenceCounts": evidence_counts,
        "sampleEvidence": candidate.get("sampleEvidence", [])[:3],
        "nextVerification": [
            "Confirm whether the company has direct revenue exposure to the matched bottleneck.",
            "Find official filings or financial data before promoting this from candidate to watchlist.",
            "Check whether the match is only search-keyword noise.",
        ],
    }


def top(snapshot: Snapshot, limit: int, sector: str | None = None) -> dict[str, Any]:
    scored = [score_company(snapshot, company) for company in snapshot.companies]
    if sector:
        scored = [item for item in scored if any(s["id"] == sector for s in item["sectors"])]
    scored.sort(key=lambda item: item["stockPickerScore"], reverse=True)
    return {"health": snapshot.health(), "items": scored[:limit]}


def candidates(snapshot: Snapshot, limit: int, sector: str | None = None) -> dict[str, Any]:
    items = [score_candidate(snapshot, item) for item in snapshot.candidate_pool.get("items", [])]
    if sector:
        items = [item for item in items if any(s["id"] == sector for s in item["matchedSectors"])]
    items.sort(key=lambda item: item["candidateScore"], reverse=True)
    return {"health": snapshot.health(), "items": items[:limit]}


def company(snapshot: Snapshot, query: str) -> dict[str, Any]:
    item = snapshot.companies_by_code.get(query)
    if not item:
        item = next((c for c in snapshot.companies if query in {str(c.get("id")), str(c.get("name"))}), None)
    if item:
        return {"health": snapshot.health(), "company": score_company(snapshot, item)}
    candidate = next(
        (
            c
            for c in snapshot.candidate_pool.get("items", [])
            if query in {str(c.get("code")), str(c.get("id")), str(c.get("name"))}
        ),
        None,
    )
    if candidate:
        return {"health": snapshot.health(), "candidate": score_candidate(snapshot, candidate)}
    return {"health": snapshot.health(), "error": "not_found", "query": query}


def evidence(snapshot: Snapshot, query: str, limit: int) -> dict[str, Any]:
    item = snapshot.companies_by_code.get(query)
    if not item:
        item = next((c for c in snapshot.companies if query in {str(c.get("id")), str(c.get("name"))}), None)
    if not item:
        return {"health": snapshot.health(), "error": "company_not_found", "query": query}
    items = snapshot.evidence_by_company.get(str(item["id"]), [])[:limit]
    return {"health": snapshot.health(), "company": {"name": item["name"], "code": str(item["code"])}, "items": items}


def search(snapshot: Snapshot, text: str, limit: int) -> dict[str, Any]:
    text_lower = text.lower()
    matches = []
    for company_item in snapshot.companies:
        haystack = " ".join(
            [
                str(company_item.get("name", "")),
                str(company_item.get("code", "")),
                str(company_item.get("role", "")),
                " ".join(company_item.get("sectorIds", [])),
            ]
        ).lower()
        if text_lower in haystack:
            matches.append(score_company(snapshot, company_item))
    matches.sort(key=lambda item: item["stockPickerScore"], reverse=True)
    return {"health": snapshot.health(), "items": matches[:limit]}


def etf(snapshot: Snapshot, query: str | None, limit: int) -> dict[str, Any]:
    if not snapshot.live_enabled:
        return {
            "health": snapshot.health(),
            "error": "live_required",
            "message": "Run with --live after refreshing etf_holdings cache.",
        }
    query_text = (query or "").lower()
    items = []
    for raw in snapshot.etf_holdings:
        haystack = " ".join(
            [
                str(raw.get("etfCode", "")),
                str(raw.get("etfName", "")),
                str(raw.get("theme", "")),
                " ".join(str(key) for key in raw.get("bottleneckExposure", {}).keys()),
            ]
        ).lower()
        if query_text and query_text not in haystack:
            continue
        exposure = raw.get("bottleneckExposure", {})
        matched = []
        for symbol in raw.get("matchedCompanies", []):
            company_item = snapshot.companies_by_code.get(str(symbol))
            if company_item:
                matched.append(
                    {
                        "symbol": str(symbol),
                        "name": company_item.get("name"),
                        "score": score_company(snapshot, company_item)["stockPickerScore"],
                        "sectors": company_item.get("sectorIds", []),
                    }
                )
        matched.sort(key=lambda item: finite(item.get("score")), reverse=True)
        items.append(
            {
                "etfCode": raw.get("etfCode"),
                "etfName": raw.get("etfName"),
                "theme": raw.get("theme"),
                "purityScore": raw.get("purityScore"),
                "top10Weight": raw.get("top10Weight"),
                "bottleneckExposure": exposure,
                "matchedCompanies": matched[:10],
                "topHoldings": raw.get("holdings", [])[:10],
                "source": raw.get("source"),
                "researchUse": "ETF can reduce single-stock risk but may dilute bottleneck purity; inspect holdings before using it as a substitute.",
            }
        )
    items.sort(key=lambda item: finite(item.get("purityScore")), reverse=True)
    payload: dict[str, Any] = {"health": snapshot.health(), "items": items[:limit]}
    if not items:
        payload["warning"] = "No ETF holdings matched. Refresh with fetch_etf_holdings.py --etfs <codes> and rerun with --live."
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI bottleneck stock picker snapshot query.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT), help="a-share-bottleneck-map repository root")
    parser.add_argument("--live", action="store_true", help="Use live news, financials, ETF holdings, and technicals caches")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_live_option(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument(
            "--live",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Use live news, financials, ETF holdings, and technicals caches",
        )

    health_parser = sub.add_parser("health")
    add_live_option(health_parser)

    top_parser = sub.add_parser("top")
    top_parser.add_argument("--limit", type=int, default=10)
    add_live_option(top_parser)

    sector_parser = sub.add_parser("sector")
    sector_parser.add_argument("sector")
    sector_parser.add_argument("--limit", type=int, default=10)
    add_live_option(sector_parser)

    company_parser = sub.add_parser("company")
    company_parser.add_argument("query")
    add_live_option(company_parser)

    candidates_parser = sub.add_parser("candidates")
    candidates_parser.add_argument("--sector")
    candidates_parser.add_argument("--limit", type=int, default=20)
    add_live_option(candidates_parser)

    evidence_parser = sub.add_parser("evidence")
    evidence_parser.add_argument("--company", required=True)
    evidence_parser.add_argument("--limit", type=int, default=10)
    add_live_option(evidence_parser)

    search_parser = sub.add_parser("search")
    search_parser.add_argument("text")
    search_parser.add_argument("--limit", type=int, default=10)
    add_live_option(search_parser)

    etf_parser = sub.add_parser("etf")
    etf_parser.add_argument("query", nargs="?", default="")
    etf_parser.add_argument("--limit", type=int, default=10)
    add_live_option(etf_parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = Snapshot(Path(args.repo_root).resolve(), live=args.live)
    if args.command == "health":
        payload = snapshot.health()
    elif args.command == "top":
        payload = top(snapshot, args.limit)
    elif args.command == "sector":
        payload = top(snapshot, args.limit, sector=args.sector)
    elif args.command == "company":
        payload = company(snapshot, args.query)
    elif args.command == "candidates":
        payload = candidates(snapshot, args.limit, sector=args.sector)
    elif args.command == "evidence":
        payload = evidence(snapshot, args.company, args.limit)
    elif args.command == "search":
        payload = search(snapshot, args.text, args.limit)
    elif args.command == "etf":
        payload = etf(snapshot, args.query, args.limit)
    else:
        raise AssertionError(args.command)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
