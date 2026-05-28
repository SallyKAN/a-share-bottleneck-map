#!/usr/bin/env python3
"""Local app server for A股AI扩张瓶颈地图.

Serves static files and exposes click-triggered data refresh APIs.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from scripts.dsa_bridge import health as dsa_health
from scripts.refresh_candidates import refresh_candidates_once
from scripts.refresh_evidence import refresh_evidence_once
from scripts.refresh_quotes import refresh_once
from scripts.refresh_ranking import refresh_ranking_once


PROJECT_ROOT = Path(__file__).resolve().parent
DIST_ROOT = PROJECT_ROOT / "dist"


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        if parsed.path == "/api/refresh-candidates":
            self._handle_refresh_candidates()
            return
        if parsed.path == "/api/refresh-quotes":
            self._handle_refresh_quotes()
            return
        if parsed.path == "/api/refresh-evidence":
            self._handle_refresh_evidence()
            return
        if parsed.path == "/api/refresh-ranking":
            self._handle_refresh_ranking()
            return
        if parsed.path == "/api/refresh-all":
            self._handle_refresh_all()
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"success": False, "error": "not_found"})

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json(HTTPStatus.OK, {"success": True, **self._data_health(), "dsa": dsa_health()})
            return
        if parsed.path.startswith("/api/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"success": False, "error": "not_found"})
            return
        self._serve_static_or_spa(parsed.path)

    def _data_health(self) -> dict:
        files = {}
        for name in ("sectors", "companies", "candidate_pool", "evidence", "quotes", "ranking"):
            path = PROJECT_ROOT / "data" / f"{name}.json"
            files[name] = {
                "exists": path.exists(),
                "updatedAt": path.stat().st_mtime if path.exists() else None,
            }
        return {"dataFiles": files}

    def _serve_static_or_spa(self, path: str) -> None:
        if DIST_ROOT.exists():
            requested = path.lstrip("/") or "index.html"
            if requested.startswith("data/"):
                data_target = (PROJECT_ROOT / requested).resolve()
                if data_target.is_file() and data_target.is_relative_to(PROJECT_ROOT.resolve()):
                    self.path = "/" + requested
                    return SimpleHTTPRequestHandler.do_GET(self)
            target = (DIST_ROOT / requested).resolve()
            dist_resolved = DIST_ROOT.resolve()
            if target.is_file() and target.is_relative_to(dist_resolved):
                self.path = "/dist/" + requested
                return SimpleHTTPRequestHandler.do_GET(self)
            self.path = "/dist/index.html"
            return SimpleHTTPRequestHandler.do_GET(self)
        return SimpleHTTPRequestHandler.do_GET(self)

    def _handle_refresh_candidates(self) -> None:
        try:
            payload = refresh_candidates_once(max_candidates=300, max_promoted_per_sector=30, max_queries_per_sector=4)
            ranking = refresh_ranking_once()
        except Exception as exc:  # noqa: BLE001
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"success": False, "error": str(exc)})
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "success": True,
                "updatedAt": payload.get("updatedAt"),
                "itemCount": payload.get("itemCount"),
                "promotedCount": payload.get("promotedCount"),
                "rankingRows": ranking.get("totalTickers"),
                "failureCount": payload.get("failureCount"),
                "failures": payload.get("failures", []),
            },
        )

    def _handle_refresh_quotes(self) -> None:
        try:
            payload = refresh_once(sleep_seconds=0.05)
        except Exception as exc:  # noqa: BLE001 - report API failure to UI
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"success": False, "error": str(exc)},
            )
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "success": True,
                "updatedAt": payload.get("updatedAt"),
                "itemCount": payload.get("itemCount"),
                "failureCount": payload.get("failureCount"),
                "failures": payload.get("failures", []),
            },
        )

    def _handle_refresh_ranking(self) -> None:
        try:
            payload = refresh_ranking_once()
        except Exception as exc:  # noqa: BLE001
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"success": False, "error": str(exc)})
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "success": True,
                "asOf": payload.get("asOf"),
                "totalTickers": payload.get("totalTickers"),
            },
        )

    def _handle_refresh_all(self) -> None:
        results = {}
        failures = []
        steps = [
            ("candidates", lambda: refresh_candidates_once(max_candidates=300, max_promoted_per_sector=30)),
            ("quotes", lambda: refresh_once(sleep_seconds=0.05)),
            ("evidence", lambda: refresh_evidence_once(max_companies=0, max_searches=4, results_per_dimension=2)),
            ("ranking", refresh_ranking_once),
        ]
        for name, fn in steps:
            try:
                results[name] = fn()
            except Exception as exc:  # noqa: BLE001 - refresh-all should return partial results
                failures.append({"step": name, "error": str(exc)})
        status = HTTPStatus.MULTI_STATUS if failures else HTTPStatus.OK
        self._send_json(status, {"success": not failures, "results": results, "failures": failures})

    def _handle_refresh_evidence(self) -> None:
        try:
            payload = refresh_evidence_once(
                max_companies=0,
                max_searches=4,
                results_per_dimension=2,
                sleep_seconds=0.1,
            )
        except Exception as exc:  # noqa: BLE001 - report API failure to UI
            status = HTTPStatus.SERVICE_UNAVAILABLE if "搜索服务不可用" in str(exc) else HTTPStatus.INTERNAL_SERVER_ERROR
            self._send_json(status, {"success": False, "error": str(exc)})
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "success": True,
                "updatedAt": payload.get("updatedAt"),
                "itemCount": payload.get("itemCount"),
                "companyCount": payload.get("companyCount"),
                "failureCount": payload.get("failureCount"),
                "failures": payload.get("failures", []),
            },
        )


def main() -> int:
    host = "127.0.0.1"
    port = 5173
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Serving A股AI扩张瓶颈地图 on http://{host}:{port}/")
    print("POST /api/refresh-quotes will refresh data/quotes.json via daily_stock_analysis.")
    print("POST /api/refresh-evidence will refresh data/evidence.json via daily_stock_analysis SearchService.")
    print("POST /api/refresh-candidates and /api/refresh-ranking update the research system snapshots.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
