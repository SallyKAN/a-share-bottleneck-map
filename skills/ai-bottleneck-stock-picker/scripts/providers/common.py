"""Shared helpers for independent live providers."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").split())[:limit]


def finite(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("%", "")
        if text in {"", "-", "--", "None", "null"}:
            return default
        try:
            return float(text)
        except ValueError:
            return default
    return default


def load_companies(repo_root: Path, symbols: set[str], limit: int) -> list[dict[str, Any]]:
    companies = json.loads((repo_root / "data" / "companies.json").read_text(encoding="utf-8"))
    if symbols:
        return [c for c in companies if str(c.get("code")) in symbols]
    ranking = json.loads((repo_root / "data" / "ranking.json").read_text(encoding="utf-8"))
    top_codes = [str(row.get("code")) for row in ranking.get("rows", [])[:limit]]
    by_code = {str(c.get("code")): c for c in companies}
    return [by_code[code] for code in top_codes if code in by_code]


def load_symbols(repo_root: Path, symbols: set[str], limit: int) -> list[str]:
    if symbols:
        return sorted(symbols)
    ranking = json.loads((repo_root / "data" / "ranking.json").read_text(encoding="utf-8"))
    return [str(row.get("code")) for row in ranking.get("rows", [])[:limit] if row.get("code")]


def load_company_map(repo_root: Path) -> dict[str, dict[str, Any]]:
    companies = json.loads((repo_root / "data" / "companies.json").read_text(encoding="utf-8"))
    return {str(item.get("code")): item for item in companies}


def quote_by_code(repo_root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    quotes = json.loads((repo_root / "data" / "quotes.json").read_text(encoding="utf-8"))
    return quotes, {str(item.get("code")): item for item in quotes.get("items", [])}

