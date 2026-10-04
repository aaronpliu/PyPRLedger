"""Tests for the dependency database client.

The transport is faked, so no dependency database is contacted: what is
asserted is the question the client asks and the answer it hands back.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from src.core.config import settings
from src.core.exceptions import DependencyApiException
from src.services import dependency_api_client
from src.services.dependency_api_client import DependencyApiClient


REPLY: dict[str, Any] = {
    "app_name": "pylang",
    "tagOrBranch": "1.0.0_10000",
    "dependencies": {"packageA": "1.0.0"},
    "packages": [],
}


def point_at(monkeypatch, response: httpx.Response, calls: list[httpx.Request]) -> None:
    """Answer every request with one response, recording what was asked."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return response

    real_client = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(dependency_api_client.httpx, "AsyncClient", factory)
    monkeypatch.setattr(settings, "DEPENDENCY_API_MOCK", False)
    monkeypatch.setattr(settings, "DEPENDENCY_API_BASE_URL", "http://dependency.example")
    monkeypatch.setattr(settings, "DEPENDENCY_API_RELEASE_PATH", "/api/v1/appReleaseInfo")


@pytest.fixture
def calls(monkeypatch) -> list[httpx.Request]:
    recorded: list[httpx.Request] = []
    point_at(monkeypatch, httpx.Response(200, json=REPLY), recorded)
    return recorded


async def test_the_client_asks_for_one_application_ref(calls):
    payload = await DependencyApiClient().get_app_release_info("pylang", "1.0.0_10000")

    assert payload == REPLY
    assert len(calls) == 1
    request = calls[0]
    assert request.method == "GET"
    assert request.url.path == "/api/v1/appReleaseInfo"
    assert request.url.params["app_name"] == "pylang"
    # the record names the ref it was asked about, not `ref`
    assert request.url.params["tagOrBranch"] == "1.0.0_10000"


async def test_an_application_without_a_record_reads_as_nothing(monkeypatch):
    calls: list[httpx.Request] = []
    point_at(
        monkeypatch,
        httpx.Response(404, json={"detail": {"error": "dependency_graph_not_found"}}),
        calls,
    )

    assert await DependencyApiClient().get_app_release_info("ghost", "1.0.0") is None


async def test_an_erroring_database_is_reported(monkeypatch):
    calls: list[httpx.Request] = []
    point_at(monkeypatch, httpx.Response(500, json={"detail": "boom"}), calls)

    with pytest.raises(DependencyApiException):
        await DependencyApiClient().get_app_release_info("pylang", "1.0.0")


async def test_an_unconfigured_database_is_reported(monkeypatch):
    monkeypatch.setattr(settings, "DEPENDENCY_API_MOCK", False)
    monkeypatch.setattr(settings, "DEPENDENCY_API_BASE_URL", "")

    with pytest.raises(DependencyApiException):
        await DependencyApiClient().get_app_release_info("pylang", "1.0.0")
