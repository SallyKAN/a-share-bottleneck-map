#!/usr/bin/env python3
"""Build cross-sector hidden-winner ranking."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.json_utils import PROJECT_ROOT, read_json, write_json_atomic


SECTORS_FILE = PROJECT_ROOT / "data" / "sectors.json"
COMPANIES_FILE = PROJECT_ROOT / "data" / "companies.json"
EVIDENCE_FILE = PROJECT_ROOT / "data" / "evidence.json"
QUOTES_FILE = PROJECT_ROOT / "data" / "quotes.json"
SCORING_FILE = PROJECT_ROOT / "data" / "scoring.json"
RANKING_FILE = PROJECT_ROOT / "data" / "ranking.json"

SOURCE_TIER_WEIGHTS = {
    "official": 5,
    "financial": 4,
    "research": 3,
    "reputable_media": 2,
    "search_web": 1,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _score(company: dict[str, Any], weights: dict[str, float]) -> int:
    raw = 0.0
    for key, weight in weights.items():
        raw += float(company.get("metrics", {}).get(key, 0)) * float(weight)
    sector_bonus = max(0, len(set(company.get("sectorIds") or [])) - 1) * 4
    appearance_bonus = max(0, len(company.get("dependencyRefs") or []) - len(set(company.get("sectorIds") or []))) * 2
    return round(raw + sector_bonus + appearance_bonus)


def _quote_status(quote: dict[str, Any] | None) -> str:
    if not quote:
        return "unavailable"
    if quote.get("status"):
        return str(quote["status"])
    if quote.get("stale"):
        return "stale"
    if quote.get("price") is None:
        return "unavailable"
    return "ok"


def refresh_ranking_once() -> dict[str, Any]:
    sectors = read_json(SECTORS_FILE)
    companies = read_json(COMPANIES_FILE)
    evidence = read_json(EVIDENCE_FILE)
    quotes = read_json(QUOTES_FILE)
    scoring = read_json(SCORING_FILE)

    sector_by_id = {sector["id"]: sector for sector in sectors}
    quote_by_code = {str(item["code"]): item for item in quotes.get("items", [])}
    evidence_by_company: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        evidence_by_company.setdefault(str(item.get("companyId")), []).append(item)

    rows: list[dict[str, Any]] = []
    for company in companies:
        sector_ids = list(dict.fromkeys(company.get("sectorIds") or []))
        dependency_refs = company.get("dependencyRefs") or [
            {"sectorId": sector_id, "nodeId": sector_id, "role": sector_by_id.get(sector_id, {}).get("flagship", sector_id)}
            for sector_id in sector_ids
        ]
        company_evidence = evidence_by_company.get(company["id"], [])
        evidence_score = sum(
            SOURCE_TIER_WEIGHTS.get(str(item.get("sourceTier", "search_web")), 1) * float(item.get("confidence", 0.5))
            for item in company_evidence
        )
        quote = quote_by_code.get(str(company["code"]))
        rows.append(
            {
                "companyId": company["id"],
                "name": company["name"],
                "code": company["code"],
                "sectors": sector_ids,
                "sectorNames": [sector_by_id.get(sector_id, {}).get("title", sector_id) for sector_id in sector_ids],
                "sectorCount": len(sector_ids),
                "appearances": len(dependency_refs),
                "dependencyRefs": dependency_refs,
                "score": _score(company, scoring.get("weights", {})),
                "evidenceScore": round(evidence_score, 2),
                "evidenceCount": len(company_evidence),
                "quote": quote,
                "quoteStatus": _quote_status(quote),
            }
        )

    rows.sort(
        key=lambda row: (
            row["sectorCount"],
            row["appearances"],
            row["evidenceScore"],
            row["score"],
            row["code"],
        ),
        reverse=True,
    )
    payload = {
        "source": "companies+sectors+evidence+quotes",
        "asOf": _now_iso(),
        "totalTickers": len(rows),
        "rows": rows,
    }
    write_json_atomic(RANKING_FILE, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build hidden winner ranking.")
    parser.parse_args()
    payload = refresh_ranking_once()
    print(f"Built ranking: {payload['totalTickers']} rows at {payload['asOf']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
