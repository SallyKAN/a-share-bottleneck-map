"""Independent financial providers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import finite, load_symbols, quote_by_code
from .http import get_json


def confirmation_score(item: dict[str, Any]) -> float:
    score = 50.0
    for key in ("revenueYoY", "netProfitYoY"):
        value = finite(item.get(key))
        if value is not None:
            score += max(min(value, 60), -60) * 0.25
    gross = finite(item.get("grossMargin"))
    if gross is not None:
        score += max(min(gross, 60), 0) * 0.2
    cash = finite(item.get("operatingCashFlow"))
    if cash is not None and cash < 0:
        score -= 8
    return max(0.0, min(100.0, score))


def eastmoney_sec_id(symbol: str) -> str:
    if symbol.startswith(("6", "5", "9")):
        return f"1.{symbol}"
    return f"0.{symbol}"


def parse_report_date(value: Any) -> str | None:
    text = str(value or "")
    return text[:10] if text else None


def fetch_eastmoney_financial(symbol: str) -> dict[str, Any] | None:
    secid = eastmoney_sec_id(symbol)
    payload = get_json(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        params={
            "sortColumns": "REPORT_DATE",
            "sortTypes": "-1",
            "pageSize": 1,
            "pageNumber": 1,
            "reportName": "RPT_DMSK_FN_INCOME",
            "columns": "ALL",
            "filter": f'(SECURITY_CODE="{symbol}")',
            "source": "WEB",
            "client": "WEB",
        },
    )
    rows = payload.get("result", {}).get("data") or []
    if not rows:
        return None
    row = rows[0]
    return {
        "symbol": symbol,
        "period": parse_report_date(row.get("REPORT_DATE")),
        "revenue": finite(row.get("TOTAL_OPERATE_INCOME")),
        "revenueYoY": finite(row.get("TOTAL_OPERATE_INCOME_YOY")),
        "netProfit": finite(row.get("PARENT_NETPROFIT")),
        "netProfitYoY": finite(row.get("PARENT_NETPROFIT_YOY")),
        "grossMargin": None,
        "operatingCashFlow": None,
        "inventory": None,
        "contractLiabilities": None,
        "capex": None,
        "rdExpense": finite(row.get("RESEARCH_EXPENSE")),
        "sourceStatus": {
            "valuation": "quotes_json",
            "earnings": "eastmoney_income",
            "growth": "eastmoney_income",
        },
        "errors": [],
        "_secid": secid,
    }


def quote_fallback_item(symbol: str, quote: dict[str, Any], quote_updated_at: str | None, warning: str | None = None) -> dict[str, Any]:
    item = {
        "symbol": symbol,
        "period": quote_updated_at,
        "revenueYoY": None,
        "netProfitYoY": None,
        "grossMargin": None,
        "operatingCashFlow": None,
        "inventory": None,
        "contractLiabilities": None,
        "capex": None,
        "rdExpense": None,
        "peRatio": finite(quote.get("peRatio")),
        "pbRatio": finite(quote.get("pbRatio")),
        "marketCap": finite(quote.get("marketCap")),
        "amount": finite(quote.get("amount")),
        "turnoverRate": finite(quote.get("turnoverRate")),
        "sourceStatus": {
            "valuation": "quotes_json",
            "earnings": "missing",
            "growth": "missing",
        },
        "errors": [warning] if warning else [],
    }
    item["financialConfirmation"] = 50.0
    return item


def fetch_financials(repo_root: Path, symbols: set[str], limit: int) -> dict[str, Any]:
    quotes, quotes_by_code = quote_by_code(repo_root)
    items = []
    failures = []
    used_eastmoney = 0
    for symbol in load_symbols(repo_root, symbols, limit):
        quote = quotes_by_code.get(symbol, {})
        try:
            item = fetch_eastmoney_financial(symbol)
        except Exception as exc:  # noqa: BLE001
            failures.append({"symbol": symbol, "provider": "eastmoney_income", "error": str(exc)})
            item = None
        if item:
            item["peRatio"] = finite(quote.get("peRatio"))
            item["pbRatio"] = finite(quote.get("pbRatio"))
            item["marketCap"] = finite(quote.get("marketCap"))
            item["amount"] = finite(quote.get("amount"))
            item["turnoverRate"] = finite(quote.get("turnoverRate"))
            item["financialConfirmation"] = round(confirmation_score(item), 2)
            items.append(item)
            used_eastmoney += 1
        elif quote:
            items.append(quote_fallback_item(symbol, quote, quotes.get("updatedAt"), "eastmoney financial unavailable"))
        else:
            failures.append({"symbol": symbol, "provider": "quotes_json", "error": "quote fallback unavailable"})
    warnings = []
    if used_eastmoney < len(items):
        warnings.append("some financial rows use quotes.json valuation fallback; revenue/profit/cash-flow may be unavailable")
    return {
        "source": "eastmoney_financial + quotes.json fallback" if used_eastmoney else "quotes.json fallback",
        "items": items,
        "failureCount": len(failures),
        "failures": failures,
        "warnings": warnings,
    }

