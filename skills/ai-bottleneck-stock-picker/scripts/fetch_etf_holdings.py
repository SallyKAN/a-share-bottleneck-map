#!/usr/bin/env python3
"""Fetch ETF holdings cache.

Uses akshare when available. If no provider is available, keeps previous cache.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from live_cache import DEFAULT_REPO_ROOT, now_iso, read_cache, write_cache, write_non_empty_cache


def load_company_map(repo_root: Path) -> dict[str, dict[str, Any]]:
    companies = json.loads((repo_root / "data" / "companies.json").read_text(encoding="utf-8"))
    return {str(item.get("code")): item for item in companies}


def bottleneck_exposure(holdings: list[dict[str, Any]], company_map: dict[str, dict[str, Any]]) -> dict[str, float]:
    exposure: dict[str, float] = {}
    for holding in holdings:
        company = company_map.get(str(holding.get("symbol")))
        if not company:
            continue
        weight = float(holding.get("weight") or 0)
        sectors = company.get("sectorIds", [])
        for sector in sectors:
            exposure[sector] = exposure.get(sector, 0.0) + weight
    return {key: round(value, 4) for key, value in sorted(exposure.items())}


def try_akshare_holdings(etf_code: str) -> tuple[str, list[dict[str, Any]]]:
    import akshare as ak

    candidate_funcs = [
        "fund_portfolio_hold_em",
        "fund_portfolio_hold_all_em",
        "fund_etf_fund_info_em",
    ]
    errors = []
    for func_name in candidate_funcs:
        func = getattr(ak, func_name, None)
        if func is None:
            continue
        try:
            df = func(symbol=etf_code)
        except TypeError:
            try:
                df = func(fund=etf_code)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{func_name}: {exc}")
                continue
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{func_name}: {exc}")
            continue
        if getattr(df, "empty", True):
            continue
        holdings = []
        for _, row in df.head(30).iterrows():
            row_dict = row.to_dict()
            symbol = row_dict.get("股票代码") or row_dict.get("证券代码") or row_dict.get("代码")
            name = row_dict.get("股票名称") or row_dict.get("证券名称") or row_dict.get("名称")
            weight = row_dict.get("占净值比例") or row_dict.get("持仓占比") or row_dict.get("占比")
            try:
                weight_value = float(str(weight).replace("%", "")) / (100 if "%" in str(weight) else 1)
            except Exception:  # noqa: BLE001
                weight_value = 0.0
            if symbol:
                holdings.append({"symbol": str(symbol).zfill(6), "name": str(name or ""), "weight": weight_value})
        if holdings:
            return func_name, holdings
    raise RuntimeError("akshare ETF holdings failed: " + "; ".join(errors[:3]))


def fetch(repo_root: Path, etfs: list[str]) -> dict[str, Any]:
    if not etfs:
        raise RuntimeError("No ETF codes provided. Pass --etfs 512480,159995 or keep using existing cache.")
    company_map = load_company_map(repo_root)
    items = []
    failures = []
    for etf_code in etfs:
        try:
            source, holdings = try_akshare_holdings(etf_code)
            matched = [h["symbol"] for h in holdings if h["symbol"] in company_map]
            exposure = bottleneck_exposure(holdings, company_map)
            top10_weight = sum(float(h.get("weight") or 0) for h in holdings[:10])
            items.append(
                {
                    "etfCode": etf_code,
                    "etfName": "",
                    "theme": "",
                    "holdings": holdings,
                    "top10Weight": round(top10_weight, 4),
                    "matchedCompanies": matched,
                    "bottleneckExposure": exposure,
                    "purityScore": round(min(sum(exposure.values()) * 100, 100), 2),
                    "source": source,
                }
            )
        except Exception as exc:  # noqa: BLE001
            failures.append({"etfCode": etf_code, "error": str(exc)})
    return {
        "source": "akshare",
        "updatedAt": now_iso(),
        "cacheName": "etf_holdings",
        "items": items,
        "failureCount": len(failures),
        "failures": failures,
        "warnings": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch ETF holdings cache.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--symbols", default="", help="Ignored; use --etfs for ETF codes")
    parser.add_argument("--etfs", default="")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    etfs = [s.strip() for s in args.etfs.split(",") if s.strip()]
    try:
        payload = fetch(repo_root, etfs)
        payload = write_non_empty_cache(repo_root, "etf_holdings", payload)
    except Exception as exc:  # noqa: BLE001
        payload = read_cache(repo_root, "etf_holdings")
        payload = dict(payload)
        payload["warnings"] = list(payload.get("warnings", [])) + [f"etf_holdings refresh failed: {exc}"]
        write_cache(repo_root, "etf_holdings", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
