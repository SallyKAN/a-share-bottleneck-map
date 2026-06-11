#!/usr/bin/env python3
"""Fetch financial confirmation cache using independent providers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from live_cache import DEFAULT_REPO_ROOT, now_iso, write_cache, write_non_empty_cache
from providers.financials import fetch_financials


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch financial confirmation cache.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--symbols", default="")
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    symbols = {s.strip() for s in args.symbols.split(",") if s.strip()}
    try:
        payload = fetch_financials(repo_root, symbols, args.limit)
        payload["updatedAt"] = now_iso()
        payload["cacheName"] = "financials"
        payload = write_non_empty_cache(repo_root, "financials", payload)
    except Exception as exc:  # noqa: BLE001
        payload = {
            "source": "independent_financials_failed",
            "updatedAt": now_iso(),
            "cacheName": "financials",
            "items": [],
            "failureCount": 1,
            "failures": [{"error": str(exc)}],
            "warnings": [f"financials refresh failed: {exc}"],
        }
        write_cache(repo_root, "financials", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
