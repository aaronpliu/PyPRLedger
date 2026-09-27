"""Tests for the GitHub Enterprise release API support.

All HTTP traffic is mocked with httpx.MockTransport - no real GitHub is contacted.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from src.core.config import settings
from src.core.exceptions import GitServiceException
from src.services.git_providers import (
    bitbucket_cloud,
    bitbucket_server,
    get_git_provider,
    github_enterprise,
)


OWNER = "acme"
REPO = "pyledger"

RELEASE_PAYLOAD: dict[str, Any] = {
    "id": 991,
    "tag_name": "v1.2.0",
    "name": "v1.2.0",
    "body": "## What's Changed",
    "draft": False,
    "prerelease": True,
    "html_url": f"https://github.local/{OWNER}/{REPO}/releases/tag/v1.2.0",
    "published_at": "2026-09-01T10:00:00Z",
    "created_at": "2026-09-01T09:00:00Z",
    "author": {"login": "octocat"},
}


def install_transport(monkeypatch, handler) -> None:
    """Route every provider HTTP call through the given handler."""
    real_client = httpx.AsyncClient

    def client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(github_enterprise.httpx, "AsyncClient", client_factory)


@pytest.fixture
def provider(monkeypatch) -> github_enterprise.GitHubEnterpriseProvider:
    monkeypatch.setattr(settings, "GITHUB_ENTERPRISE_URL", "https://github.local")
    monkeypatch.setattr(settings, "GITHUB_ENTERPRISE_TOKEN", "test-token")
    return github_enterprise.GitHubEnterpriseProvider()


def test_only_github_supports_releases() -> None:
    assert get_git_provider("github_enterprise").supports_releases is True
    assert get_git_provider("bitbucket_server").supports_releases is False
    assert get_git_provider("bitbucket_cloud").supports_releases is False


async def test_unsupported_providers_raise_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await bitbucket_server.BitbucketServerProvider().list_releases("PROJ", "repo")
    with pytest.raises(NotImplementedError):
        await bitbucket_cloud.BitbucketCloudProvider().create_release(
            "ws", "repo", tag_name="v1.0.0", name="v1.0.0"
        )


async def test_list_releases_normalizes_the_payload(monkeypatch, provider) -> None:
    requested: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        return httpx.Response(200, json=[RELEASE_PAYLOAD])

    install_transport(monkeypatch, handler)

    releases = await provider.list_releases(OWNER, REPO, limit=10)

    assert str(requested[0].url).startswith(
        f"https://github.local/api/v3/repos/{OWNER}/{REPO}/releases"
    )
    assert releases == [
        {
            "id": "991",
            "tag_name": "v1.2.0",
            "name": "v1.2.0",
            "body": "## What's Changed",
            "draft": False,
            "prerelease": True,
            "html_url": f"https://github.local/{OWNER}/{REPO}/releases/tag/v1.2.0",
            "published_at": "2026-09-01T10:00:00Z",
            "created_at": "2026-09-01T09:00:00Z",
            "author": "octocat",
        }
    ]


async def test_create_release_posts_the_release(monkeypatch, provider) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(201, json=RELEASE_PAYLOAD)

    install_transport(monkeypatch, handler)

    release = await provider.create_release(
        OWNER,
        REPO,
        tag_name="v1.2.0",
        name="Release v1.2.0",
        body="notes",
        target_commitish="release/1.2",
        prerelease=True,
    )

    assert captured["method"] == "POST"
    assert captured["url"] == f"https://github.local/api/v3/repos/{OWNER}/{REPO}/releases"
    assert captured["body"] == {
        "tag_name": "v1.2.0",
        "name": "Release v1.2.0",
        "body": "notes",
        "draft": False,
        "prerelease": True,
        "target_commitish": "release/1.2",
    }
    assert release["id"] == "991"
    assert release["html_url"].endswith("/releases/tag/v1.2.0")


async def test_create_release_omits_the_target_branch_when_not_given(monkeypatch, provider) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(201, json=RELEASE_PAYLOAD)

    install_transport(monkeypatch, handler)

    await provider.create_release(OWNER, REPO, tag_name="v1.2.0", name="v1.2.0")

    assert "target_commitish" not in captured["body"]


async def test_update_release_patches_only_the_given_fields(monkeypatch, provider) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=RELEASE_PAYLOAD)

    install_transport(monkeypatch, handler)

    await provider.update_release(OWNER, REPO, "991", name="New title", prerelease=False)

    assert captured["method"] == "PATCH"
    assert captured["url"].endswith(f"/repos/{OWNER}/{REPO}/releases/991")
    assert captured["body"] == {"name": "New title", "prerelease": False}


async def test_provider_errors_carry_the_response_message(monkeypatch, provider) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422, json={"message": "Validation Failed", "errors": [{"code": "already_exists"}]}
        )

    install_transport(monkeypatch, handler)

    with pytest.raises(GitServiceException) as excinfo:
        await provider.create_release(OWNER, REPO, tag_name="v1.2.0", name="v1.2.0")

    assert "422" in str(excinfo.value)
    assert "already_exists" in str(excinfo.value)
