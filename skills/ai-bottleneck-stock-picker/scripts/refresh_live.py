#!/usr/bin/env python3
"""V2 live data cache entrypoint.

This first implementation creates/inspects live cache files and defines the
command contract for future provider-specific fetchers.
"""

from __future__ import annotations

import argparse
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


def empty_payload(name: str) -> dict[str, Any]:
    return {
        "source": "not_configured",
        "updatedAt": None,
        "cacheName": name,
        "items": [],
        "warnings": ["live provider not implemented yet"],
    }


def read_cache(repo_root: Path, name: str) -> dict[str, Any]:
    path = cache_path(repo_root, name)
    if not path.exists():
        return empty_payload(name)
    return json.loads(path.read_text(encoding="utf-8"))


def init_cache(repo_root: Path) -> dict[str, Any]:
    directory = cache_dir(repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    created = []
    for name in CACHE_NAMES:
        path = cache_path(repo_root, name)
        if not path.exists():
            path.write_text(json.dumps(empty_payload(name), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            created.append(str(path))
    return {"updatedAt": now_iso(), "cacheDir": str(directory), "created": created}


def status(repo_root: Path) -> dict[str, Any]:
    payload = {"updatedAt": now_iso(), "cacheDir": str(cache_dir(repo_root)), "caches": {}}
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage V2 live cache placeholders.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    if args.command == "init":
        payload = init_cache(repo_root)
    elif args.command == "status":
        payload = status(repo_root)
    else:
        raise AssertionError(args.command)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
