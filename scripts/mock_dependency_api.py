#!/usr/bin/env python3
"""Serve the dependency database's answer from canned data, over real HTTP.

    uv run python scripts/mock_dependency_api.py --port 9091

Answers ``GET /api/v1/appReleaseInfo?app_name=<name>&tagOrBranch=<ref>`` with the
payload PRLedger consolidates, and 404 for an application the canned data does
not know - which is how an unregistered repository reads. The payloads are the
same ones the client serves while ``DEPENDENCY_API_MOCK`` is on, so the two
cannot drift.

Point PRLedger at it with:

    DEPENDENCY_API_MOCK=False
    DEPENDENCY_API_BASE_URL=http://127.0.0.1:9091
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.dependency_mock_data import (  # noqa: E402
    known_app_names,
    release_info_for,
)


RELEASE_PATH = "/api/v1/appReleaseInfo"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - the name is fixed by the stdlib
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") != RELEASE_PATH:
            self.answer(404, {"detail": {"error": "not_found", "path": parsed.path}})
            return

        query = parse_qs(parsed.query)
        app_name = (query.get("app_name") or [""])[0]
        tag_or_branch = (query.get("tagOrBranch") or [""])[0]

        payload = release_info_for(app_name, tag_or_branch)
        if payload is None:
            self.answer(
                404,
                {"detail": {"error": "dependency_graph_not_found", "app_name": app_name}},
            )
            return
        self.answer(200, payload)

    def do_POST(self) -> None:  # noqa: N802 - the name is fixed by the stdlib
        self.answer(405, {"detail": {"error": "method_not_allowed"}})

    def answer(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[mock-dependency-api] {self.address_string()} {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock dependency database API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9091)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving {RELEASE_PATH} on http://{args.host}:{args.port}")
    print(f"  applications: {', '.join(known_app_names())}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
