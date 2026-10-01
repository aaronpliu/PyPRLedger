"""Tests for the provider primitives behind the release merge check.

Two primitives are exercised per provider:

* ``compare_commits_complete`` - the difference in the missing direction plus a
  completeness flag, so a check can answer "nothing is missing" instead of
  "the page was full, who knows".
* ``contains_commit`` - whether one commit is reachable from a ref, answered by
  the provider in a single call rather than by listing a release.

All HTTP traffic is mocked with httpx.MockTransport - no real API is contacted.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from src.core.config import settings
from src.services.git_providers import bitbucket_cloud, bitbucket_server, github_enterprise


C1 = "1111111111111111111111111111111111111111"
C2 = "2222222222222222222222222222222222222222"

PROJECT = "PROJ"
REPO = "my-repo"
WORKSPACE = "acme"


def install_transport(monkeypatch, module: Any, handler) -> None:
    """Route every provider HTTP call of ``module`` through ``handler``."""
    real_client = httpx.AsyncClient

    def client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", client_factory)


def server_commit(sha: str) -> dict[str, Any]:
    """A Bitbucket Server shaped commit payload."""
    return {
        "id": sha,
        "displayId": sha[:7],
        "author": {"name": "jane", "displayName": "Jane Doe"},
        "authorTimestamp": 1_690_000_000_000,
        "message": "feat: change",
    }


def github_commit(index: int) -> dict[str, Any]:
    """A GitHub shaped commit payload."""
    return {"sha": f"{index:040x}", "commit": {"message": f"feat: change {index}"}}


def server_page(values: list[dict[str, Any]], *, last: bool) -> httpx.Response:
    payload: dict[str, Any] = {"values": values, "size": len(values), "isLastPage": last}
    if not last:
        payload["nextPageStart"] = len(values)
    return httpx.Response(200, json=payload)


# --------------------------------------------------------------------------- #
# Bitbucket Server
# --------------------------------------------------------------------------- #


async def test_server_compare_asks_for_the_difference_in_provider_direction(monkeypatch) -> None:
    """The query must ask for git log from_ref..to_ref, which the API inverts.

    Bitbucket Server streams ``from`` \\ ``to``, so ``from_ref`` has to be sent
    as the ``to`` parameter and ``to_ref`` as the ``from`` parameter.
    """
    seen: list[dict[str, list[str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(parse_qs(urlparse(str(request.url)).query))
        return server_page([], last=True)

    install_transport(monkeypatch, bitbucket_server, handler)
    provider = bitbucket_server.BitbucketServerProvider()

    await provider.compare_commits_complete(PROJECT, REPO, "v1.0.0", "v2.0.0", limit=10)

    assert seen[0]["from"] == ["v2.0.0"]
    assert seen[0]["to"] == ["v1.0.0"]


async def test_server_contains_commit_asks_in_the_containment_direction(monkeypatch) -> None:
    """The difference must be commits(commit) \\ commits(ref), not the other way around."""
    seen: list[dict[str, list[str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(parse_qs(urlparse(str(request.url)).query))
        return server_page([], last=True)

    install_transport(monkeypatch, bitbucket_server, handler)
    provider = bitbucket_server.BitbucketServerProvider()

    assert await provider.contains_commit(PROJECT, REPO, "v1.1.0", C1) is True
    # Bitbucket Server returns from \ to, so the commit goes into "from".
    assert seen[0]["from"] == [C1]
    assert seen[0]["to"] == ["v1.1.0"]


async def test_server_contains_commit_is_false_when_work_is_missing(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return server_page([server_commit(C2)], last=True)

    install_transport(monkeypatch, bitbucket_server, handler)
    provider = bitbucket_server.BitbucketServerProvider()

    assert await provider.contains_commit(PROJECT, REPO, "v1.1.0", C1) is False


async def test_server_contains_commit_short_circuits_a_blank_or_equal_commit(monkeypatch) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return server_page([], last=True)

    install_transport(monkeypatch, bitbucket_server, handler)
    provider = bitbucket_server.BitbucketServerProvider()

    assert await provider.contains_commit(PROJECT, REPO, "v1.1.0", "") is False
    assert await provider.contains_commit(PROJECT, REPO, "v1.1.0", " v1.1.0 ") is True
    assert await provider.contains_commit(PROJECT, REPO, "", C1) is False
    assert calls == []


async def test_server_compare_commits_complete_reports_the_last_page(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return server_page([server_commit(C1)], last=True)

    install_transport(monkeypatch, bitbucket_server, handler)
    provider = bitbucket_server.BitbucketServerProvider()

    commits, complete = await provider.compare_commits_complete(
        PROJECT, REPO, "v1.0.0", "v2.0.0", limit=10
    )

    assert [commit["id"] for commit in commits] == [C1]
    assert complete is True


async def test_server_compare_commits_complete_flags_a_full_page(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return server_page([server_commit(C1)], last=False)

    install_transport(monkeypatch, bitbucket_server, handler)
    provider = bitbucket_server.BitbucketServerProvider()

    commits, complete = await provider.compare_commits_complete(
        PROJECT, REPO, "v1.0.0", "v2.0.0", limit=1
    )

    # the limit was reached, so "nothing missing" cannot be claimed
    assert len(commits) == 1
    assert complete is False


# --------------------------------------------------------------------------- #
# Bitbucket Cloud
# --------------------------------------------------------------------------- #


def cloud_page(values: list[dict[str, Any]]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"values": values, "pagelen": len(values), "page": 1, "size": len(values)},
    )


async def test_cloud_contains_commit_uses_include_for_the_commit(monkeypatch) -> None:
    seen: list[dict[str, list[str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(parse_qs(urlparse(str(request.url)).query))
        return cloud_page([])

    install_transport(monkeypatch, bitbucket_cloud, handler)
    provider = bitbucket_cloud.BitbucketCloudProvider()

    assert await provider.contains_commit(WORKSPACE, REPO, "v1.1.0", C1) is True
    assert seen[0]["include"] == [C1]
    assert seen[0]["exclude"] == ["v1.1.0"]


async def test_cloud_contains_commit_is_false_when_work_is_missing(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return cloud_page(
            [
                {
                    "hash": C2,
                    "date": "2024-05-01T10:00:00+00:00",
                    "message": "fix: crash",
                    "author": {"raw": "Jane Doe <jane@example.com>"},
                    "parents": [],
                }
            ]
        )

    install_transport(monkeypatch, bitbucket_cloud, handler)
    provider = bitbucket_cloud.BitbucketCloudProvider()

    assert await provider.contains_commit(WORKSPACE, REPO, "v1.1.0", C1) is False


# --------------------------------------------------------------------------- #
# GitHub Enterprise
# --------------------------------------------------------------------------- #


@pytest.fixture
def github(monkeypatch) -> github_enterprise.GitHubEnterpriseProvider:
    """A GitHub provider pointed at a mock host."""
    monkeypatch.setattr(settings, "GITHUB_ENTERPRISE_URL", "https://github.local")
    return github_enterprise.GitHubEnterpriseProvider()


async def test_github_contains_commit_uses_ahead_by(monkeypatch, github) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(
            200,
            json={"status": "behind", "ahead_by": 0, "behind_by": 2, "commits": []},
        )

    install_transport(monkeypatch, github_enterprise, handler)

    assert await github.contains_commit(WORKSPACE, REPO, "v1.1.0", C1) is True
    # the ref is the base side: compare/{ref}...{commit}
    assert f"/compare/v1.1.0...{C1}?" in seen[0]


async def test_github_contains_commit_is_false_when_the_commit_adds_work(
    monkeypatch, github
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "ahead", "ahead_by": 3, "behind_by": 0, "commits": [{"sha": C2}]},
        )

    install_transport(monkeypatch, github_enterprise, handler)

    assert await github.contains_commit(WORKSPACE, REPO, "v1.1.0", C1) is False


async def test_github_contains_commit_falls_back_to_the_status(monkeypatch, github) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # older payloads omit the counters, only the status is available
        return httpx.Response(200, json={"status": "identical", "commits": []})

    install_transport(monkeypatch, github_enterprise, handler)

    assert await github.contains_commit(WORKSPACE, REPO, "v1.1.0", C1) is True


async def test_github_contains_commit_is_false_for_an_unknown_commit(monkeypatch, github) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    install_transport(monkeypatch, github_enterprise, handler)

    assert await github.contains_commit(WORKSPACE, REPO, "v1.1.0", C1) is False


async def test_github_compare_commits_complete_reports_when_total_is_reached(
    monkeypatch, github
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"total_commits": 1, "commits": [github_commit(0)]})

    install_transport(monkeypatch, github_enterprise, handler)

    commits, complete = await github.compare_commits_complete(
        WORKSPACE, REPO, "v1.0.0", "v2.0.0", limit=10
    )

    assert len(commits) == 1
    assert complete is True


async def test_github_compare_commits_complete_follows_pages(monkeypatch, github) -> None:
    pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page", "1")
        pages.append(page)
        if page == "1":
            return httpx.Response(
                200,
                json={
                    "total_commits": 101,
                    "commits": [github_commit(index) for index in range(100)],
                },
            )
        return httpx.Response(200, json={"total_commits": 101, "commits": [github_commit(100)]})

    install_transport(monkeypatch, github_enterprise, handler)

    commits, complete = await github.compare_commits_complete(
        WORKSPACE, REPO, "v1.0.0", "v2.0.0", limit=1000
    )

    # a single page would have silently dropped the 101st commit
    assert pages == ["1", "2"]
    assert len(commits) == 101
    assert complete is True


async def test_github_compare_commits_complete_is_incomplete_at_the_limit(
    monkeypatch, github
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"total_commits": 100, "commits": [github_commit(index) for index in range(100)]},
        )

    install_transport(monkeypatch, github_enterprise, handler)

    commits, complete = await github.compare_commits_complete(
        WORKSPACE, REPO, "v1.0.0", "v2.0.0", limit=10
    )

    assert len(commits) == 10
    assert complete is False
