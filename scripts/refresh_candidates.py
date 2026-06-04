#!/usr/bin/env python3
"""Discover and promote A-share bottleneck candidates."""

from __future__ import annotations

import argparse
import hashlib
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.dsa_bridge import get_search_service, load_stock_index
from scripts.json_utils import PROJECT_ROOT, read_json, write_json_atomic


SECTORS_FILE = PROJECT_ROOT / "data" / "sectors.json"
COMPANIES_FILE = PROJECT_ROOT / "data" / "companies.json"
CANDIDATES_FILE = PROJECT_ROOT / "data" / "candidate_pool.json"
QUOTES_FILE = PROJECT_ROOT / "data" / "quotes.json"

DEFAULT_METRICS = {
    "bottleneckStrength": 62,
    "positionCertainty": 58,
    "evidenceQuality": 52,
    "financialConversion": 50,
    "valuationDiscipline": 55,
    "riskControl": 55,
}
OFFICIAL_DOMAINS = ("cninfo.com.cn", "sse.com.cn", "szse.cn")
ST_PREFIX = ("ST", "*ST", "退市")
SECTOR_CONCEPTS = {
    "optical": ["CPO概念", "光模块", "光通信", "硅光", "6G概念"],
    "package": ["先进封装", "Chiplet概念", "半导体", "集成电路", "存储芯片"],
    "pcb": ["PCB", "覆铜板", "玻璃基板", "消费电子", "5G"],
    "power": ["液冷服务器", "数据中心", "东数西算", "储能", "特高压"],
    "domestic": ["国产芯片", "AI芯片", "华为昇腾", "算力租赁", "服务器"],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _slug(code: str) -> str:
    return f"auto-{code}"


def _node_ids(nodes: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for node in nodes:
        node_id = node.get("nodeId")
        if node_id:
            ids.append(str(node_id))
        ids.extend(_node_ids(node.get("children") or []))
    return ids


def _sector_keywords(sector: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("flagship", "title", "subtitle"):
        if sector.get(key):
            values.append(str(sector[key]))
    values.extend(sector.get("blindspots") or [])
    values.extend(sector.get("bottlenecks") or [])
    values.extend(sector.get("discoveryKeywords") or [])
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        for part in re.split(r"[,，、/ ]+", value):
            part = part.strip()
            if len(part) >= 2 and part not in seen:
                seen.add(part)
                result.append(part)
    return result[:12]


def _load_a_stock_index() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    by_code: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []
    for item in load_stock_index():
        if item.get("market") != "CN" or item.get("assetType") != "stock" or item.get("active") is False:
            continue
        code = str(item.get("displayCode") or "").strip()
        name = str(item.get("nameZh") or "").strip()
        if not code or not name or name.startswith(ST_PREFIX):
            continue
        item = {**item, "code": code, "name": name}
        by_code[code] = item
        items.append(item)
    return by_code, items


def _extract_matches(text: str, stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    code_hits = set(re.findall(r"(?<!\d)([0368]\d{5})(?!\d)", text))
    for item in stocks:
        code = item["code"]
        name = item["name"]
        if code in seen:
            continue
        if code in code_hits or name in text:
            seen.add(code)
            matches.append(item)
    return matches


def _source_tier(source: str, url: str) -> str:
    text = f"{source} {url}".lower()
    return "official" if any(domain in text for domain in OFFICIAL_DOMAINS) else "search_web"


def _candidate_id(code: str, sector_id: str) -> str:
    digest = hashlib.sha1(f"{code}|{sector_id}".encode("utf-8")).hexdigest()[:8]
    return f"cand-{code}-{digest}"


def _score_candidate(candidate: dict[str, Any]) -> int:
    official = candidate["sourceTiers"].get("official", 0)
    concept = candidate["sourceTiers"].get("concept_board", 0)
    web = candidate["sourceTiers"].get("search_web", 0)
    keywords = len(candidate["matchedKeywords"])
    score = official * 45 + min(concept, 3) * 26 + min(web, 4) * 12 + min(keywords, 5) * 4
    return min(100, score)


def _search_query(service: Any, query: str, *, max_results: int = 5, days: int = 30) -> Any:
    for provider in getattr(service, "_providers", []):
        if not getattr(provider, "is_available", False):
            continue
        response = provider.search(query, max_results=max_results, days=days)
        if getattr(response, "success", False):
            return response
    raise RuntimeError("所有搜索引擎都不可用或搜索失败")


def _promote_candidate(candidate: dict[str, Any], sector: dict[str, Any]) -> dict[str, Any]:
    node_ids = _node_ids(sector.get("dependencies") or [])
    node_id = node_ids[-1] if node_ids else sector["id"]
    metrics = dict(DEFAULT_METRICS)
    metrics["bottleneckStrength"] = max(metrics["bottleneckStrength"], min(88, candidate["admissionScore"]))
    metrics["positionCertainty"] = max(metrics["positionCertainty"], min(82, candidate["admissionScore"] - 5))
    metrics["evidenceQuality"] = max(metrics["evidenceQuality"], min(84, candidate["admissionScore"] - 8))
    return {
        "id": _slug(candidate["code"]),
        "name": candidate["name"],
        "code": candidate["code"],
        "sectorIds": [sector["id"]],
        "role": f"{sector.get('flagship', sector['title'])}候选公司，需继续核验证据质量",
        "dependencyRefs": [
            {
                "sectorId": sector["id"],
                "nodeId": node_id,
                "role": sector.get("flagship", sector["title"]),
                "evidenceIds": [],
                "confidence": round(candidate["admissionScore"] / 100, 2),
            }
        ],
        "admission": {
            "source": "auto_candidate_rules",
            "score": candidate["admissionScore"],
            "promotedAt": _now_iso(),
            "curated": False,
        },
        "metrics": metrics,
    }


def _append_unavailable_quotes(promoted: list[dict[str, Any]]) -> None:
    if not promoted:
        return
    try:
        quotes = read_json(QUOTES_FILE)
    except Exception:  # noqa: BLE001
        quotes = {"source": "mixed", "updatedAt": _now_iso(), "itemCount": 0, "failureCount": 0, "failures": [], "items": []}
    existing = {str(item.get("code")) for item in quotes.get("items", [])}
    added = 0
    for company in promoted:
        if company["code"] in existing:
            continue
        quotes.setdefault("items", []).append(
            {
                "code": company["code"],
                "name": company["name"],
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
                "error": "quote_pending_refresh",
            }
        )
        added += 1
    if added:
        quotes["itemCount"] = len(quotes.get("items", []))
        quotes["updatedAt"] = _now_iso()
        write_json_atomic(QUOTES_FILE, quotes)


def _load_concept_boards() -> list[str]:
    try:
        import akshare as ak

        df = ak.stock_board_concept_name_em()
    except Exception:
        return []
    if df is None or df.empty:
        return []
    name_col = "板块名称" if "板块名称" in df.columns else df.columns[1]
    return [str(value) for value in df[name_col].dropna().tolist()]


def _match_concepts(available: list[str], desired: list[str]) -> list[str]:
    matched: list[str] = []
    for keyword in desired:
        exact = [name for name in available if name == keyword]
        fuzzy = [name for name in available if keyword in name or name in keyword]
        for name in exact + fuzzy:
            if name not in matched:
                matched.append(name)
    return matched[:5]


def _add_candidate(
    candidates_by_key: dict[str, dict[str, Any]],
    *,
    code: str,
    name: str,
    sector_id: str,
    keyword: str,
    tier: str,
    evidence: dict[str, str],
) -> None:
    key = f"{code}|{sector_id}"
    item = candidates_by_key.setdefault(
        key,
        {
            "id": _candidate_id(code, sector_id),
            "code": code,
            "name": name,
            "matchedSectors": [sector_id],
            "matchedKeywords": [],
            "sourceTiers": {},
            "evidenceCounts": {"total": 0},
            "status": "candidate",
            "admissionScore": 0,
            "sampleEvidence": [],
            "updatedAt": _now_iso(),
        },
    )
    if keyword not in item["matchedKeywords"]:
        item["matchedKeywords"].append(keyword)
    item["sourceTiers"][tier] = item["sourceTiers"].get(tier, 0) + 1
    item["evidenceCounts"]["total"] += 1
    if len(item["sampleEvidence"]) < 5:
        item["sampleEvidence"].append(evidence)


def _discover_from_concept_boards(
    candidates_by_key: dict[str, dict[str, Any]],
    sectors: list[dict[str, Any]],
    by_code: dict[str, dict[str, Any]],
    *,
    max_per_concept: int,
    failures: list[dict[str, str]],
) -> None:
    try:
        import akshare as ak
    except Exception as exc:  # noqa: BLE001
        failures.append({"sectorId": "all", "query": "akshare", "error": str(exc)})
        return

    available = _load_concept_boards()
    for sector in sectors:
        concepts = _match_concepts(available, SECTOR_CONCEPTS.get(sector["id"], []))
        for concept in concepts:
            try:
                df = ak.stock_board_concept_cons_em(symbol=concept)
            except Exception as exc:  # noqa: BLE001
                failures.append({"sectorId": sector["id"], "query": concept, "error": str(exc)})
                continue
            if df is None or df.empty:
                continue
            code_col = "代码" if "代码" in df.columns else df.columns[1]
            name_col = "名称" if "名称" in df.columns else df.columns[2]
            for _, row in df.head(max_per_concept).iterrows():
                code = str(row.get(code_col, "")).zfill(6)
                name = str(row.get(name_col, "")).strip()
                if code not in by_code or not name or name.startswith(ST_PREFIX):
                    continue
                _add_candidate(
                    candidates_by_key,
                    code=code,
                    name=name,
                    sector_id=sector["id"],
                    keyword=concept,
                    tier="concept_board",
                    evidence={"title": f"东方财富概念板块成分股：{concept}", "url": "", "source": "akshare.stock_board_concept_cons_em"},
                )


def refresh_candidates_once(
    *,
    max_candidates: int = 300,
    max_promoted_per_sector: int = 30,
    max_queries_per_sector: int = 4,
    sleep_seconds: float = 0.2,
) -> dict[str, Any]:
    sectors = read_json(SECTORS_FILE)
    companies = read_json(COMPANIES_FILE)
    existing_codes = {str(company["code"]) for company in companies}
    by_code, stocks = _load_a_stock_index()
    service = get_search_service()
    if not getattr(service, "is_available", False):
        raise RuntimeError("daily_stock_analysis 搜索服务不可用，无法刷新候选池。")

    candidates_by_key: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []

    _discover_from_concept_boards(
        candidates_by_key,
        sectors,
        by_code,
        max_per_concept=max(10, max_promoted_per_sector),
        failures=failures,
    )

    for sector in sectors:
        keywords = _sector_keywords(sector)[:max_queries_per_sector]
        for keyword in keywords:
            query = f"{sector['title']} {keyword} A股 公司 公告 供应商"
            try:
                response = _search_query(service, query, max_results=5, days=30)
            except Exception as exc:  # noqa: BLE001
                failures.append({"sectorId": sector["id"], "query": query, "error": str(exc)})
                continue
            if not getattr(response, "success", False):
                failures.append(
                    {
                        "sectorId": sector["id"],
                        "query": query,
                        "error": getattr(response, "error_message", "search failed"),
                    }
                )
                continue

            for result in getattr(response, "results", []):
                text = f"{getattr(result, 'title', '')} {getattr(result, 'snippet', '')} {getattr(result, 'url', '')}"
                for match in _extract_matches(text, stocks):
                    code = match["code"]
                    if code not in by_code:
                        continue
                    tier = _source_tier(getattr(result, "source", ""), getattr(result, "url", ""))
                    _add_candidate(
                        candidates_by_key,
                        code=code,
                        name=match["name"],
                        sector_id=sector["id"],
                        keyword=keyword,
                        tier=tier,
                        evidence={
                            "title": getattr(result, "title", "")[:120],
                            "url": getattr(result, "url", ""),
                            "source": getattr(result, "source", ""),
                        },
                    )
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    candidates = list(candidates_by_key.values())
    for candidate in candidates:
        candidate["admissionScore"] = _score_candidate(candidate)
        if candidate["code"] in existing_codes:
            candidate["status"] = "promoted"
        elif candidate["admissionScore"] >= 60:
            candidate["status"] = "needs_review"

    candidates.sort(key=lambda item: (item["admissionScore"], item["evidenceCounts"]["total"]), reverse=True)
    candidates = candidates[:max_candidates]

    promoted_counts: dict[str, int] = {}
    promoted: list[dict[str, Any]] = []
    sector_by_id = {sector["id"]: sector for sector in sectors}
    for candidate in candidates:
        if candidate["code"] in existing_codes or candidate["admissionScore"] < 60:
            continue
        sector_id = candidate["matchedSectors"][0]
        if promoted_counts.get(sector_id, 0) >= max_promoted_per_sector:
            continue
        promoted_counts[sector_id] = promoted_counts.get(sector_id, 0) + 1
        candidate["status"] = "promoted"
        promoted.append(_promote_candidate(candidate, sector_by_id[sector_id]))
        existing_codes.add(candidate["code"])

    if promoted:
        companies = companies + promoted
        write_json_atomic(COMPANIES_FILE, companies)
        _append_unavailable_quotes(promoted)

    payload = {
        "source": "daily_stock_analysis.SearchService + stocks.index.json",
        "updatedAt": _now_iso(),
        "itemCount": len(candidates),
        "promotedCount": len(promoted),
        "failureCount": len(failures),
        "failures": failures,
        "items": candidates,
    }
    if not candidates:
        failure_preview = "; ".join(
            f"{failure.get('sectorId', 'unknown')}: {failure.get('error', '')}" for failure in failures[:5]
        )
        detail = f" First failures: {failure_preview}" if failure_preview else ""
        raise RuntimeError(
            "Candidate refresh returned 0 items; keeping the previous candidate snapshot instead of overwriting it."
            + detail
        )

    write_json_atomic(CANDIDATES_FILE, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh A股AI扩张瓶颈地图候选池.")
    parser.add_argument("--max-candidates", type=int, default=300)
    parser.add_argument("--max-promoted-per-sector", type=int, default=30)
    parser.add_argument("--max-queries-per-sector", type=int, default=4)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    args = parser.parse_args()
    payload = refresh_candidates_once(
        max_candidates=args.max_candidates,
        max_promoted_per_sector=args.max_promoted_per_sector,
        max_queries_per_sector=args.max_queries_per_sector,
        sleep_seconds=args.sleep_seconds,
    )
    print(
        f"Refreshed {payload['itemCount']} candidates, promoted {payload['promotedCount']} "
        f"({payload['failureCount']} failures)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
