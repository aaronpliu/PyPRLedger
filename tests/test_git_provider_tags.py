"""Tests for the provider primitive behind the release note scope.

``list_tags_with_commits`` resolves a repository's tags to the commit each one
points at, which is what lets a release scope be computed on the server instead
of guessed from a page-sized list of tag names.

All HTTP traffic is mocked with httpx.MockTransport - no real API is contacted.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

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


def server_page(values: list[dict[str, Any]], *, last: bool) -> httpx.Response:
    payload: dict[str, Any] = {"values": values, "size": len(values), "isLastPage": last}
    if not last:
        payload["nextPageStart"] = len(values)
    return httpx.Response(200, json=payload)


def github_provider(monkeypatch) -> github_enterprise.GitHubEnterpriseProvider:
    """A GitHub provider pointed at a mock host."""
    monkeypatch.setattr(settings, "GITHUB_ENTERPRISE_URL", "https://github.local")
    return github_enterprise.GitHubEnterpriseProvider()


def cloud_page(values: list[dict[str, Any]], *, next_url: str | None = None) -> httpx.Response:
    payload: dict[str, Any] = {"values": values, "pagelen": len(values), "size": len(values)}
    if next_url:
        payload["next"] = next_url
    else:
        payload["page"] = 1
    return httpx.Response(200, json=payload)


# --------------------------------------------------------------------------- #
# Bitbucket Server
# --------------------------------------------------------------------------- #


async def test_server_tags_carry_the_commit_and_the_tag_type(monkeypatch) -> None:
    """``latestCommit`` is the revision, ``type`` says how the tag was made."""
    values = [
        {
            "id": "refs/tags/v1.0.0",
            "displayId": "v1.0.0",
            "type": "ANNOTATED",
            "latestCommit": C1,
            "latestCommitTimestamp": 1_690_000_000_000,
        },
        {
            "id": "refs/tags/v1.1.0",
            "displayId": "v1.1.0",
            "type": "LIGHTWEIGHT",
            "latestCommit": C2,
            "latestCommitTimestamp": 1_700_000_000_000,
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return server_page(values, last=True)

    install_transport(monkeypatch, bitbucket_server, handler)
    provider = bitbucket_server.BitbucketServerProvider()

    tags = await provider.list_tags_with_commits(PROJECT, REPO, limit=10)

    assert [(tag["name"], tag["sha"]) for tag in tags] == [
        ("v1.0.0", C1),
        ("v1.1.0", C2),
    ]
    assert tags[0]["is_annotated"] is True
    assert tags[1]["is_annotated"] is False
    assert tags[0]["date"] == 1_690_000_000_000


async def test_server_tags_page_through_until_the_limit(monkeypatch) -> None:
    """A repository with more tags than one page must not lose the older ones."""
    starts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = parse_qs(urlparse(str(request.url)).query)
        starts.append(params["start"][0])
        index = int(params["start"][0])
        return server_page(
            [
                {
                    "displayId": f"v1.{index}.0",
                    "type": "LIGHTWEIGHT",
                    "latestCommit": C1,
                }
            ],
            last=index >= 1,
        )

    install_transport(monkeypatch, bitbucket_server, handler)
    provider = bitbucket_server.BitbucketServerProvider()

    tags = await provider.list_tags_with_commits(PROJECT, REPO, limit=10)

    assert [tag["name"] for tag in tags] == ["v1.0.0", "v1.1.0"]
    assert starts == ["0", "1"]


async def test_server_tags_do_not_depend_on_a_server_side_ordering(monkeypatch) -> None:
    """No ``orderBy`` is sent - the caller orders the entries itself."""
    seen: list[dict[str, list[str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(parse_qs(urlparse(str(request.url)).query))
        return server_page([], last=True)

    install_transport(monkeypatch, bitbucket_server, handler)
    provider = bitbucket_server.BitbucketServerProvider()

    await provider.list_tags_with_commits(PROJECT, REPO, limit=10)

    assert "orderBy" not in seen[0]


async def test_server_tags_survive_a_missing_date_and_drop_blank_or_repeated_names(
    monkeypatch,
) -> None:
    """A tag without a timestamp is still usable; anonymous or repeated tags are not."""
    values = [
        {"displayId": "v1.0.0", "type": "LIGHTWEIGHT", "latestCommit": C1},
        {"displayId": "  ", "latestCommit": C2},
        {"displayId": "v1.0.0", "latestCommit": C2},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return server_page(values, last=True)

    install_transport(monkeypatch, bitbucket_server, handler)
    provider = bitbucket_server.BitbucketServerProvider()

    tags = await provider.list_tags_with_commits(PROJECT, REPO, limit=10)

    assert tags == [
        {"name": "v1.0.0", "sha": C1, "date": None, "is_annotated": False},
    ]


# --------------------------------------------------------------------------- #
# Bitbucket Cloud
# --------------------------------------------------------------------------- #


async def test_cloud_tags_use_the_target_commit(monkeypatch) -> None:
    """Cloud reports the commit (and its date) under ``target``."""
    values = [
        {
            "name": "v2.0.0",
            "target": {"hash": C1, "date": "2024-05-01T10:00:00+00:00", "type": "commit"},
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return cloud_page(values)

    install_transport(monkeypatch, bitbucket_cloud, handler)
    provider = bitbucket_cloud.BitbucketCloudProvider()

    tags = await provider.list_tags_with_commits(WORKSPACE, REPO, limit=10)

    assert tags[0]["name"] == "v2.0.0"
    assert tags[0]["sha"] == C1
    assert tags[0]["date"] == 1714557600000
    assert tags[0]["is_annotated"] is False


async def test_cloud_annotated_tag_is_dereferenced_to_its_commit(monkeypatch) -> None:
    """An annotated tag points at a tag object - the commit is one level deeper."""
    values = [
        {
            "name": "v2.1.0",
            "target": {
                "hash": C2,
                "type": "tag",
                "target": {"hash": C1, "date": "2024-05-02T10:00:00+00:00", "type": "commit"},
            },
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return cloud_page(values)

    install_transport(monkeypatch, bitbucket_cloud, handler)
    provider = bitbucket_cloud.BitbucketCloudProvider()

    tags = await provider.list_tags_with_commits(WORKSPACE, REPO, limit=10)

    assert tags[0]["sha"] == C1
    assert tags[0]["is_annotated"] is True
    assert tags[0]["date"] == 1714644000000


async def test_cloud_tags_page_through_and_drop_duplicates(monkeypatch) -> None:
    """Cloud paginates through ``next``; a repeated name is offered once."""
    next_url = f"https://api.bitbucket.org/2.0/repositories/{WORKSPACE}/{REPO}/refs/tags?page=2"
    pages = [
        cloud_page(
            [{"name": "v1.0.0", "target": {"hash": C1, "type": "commit"}}], next_url=next_url
        ),
        cloud_page(
            [
                {"name": "v1.0.0", "target": {"hash": C1, "type": "commit"}},
                {"name": "v1.1.0", "target": {"hash": C2, "type": "commit"}},
            ]
        ),
    ]
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        response = pages[min(calls["count"], len(pages) - 1)]
        calls["count"] += 1
        return response

    install_transport(monkeypatch, bitbucket_cloud, handler)
    provider = bitbucket_cloud.BitbucketCloudProvider()

    tags = await provider.list_tags_with_commits(WORKSPACE, REPO, limit=10)

    assert [tag["name"] for tag in tags] == ["v1.0.0", "v1.1.0"]
    assert calls["count"] == 2


# --------------------------------------------------------------------------- #
# GitHub Enterprise
# --------------------------------------------------------------------------- #


async def test_github_tags_use_the_commit_the_tag_points_to(monkeypatch) -> None:
    """GitHub resolves annotated tags in the tag listing itself."""
    values = [
        {"name": "v3.0.0", "commit": {"sha": C1}},
        {"name": "v3.1.0", "commit": {"sha": C2}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=values)

    install_transport(monkeypatch, github_enterprise, handler)
    provider = github_provider(monkeypatch)

    tags = await provider.list_tags_with_commits("acme", REPO, limit=10)

    assert [(tag["name"], tag["sha"]) for tag in tags] == [
        ("v3.0.0", C1),
        ("v3.1.0", C2),
    ]


async def test_github_tags_report_what_the_listing_does_not_know(monkeypatch) -> None:
    """No date and no tag type in the payload - they stay unknown, not guessed."""
    values = [{"name": "v3.2.0", "commit": {"sha": C1}}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=values)

    install_transport(monkeypatch, github_enterprise, handler)
    provider = github_provider(monkeypatch)

    tags = await provider.list_tags_with_commits("acme", REPO, limit=10)

    assert tags[0]["date"] is None
    assert tags[0]["is_annotated"] is None


async def test_github_tags_page_through_until_the_limit(monkeypatch) -> None:
    """GitHub caps a page at 100 tags, so the listing has to follow the pages."""
    pages_requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = parse_qs(urlparse(str(request.url)).query)
        page = params["page"][0]
        pages_requested.append(page)
        if page == "1":
            return httpx.Response(
                200,
                json=[{"name": f"v1.{index}.0", "commit": {"sha": C1}} for index in range(100)],
            )
        return httpx.Response(200, json=[{"name": "v1.100.0", "commit": {"sha": C2}}])

    install_transport(monkeypatch, github_enterprise, handler)
    provider = github_provider(monkeypatch)

    tags = await provider.list_tags_with_commits("acme", REPO, limit=101)

    assert len(tags) == 101
    assert tags[-1]["name"] == "v1.100.0"
    assert pages_requested == ["1", "2"]
