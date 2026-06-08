#!/usr/bin/env python3
"""V2 live data cache entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from live_cache import DEFAULT_REPO_ROOT, init_caches, status


def run_fetcher(script: str, repo_root: Path, symbols: str, limit: int, etfs: str = "") -> dict:
    script_path = Path(__file__).resolve().parent / script
    cmd = [sys.executable, str(script_path), "--repo-root", str(repo_root)]
    if symbols:
        cmd.extend(["--symbols", symbols])
    if etfs:
        cmd.extend(["--etfs", etfs])
    if limit:
        cmd.extend(["--limit", str(limit)])
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    return {
        "script": script,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage V2 live cache placeholders.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--symbols", default="", help="Comma-separated symbols for live fetchers")
    parser.add_argument("--etfs", default="", help="Comma-separated ETF codes for ETF holding refresh")
    parser.add_argument("--limit", type=int, default=20, help="Max symbols/items per fetcher")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_shared_options(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--repo-root", default=argparse.SUPPRESS)
        command_parser.add_argument("--symbols", default=argparse.SUPPRESS, help="Comma-separated symbols for live fetchers")
        command_parser.add_argument("--etfs", default=argparse.SUPPRESS, help="Comma-separated ETF codes for ETF holding refresh")
        command_parser.add_argument("--limit", type=int, default=argparse.SUPPRESS, help="Max symbols/items per fetcher")

    init_parser = sub.add_parser("init")
    add_shared_options(init_parser)
    status_parser = sub.add_parser("status")
    add_shared_options(status_parser)
    all_parser = sub.add_parser("all")
    add_shared_options(all_parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    if args.command == "init":
        payload = init_caches(repo_root)
    elif args.command == "status":
        payload = status(repo_root)
    elif args.command == "all":
        init_caches(repo_root)
        payload = {
            "repoRoot": str(repo_root),
            "results": [
                run_fetcher("fetch_technicals.py", repo_root, args.symbols, args.limit),
                run_fetcher("fetch_news.py", repo_root, args.symbols, args.limit),
                run_fetcher("fetch_financials.py", repo_root, args.symbols, args.limit),
                run_fetcher("fetch_etf_holdings.py", repo_root, "", args.limit, etfs=args.etfs),
            ],
            "status": status(repo_root),
        }
    else:
        raise AssertionError(args.command)
    import json

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
