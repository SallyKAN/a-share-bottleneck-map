"""Shared live-cache helpers for the AI bottleneck stock picker."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO_ROOT = SKILL_ROOT.parents[1]
CACHE_NAMES = ("live_news", "financials", "etf_holdings", "technicals")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cache_dir(repo_root: Path) -> Path:
    return repo_root / ".cache" / "ai-bottleneck-stock-picker"


def cache_path(repo_root: Path, name: str) -> Path:
    return cache_dir(repo_root) / f"{name}.json"


def empty_payload(name: str, warning: str = "live provider not configured") -> dict[str, Any]:
    return {
        "source": "not_configured",
        "updatedAt": None,
        "cacheName": name,
        "items": [],
        "warnings": [warning],
    }


def read_cache(repo_root: Path, name: str) -> dict[str, Any]:
    path = cache_path(repo_root, name)
    if not path.exists():
        return empty_payload(name)
    return json.loads(path.read_text(encoding="utf-8"))


def write_cache(repo_root: Path, name: str, payload: dict[str, Any]) -> None:
    directory = cache_dir(repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = cache_path(repo_root, name)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_non_empty_cache(repo_root: Path, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items", [])
    if not items:
        previous = read_cache(repo_root, name)
        previous_items = previous.get("items", [])
        warning = f"{name} refresh returned 0 items; kept previous cache"
        if previous_items:
            previous = dict(previous)
            previous["warnings"] = list(previous.get("warnings", [])) + [warning]
            write_cache(repo_root, name, previous)
            return previous
        raise RuntimeError(warning)
    write_cache(repo_root, name, payload)
    return payload


def init_caches(repo_root: Path) -> dict[str, Any]:
    directory = cache_dir(repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    created = []
    for name in CACHE_NAMES:
        path = cache_path(repo_root, name)
        if not path.exists():
            write_cache(repo_root, name, empty_payload(name, "live provider not implemented yet"))
            created.append(str(path))
    return {"updatedAt": now_iso(), "cacheDir": str(directory), "created": created}


def status(repo_root: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {"updatedAt": now_iso(), "cacheDir": str(cache_dir(repo_root)), "caches": {}}
    for name in CACHE_NAMES:
        data = read_cache(repo_root, name)
        payload["caches"][name] = {
            "exists": cache_path(repo_root, name).exists(),
            "source": data.get("source"),
            "updatedAt": data.get("updatedAt"),
            "itemCount": len(data.get("items", [])),
            "warnings": data.get("warnings", []),
        }
    return payload
