#!/usr/bin/env python3
"""Fetch ETF holdings cache using independent providers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from live_cache import DEFAULT_REPO_ROOT, now_iso, read_cache, write_cache, write_non_empty_cache
from providers.etf_holdings import fetch_etf_holdings


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
        payload = fetch_etf_holdings(repo_root, etfs)
        payload["updatedAt"] = now_iso()
        payload["cacheName"] = "etf_holdings"
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
