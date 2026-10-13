#!/usr/bin/env python3
"""Serve enough of the Confluence content API to verify the release sync.

    uv run python scripts/mock_confluence_api.py --port 8099 --parent-id 123456

There is usually no instance to point a development environment at, so this
answers the four calls the sync makes, keeps the pages in memory, and logs every
request - which is what makes a sync watchable from the terminal.

Point PRLedger at it with:

    CONFLUENCE_SERVER_BASE_URL=http://127.0.0.1:8099
    CONFLUENCE_SERVER_TOKEN=mock-token
    CONFLUENCE_SERVER_SYNC_ENABLED=True

Then set a space for the repository (System settings -> Confluence Publishing, or
``CONFLUENCE_SERVER_SPACE_KEY``), publish a release, and watch it arrive here. Open
http://127.0.0.1:8099/ for the pages written so far.

Three things it enforces on purpose, because they are the mistakes worth catching:

* an ``Authorization`` header, so the credential is part of what is under test;
* a parent page id it was told about with ``--parent-id``, and 400 otherwise - the
  way an instance refuses a page that does not exist;
* the version number going up on an update, and 409 otherwise.

It is a stub: nothing is persisted, and a restart forgets every page.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlparse


CONTENT_PATH = "/rest/api/content"

# Ids the pages this stub creates are given. A parent page id handed in with
# --parent-id is kept as it was given, so a realistic (and long) id can be used.
FIRST_GENERATED_ID = 100


class ConfluenceState:
    """The pages the stub holds, and how a request is answered."""

    def __init__(self, hosted_at: str) -> None:
        self.pages: dict[str, dict[str, Any]] = {}
        self.hosted_at = hosted_at
        self._lock = Lock()
        self._next_id = FIRST_GENERATED_ID

    # -- reading ---------------------------------------------------------- #

    def list_pages(self) -> list[dict[str, Any]]:
        return sorted(self.pages.values(), key=lambda page: int(page["id"]))

    def find(self, space_key: str, title: str) -> list[dict[str, Any]]:
        return [
            page
            for page in self.list_pages()
            if page["space"]["key"] == space_key and page["title"] == title
        ]

    def get(self, page_id: str) -> dict[str, Any] | None:
        return self.pages.get(page_id)

    # -- writing ---------------------------------------------------------- #

    def create(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Create a page, or refuse it the way an instance would.

        Returns the status to answer with and the body or the reason.
        """
        with self._lock:
            problem = self._check_parent(payload)
            if problem:
                return 400, {"statusCode": 400, "message": problem}

            page_id = self._allocate_id()
            self.pages[page_id] = {
                "id": page_id,
                "type": "page",
                "title": payload["title"],
                "space": {"key": payload["space"]["key"]},
                "body": payload.get("body") or {},
                "version": {"number": 1},
                "ancestors": payload.get("ancestors") or [],
                **_links(self.hosted_at, payload["space"]["key"], page_id),
            }
            return 200, self.pages[page_id]

    def update(self, page_id: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Update a page, insisting on the version moving on, as Confluence does."""
        with self._lock:
            page = self.pages.get(page_id)
            if page is None:
                return 404, {"statusCode": 404, "message": f"No page with id {page_id}"}

            problem = self._check_parent(payload)
            if problem:
                return 400, {"statusCode": 400, "message": problem}

            current = (page.get("version") or {}).get("number", 0)
            expected = current + 1
            given = (payload.get("version") or {}).get("number")
            if given != expected:
                return 409, {
                    "statusCode": 409,
                    "message": (
                        f"A page at version {current} has to be updated with version "
                        f"{expected}, not {given}"
                    ),
                }

            space_key = (payload.get("space") or {}).get("key") or page["space"]["key"]
            self.pages[page_id] = {
                **page,
                "title": payload["title"],
                "space": {"key": space_key},
                "body": payload.get("body") or page.get("body") or {},
                "version": {"number": expected},
                "ancestors": payload.get("ancestors") or page.get("ancestors") or [],
            }
            return 200, self.pages[page_id]

    def seed_parent(self, page_id: str, title: str, space_key: str) -> None:
        """A page that may be used as a parent, as an existing one would be."""
        self.pages[page_id] = {
            "id": page_id,
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {},
            "version": {"number": 1},
            "ancestors": [],
            **_links(self.hosted_at, space_key, page_id),
        }

    # -- helpers ---------------------------------------------------------- #

    def _check_parent(self, payload: dict[str, Any]) -> str | None:
        """A parent has to be a page this stub knows, as on a real instance."""
        ancestors = payload.get("ancestors") or []
        if not ancestors:
            return None

        parent_id = str((ancestors[0] or {}).get("id") or "")
        if not parent_id:
            return "an ancestor was given without an id"
        if parent_id not in self.pages:
            return (
                f"No parent page with id {parent_id} - start this stub with "
                f"--parent-id {parent_id} to stand in for one"
            )
        return None

    def _allocate_id(self) -> str:
        while str(self._next_id) in self.pages:
            self._next_id += 1
        page_id = str(self._next_id)
        self._next_id += 1
        return page_id


def _links(base_url: str, space_key: str, page_id: str) -> dict[str, Any]:
    """The links the client builds the page URL from."""
    return {
        "_links": {
            "base": base_url,
            "webui": f"/spaces/{space_key}/pages/{page_id}",
        }
    }


def render_index(state: ConfluenceState) -> str:
    """The pages written so far, so a sync can be seen to have happened."""
    pages = state.list_pages()
    if not pages:
        rows = "<tr><td colspan='5'>No pages yet. Publish a release, or sync one by hand.</td></tr>"
    else:
        rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(page['id'])}</td>"
            f"<td>{html.escape(page['space']['key'])}</td>"
            f"<td>{html.escape(page['title'])}</td>"
            f"<td>{html.escape(page['ancestors'][0]['id']) if page['ancestors'] else '—'}</td>"
            f"<td>v{(page.get('version') or {}).get('number', '?')}</td>"
            "</tr>"
            for page in pages
        )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Mock Confluence</title>
<style>
  body {{ font: 14px system-ui, sans-serif; margin: 24px; }}
  table {{ border-collapse: collapse; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
  th {{ background: #f4f4f4; }}
  code {{ background: #f4f4f4; padding: 1px 4px; }}
</style></head>
<body>
<h1>Mock Confluence</h1>
<p>{len(pages)} page(s). Requests are logged in the terminal this runs in.</p>
<table>
  <tr><th>id</th><th>space</th><th>title</th><th>parent</th><th>version</th></tr>
  {rows}
</table>
<p>The API lives under <code>{CONTENT_PATH}</code>.</p>
</body></html>"""


class MockConfluenceHandler(BaseHTTPRequestHandler):
    """The calls the release sync makes, and a page listing what it wrote."""

    state: ConfluenceState
    server_version = "MockConfluence/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Silence the default per-request line; each call reports itself below."""

    def do_GET(self) -> None:  # noqa: N802 - the name http.server calls
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._html(render_index(self.state))
            return

        if parsed.path == CONTENT_PATH:
            if not self._authorised():
                return
            params = parse_qs(parsed.query)
            space_key = (params.get("spaceKey") or [""])[0]
            title = (params.get("title") or [""])[0]
            found = self.state.find(space_key, title)
            print(
                f"GET  {CONTENT_PATH} space={space_key!r} title={title!r} -> {len(found)} page(s)"
            )
            self._json(200, {"results": found, "size": len(found)})
            return

        if parsed.path.startswith(f"{CONTENT_PATH}/"):
            if not self._authorised():
                return
            page_id = parsed.path.rsplit("/", 1)[-1]
            page = self.state.get(page_id)
            print(f"GET  {CONTENT_PATH}/{page_id} -> {'found' if page else '404'}")
            if page is None:
                self._json(404, {"statusCode": 404, "message": f"No page with id {page_id}"})
                return
            self._json(200, page)
            return

        self._json(404, {"statusCode": 404, "message": f"No such path {parsed.path}"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != CONTENT_PATH or not self._authorised():
            self._json(404, {"statusCode": 404, "message": "No such path"})
            return

        payload = self._payload()
        if payload is None:
            return
        for field in ("title", "space"):
            if not payload.get(field):
                self._json(400, {"statusCode": 400, "message": f"'{field}' is required"})
                return

        status, body = self.state.create(payload)
        if status == 200:
            parent = (payload.get("ancestors") or [{}])[0].get("id")
            print(
                f"POST {CONTENT_PATH} -> created page {body['id']} "
                f"{body['title']!r} in {body['space']['key']}"
                + (f" under {parent}" if parent else " (no parent)")
            )
        else:
            print(f"POST {CONTENT_PATH} -> {status} {body['message']}")
        self._json(status, body)

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not parsed.path.startswith(f"{CONTENT_PATH}/") or not self._authorised():
            self._json(404, {"statusCode": 404, "message": "No such path"})
            return

        payload = self._payload()
        if payload is None:
            return

        page_id = parsed.path.rsplit("/", 1)[-1]
        status, body = self.state.update(page_id, payload)
        if status == 200:
            print(
                f"PUT  {CONTENT_PATH}/{page_id} -> updated {body['title']!r} to "
                f"v{body['version']['number']}"
            )
        else:
            print(f"PUT  {CONTENT_PATH}/{page_id} -> {status} {body['message']}")
        self._json(status, body)

    # -- plumbing --------------------------------------------------------- #

    def _authorised(self) -> bool:
        """The sync sends a credential; an absent or empty one is what this catches.

        An empty pair still arrives as a well-formed ``Basic`` header, so the header
        is decoded rather than pattern-matched: otherwise the one mistake this is
        here to catch would pass.
        """
        header = self.headers.get("Authorization") or ""
        scheme, _, value = header.partition(" ")
        if scheme == "Bearer" and value.strip():
            return True
        if scheme == "Basic" and value.strip():
            try:
                pair = base64.b64decode(value).decode()
            except (ValueError, UnicodeDecodeError):
                pair = ""
            if pair.strip(":"):
                return True

        print(f"{self.command} {urlparse(self.path).path} -> 401 no credential")
        self._json(
            401,
            {
                "statusCode": 401,
                "message": (
                    "An Authorization header is required - set CONFLUENCE_SERVER_TOKEN or "
                    "CONFLUENCE_SERVER_USERNAME/CONFLUENCE_SERVER_PASSWORD"
                ),
            },
        )
        return False

    def _payload(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            parsed = json.loads(raw or b"{}")
        except json.JSONDecodeError as e:
            self._json(400, {"statusCode": 400, "message": f"Body is not JSON: {e}"})
            return None
        return parsed if isinstance(parsed, dict) else {}

    def _json(self, status: int, body: Any) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _html(self, body: str) -> None:
        encoded = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> int:
    # Each request reports itself as it is served: a redirected log would otherwise
    # hold everything back until the process ended, which is exactly the process
    # somebody is watching rather than ending.
    sys.stdout.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(description="Mock Confluence content API")
    parser.add_argument("--port", type=int, default=8099, help="Port to listen on")
    parser.add_argument("--host", default="127.0.0.1", help="Address to bind")
    parser.add_argument(
        "--parent-id",
        action="append",
        default=[],
        help=(
            "A page id that may be used as a parent (repeatable). Without it a page "
            "naming a parent is refused, as it would be on an instance"
        ),
    )
    parser.add_argument(
        "--space",
        default="DOCS",
        help="Space the seeded parent pages belong to",
    )
    args = parser.parse_args()

    state = ConfluenceState(hosted_at=f"http://{args.host}:{args.port}")
    for page_id in args.parent_id:
        state.seed_parent(page_id, f"Parent page {page_id}", args.space)

    server = ThreadingHTTPServer((args.host, args.port), MockConfluenceHandler)
    MockConfluenceHandler.state = state

    print(f"Mock Confluence on http://{args.host}:{args.port}")
    print(f"  API:   {args.host}:{args.port}{CONTENT_PATH}")
    print(f"  Pages: http://{args.host}:{args.port}/")
    if args.parent_id:
        print(f"  Parent page ids: {', '.join(args.parent_id)} (space {args.space})")
    print("  Any Bearer/Basic credential is accepted; requests are logged below.")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
