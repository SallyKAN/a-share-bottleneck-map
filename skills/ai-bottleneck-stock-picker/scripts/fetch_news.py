#!/usr/bin/env python3
"""Fetch live news cache using independent providers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from live_cache import DEFAULT_REPO_ROOT, now_iso, read_cache, write_cache, write_non_empty_cache
from providers.news import fetch_news


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch live news cache.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--symbols", default="")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--results-per-company", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    symbols = {s.strip() for s in args.symbols.split(",") if s.strip()}
    try:
        payload = fetch_news(repo_root, symbols, args.limit, args.results_per_company)
        payload["updatedAt"] = now_iso()
        payload["cacheName"] = "live_news"
        payload = write_non_empty_cache(repo_root, "live_news", payload)
    except Exception as exc:  # noqa: BLE001
        payload = read_cache(repo_root, "live_news")
        payload = dict(payload)
        payload["warnings"] = list(payload.get("warnings", [])) + [f"live_news refresh failed: {exc}"]
        write_cache(repo_root, "live_news", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
