"""The SecurityHeadersMiddleware must actually be wired up and emit headers."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from src.core.middleware import SecurityHeadersMiddleware


def build_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    async def ping():  # pragma: no cover - trivial handler
        return {"ok": True}

    # Stand-ins for the pages fastapi_offline generates: Swagger UI, its OAuth
    # redirect, ReDoc, plus a path that merely starts with a docs prefix.
    for path in (
        "/api/docs",
        "/api/docs/oauth2-redirect",
        "/api/redoc",
        "/api/docsomethin-else",
    ):

        async def docs_page(path: str = path):  # pragma: no cover - trivial handler
            return HTMLResponse(f"<html><body>{path}</body></html>")

        app.add_api_route(path, docs_page, methods=["GET"])

    return TestClient(app)


def test_security_headers_are_present():
    response = build_client().get("/ping")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "Strict-Transport-Security" in response.headers


def test_csp_blocks_scripts_but_allows_report_styles():
    csp = build_client().get("/ping").headers["Content-Security-Policy"]

    assert "script-src 'self';" in csp
    # The App Diff HTML report ships its own <style> block
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "frame-ancestors 'none'" in csp


def test_docs_pages_may_run_their_inline_bootstrap_script():
    client = build_client()

    for path in ("/api/docs", "/api/docs/oauth2-redirect", "/api/redoc"):
        csp = client.get(path).headers["Content-Security-Policy"]
        assert "script-src 'self' 'unsafe-inline'" in csp, path


def test_docs_exception_does_not_leak_to_lookalike_paths():
    client = build_client()

    for path in ("/ping", "/api/docsomethin-else"):
        csp = client.get(path).headers["Content-Security-Policy"]
        assert "script-src 'self';" in csp, path
        assert "'unsafe-inline'" not in csp.split("style-src")[0], path


def test_obsolete_xss_header_is_disabled():
    headers = build_client().get("/ping").headers

    assert headers["X-XSS-Protection"] == "0"
