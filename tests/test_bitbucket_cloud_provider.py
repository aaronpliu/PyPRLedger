"""Tests for the Bitbucket Cloud (bitbucket.org) provider.

All HTTP traffic is mocked with httpx.MockTransport - no real API is contacted.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from src.core.exceptions import GitServiceException
from src.schemas.release_diff import ReleaseCompareRequest
from src.services.git_providers import bitbucket_cloud, get_git_provider
from src.services.release_diff_service import ReleaseDiffService


WORKSPACE = "acme"
REPO = "web-app"

C1 = "1111111111111111111111111111111111111111"
C2 = "2222222222222222222222222222222222222222"

COMMITS: dict[str, dict[str, Any]] = {
    C1: {
        "hash": C1,
        "date": "2024-05-01T10:00:00+00:00",
        "message": "feat: add login page",
        "author": {
            "raw": "Jane Doe <jane@example.com>",
            "user": {"display_name": "Jane Doe", "nickname": "jane"},
        },
        "links": {"html": {"href": f"https://bitbucket.org/{WORKSPACE}/{REPO}/commits/{C1}"}},
        "parents": [],
    },
    C2: {
        "hash": C2,
        "date": "2024-05-02T10:00:00+00:00",
        "message": "fix: crash on logout",
        # no email and no display name - the provider falls back to the nickname
        "author": {"raw": "John Roe", "user": {"nickname": "john"}},
        "links": {"html": {"href": f"https://bitbucket.org/{WORKSPACE}/{REPO}/commits/{C2}"}},
        "parents": [{"hash": C1}],
    },
}


def install_transport(monkeypatch, handler) -> None:
    """Route every provider HTTP call through the given handler."""
    real_client = httpx.AsyncClient

    def client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(bitbucket_cloud.httpx, "AsyncClient", client_factory)


def page(values: list[dict[str, Any]], next_url: str | None = None) -> httpx.Response:
    payload: dict[str, Any] = {
        "values": values,
        "pagelen": len(values),
        "page": 1,
        "size": len(values),
    }
    if next_url:
        payload["next"] = next_url
    return httpx.Response(200, json=payload)


def provider() -> bitbucket_cloud.BitbucketCloudProvider:
    return bitbucket_cloud.BitbucketCloudProvider()


def test_get_git_provider_returns_cloud_provider() -> None:
    assert isinstance(get_git_provider("bitbucket_cloud"), bitbucket_cloud.BitbucketCloudProvider)


async def test_compare_commits_uses_include_and_exclude(monkeypatch) -> None:
    requested: list[dict[str, list[str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(parse_qs(urlparse(str(request.url)).query))
        return page([COMMITS[C2]])

    install_transport(monkeypatch, handler)

    commits = await provider().compare_commits(WORKSPACE, REPO, "v1.0.0", "v1.1.0", limit=10)

    assert [commit["id"] for commit in commits] == [C2]
    assert requested[0]["include"] == ["v1.1.0"]
    assert requested[0]["exclude"] == ["v1.0.0"]


async def test_list_commits_until_uses_include(monkeypatch) -> None:
    requested: list[dict[str, list[str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(parse_qs(urlparse(str(request.url)).query))
        return page([COMMITS[C2], COMMITS[C1]])

    install_transport(monkeypatch, handler)

    commits = await provider().list_commits_until(WORKSPACE, REPO, "v1.1.0", limit=10)

    assert [commit["id"] for commit in commits] == [C2, C1]
    assert requested[0]["include"] == ["v1.1.0"]
    assert "exclude" not in requested[0]


async def test_commits_are_normalized_to_the_server_shape(monkeypatch) -> None:
    install_transport(monkeypatch, lambda request: page([COMMITS[C1]]))

    commits = await provider().list_commits_until(WORKSPACE, REPO, "main")

    commit = commits[0]
    assert commit["id"] == C1
    assert commit["author"]["name"] == "Jane Doe"
    assert commit["author"]["emailAddress"] == "jane@example.com"
    assert commit["authorTimestamp"] == 1_714_557_600_000
    assert commit["message"] == "feat: add login page"
    assert commit["url"].endswith(f"/commits/{C1}")


async def test_commits_fall_back_to_the_nickname_when_display_name_is_missing(monkeypatch) -> None:
    install_transport(monkeypatch, lambda request: page([COMMITS[C2]]))

    commits = await provider().list_commits_until(WORKSPACE, REPO, "main")

    assert commits[0]["author"]["name"] == "john"
    assert commits[0]["author"]["emailAddress"] == "john@users.noreply.bitbucket.org"


async def test_list_refs_reads_tags_and_branches(monkeypatch) -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(urlparse(str(request.url)).path)
        if request.url.path.endswith("/tags"):
            return page([{"name": "v1.0.0"}, {"name": "v1.1.0"}])
        return page([{"name": "main"}, {"name": "release/1.0"}])

    install_transport(monkeypatch, handler)

    refs = await provider().list_refs(WORKSPACE, REPO, limit=50)

    assert refs == {"tags": ["v1.0.0", "v1.1.0"], "branches": ["main", "release/1.0"]}
    assert any(path.endswith("/refs/tags") for path in paths)
    assert any(path.endswith("/refs/branches") for path in paths)


async def test_list_commits_follows_pages(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        query = parse_qs(urlparse(str(request.url)).query)
        if query.get("page") == ["1"]:
            return page([COMMITS[C2]], "https://api.bitbucket.org/2.0/next-page")
        return page([COMMITS[C1]])

    install_transport(monkeypatch, handler)

    commits = await provider().list_commits_until(WORKSPACE, REPO, "main", limit=10)

    assert [commit["id"] for commit in commits] == [C2, C1]


async def test_get_project_info_maps_workspace(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "uuid": "{1234-5678}",
                "name": "Acme Inc",
                "slug": WORKSPACE,
                "links": {"html": {"href": f"https://bitbucket.org/{WORKSPACE}/"}},
            },
        )

    install_transport(monkeypatch, handler)

    info = await provider().get_project_info(WORKSPACE)

    assert info is not None
    assert info["project_name"] == "Acme Inc"
    assert info["project_key"] == WORKSPACE
    assert info["project_url"] == f"https://bitbucket.org/{WORKSPACE}/"
    assert isinstance(info["project_id"], int)


async def test_get_repository_info_maps_cloud_repository(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "uuid": "{abcd-efgh}",
                "name": "Web App",
                "slug": REPO,
                "project": {"uuid": "{1234-5678}"},
                "links": {
                    "html": {"href": f"https://bitbucket.org/{WORKSPACE}/{REPO}"},
                    "clone": [
                        {"name": "https", "href": f"https://bitbucket.org/{WORKSPACE}/{REPO}.git"}
                    ],
                },
            },
        )

    install_transport(monkeypatch, handler)

    info = await provider().get_repository_info(WORKSPACE, REPO)

    assert info is not None
    assert info["repository_name"] == "Web App"
    assert info["repository_slug"] == REPO
    assert info["repository_url"].endswith(".git")
    assert isinstance(info["repository_id"], int)


async def test_missing_repository_returns_none(monkeypatch) -> None:
    install_transport(monkeypatch, lambda request: httpx.Response(404, json={"error": {}}))

    assert await provider().get_repository_info(WORKSPACE, REPO) is None


async def test_authentication_failure_raises_git_service_exception(monkeypatch) -> None:
    install_transport(monkeypatch, lambda request: httpx.Response(401, json={"error": {}}))

    with pytest.raises(GitServiceException):
        await provider().list_commits_until(WORKSPACE, REPO, "main")


async def test_release_diff_compare_runs_against_cloud_provider(monkeypatch) -> None:
    """The Cloud provider plugs into the release diff service without changes."""

    # v1.0.0 -> C1, v1.1.0 -> C1 + C2 (same model as the Cloud include/exclude API)
    ref_commits: dict[str, list[str]] = {"v1.0.0": [C1], "v1.1.0": [C1, C2]}

    def handler(request: httpx.Request) -> httpx.Response:
        query = parse_qs(urlparse(str(request.url)).query)
        included = set(ref_commits.get(query.get("include", [""])[0], []))
        excluded = set(ref_commits.get(query.get("exclude", [""])[0], []))
        ids = [sha for sha in (C1, C2) if sha in included and sha not in excluded]
        return page([COMMITS[sha] for sha in ids])

    install_transport(monkeypatch, handler)

    cloud_provider = provider()
    service = ReleaseDiffService(provider_factory=lambda _name: cloud_provider)

    result = await service.compare_releases(
        ReleaseCompareRequest(
            project_key=WORKSPACE,
            repository_slug=REPO,
            git_provider="bitbucket_cloud",
            old_release_ref="v1.0.0",
            new_release_ref="v1.1.0",
        )
    )

    assert result.git_provider == "bitbucket_cloud"
    assert result.status == "included"
    assert [commit.id for commit in result.old_release_commits] == [C1]
    assert [commit.id for commit in result.added_commits] == [C2]
    assert result.old_release_commits[0].author_name == "Jane Doe"


async def test_repository_url_drops_clone_credentials(monkeypatch) -> None:
    """Cloud clone links embed the account name - it must not reach the database."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "uuid": "{aaaa-bbbb}",
                "name": "Web App",
                "slug": REPO,
                "links": {
                    "html": {"href": f"https://bitbucket.org/{WORKSPACE}/{REPO}"},
                    "clone": [
                        {
                            "name": "https",
                            "href": f"https://alice@bitbucket.org/{WORKSPACE}/{REPO}.git",
                        }
                    ],
                },
            },
        )

    install_transport(monkeypatch, handler)

    info = await provider().get_repository_info(WORKSPACE, REPO)

    assert info is not None
    assert info["repository_url"] == f"https://bitbucket.org/{WORKSPACE}/{REPO}.git"


def test_strip_credentials_is_a_noop_without_userinfo() -> None:
    assert (
        bitbucket_cloud.strip_credentials("https://bitbucket.org/acme/web-app.git")
        == "https://bitbucket.org/acme/web-app.git"
    )
    assert bitbucket_cloud.strip_credentials(None) is None
    assert bitbucket_cloud.strip_credentials("") == ""
