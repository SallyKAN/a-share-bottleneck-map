"""Small HTTP helpers with JSONP support."""

from __future__ import annotations

import json
import re
from typing import Any

import requests


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://fund.eastmoney.com/",
}


def get_text(url: str, *, params: dict[str, Any] | None = None, timeout: int = 8) -> str:
    response = requests.get(url, params=params or {}, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    if "qt.gtimg.cn" in url:
        response.encoding = "gbk"
    else:
        response.encoding = response.apparent_encoding or response.encoding
    return response.text


def parse_json_or_jsonp(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped)
    match = re.search(r"^[\w$]+\((.*)\)\s*;?$", stripped, flags=re.S)
    if match:
        return json.loads(match.group(1))
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return json.loads(stripped[start : end + 1])
    raise ValueError("response is not JSON or JSONP")


def get_json(url: str, *, params: dict[str, Any] | None = None, timeout: int = 8) -> Any:
    return parse_json_or_jsonp(get_text(url, params=params, timeout=timeout))
