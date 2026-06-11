"""Independent ETF holdings providers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from .common import clean, finite, load_company_map
from .http import get_text


def bottleneck_exposure(holdings: list[dict[str, Any]], company_map: dict[str, dict[str, Any]]) -> dict[str, float]:
    exposure: dict[str, float] = {}
    for holding in holdings:
        company = company_map.get(str(holding.get("symbol")))
        if not company:
            continue
        weight = float(holding.get("weight") or 0)
        for sector in company.get("sectorIds", []):
            exposure[sector] = exposure.get(sector, 0.0) + weight
    return {key: round(value, 4) for key, value in sorted(exposure.items())}


def normalize_weight(value: Any) -> float:
    has_percent = "%" in str(value)
    number = finite(value, 0.0) or 0.0
    return number / 100 if has_percent or number > 1 else number


def eastmoney_holdings(etf_code: str) -> tuple[str, str, list[dict[str, Any]]]:
    text = get_text(
        "https://fundf10.eastmoney.com/FundArchivesDatas.aspx",
        params={
            "type": "jjcc",
            "code": etf_code,
            "topline": 30,
            "year": "",
            "month": "",
        },
    )
    content_match = re.search(r"content:\s*\"(.*)\"\s*,\s*arryear", text, flags=re.S)
    html = content_match.group(1) if content_match else text
    html = html.replace('\\"', '"').replace("\\/", "/")
    soup = BeautifulSoup(html, "html.parser")
    holdings = []
    title_link = soup.select_one("h4.t a")
    etf_name = clean(title_link.get_text(" ", strip=True) if title_link else "", 80)
    for row in soup.select("table tbody tr")[:30]:
        cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
        if len(cells) < 7:
            continue
        symbol = cells[1]
        name = cells[2]
        weight = cells[6]
        if symbol:
            holdings.append({"symbol": str(symbol).zfill(6), "name": clean(name, 80), "weight": normalize_weight(weight)})
    if not holdings:
        raise RuntimeError("eastmoney holdings returned no stock rows")
    return "eastmoney_fund_archives", etf_name, holdings


def akshare_holdings(etf_code: str) -> tuple[str, str, list[dict[str, Any]]]:
    import akshare as ak

    errors = []
    for func_name in ("fund_portfolio_hold_em", "fund_portfolio_hold_all_em", "fund_etf_fund_info_em"):
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
            if symbol:
                holdings.append({"symbol": str(symbol).zfill(6), "name": clean(name, 80), "weight": normalize_weight(weight)})
        if holdings:
            return func_name, "", holdings
    raise RuntimeError("akshare ETF holdings failed: " + "; ".join(errors[:3]))


def fetch_etf_holdings(repo_root: Path, etfs: list[str]) -> dict[str, Any]:
    if not etfs:
        raise RuntimeError("No ETF codes provided. Pass --etfs 512480,159995 or keep using existing cache.")
    company_map = load_company_map(repo_root)
    items = []
    failures = []
    for etf_code in etfs:
        source = ""
        etf_name = ""
        holdings: list[dict[str, Any]] = []
        for provider in (eastmoney_holdings, akshare_holdings):
            try:
                source, etf_name, holdings = provider(etf_code)
                if holdings:
                    break
            except Exception as exc:  # noqa: BLE001
                failures.append({"etfCode": etf_code, "provider": provider.__name__, "error": str(exc)})
        if not holdings:
            continue
        matched = [h["symbol"] for h in holdings if h["symbol"] in company_map]
        exposure = bottleneck_exposure(holdings, company_map)
        top10_weight = sum(float(h.get("weight") or 0) for h in holdings[:10])
        items.append(
            {
                "etfCode": etf_code,
                "etfName": etf_name,
                "theme": "",
                "holdings": holdings,
                "top10Weight": round(top10_weight, 4),
                "matchedCompanies": matched,
                "bottleneckExposure": exposure,
                "purityScore": round(min(sum(exposure.values()) * 100, 100), 2),
                "source": source,
            }
        )
    return {
        "source": "independent_etf_holdings",
        "items": items,
        "failureCount": len(failures),
        "failures": failures,
        "warnings": [],
    }
