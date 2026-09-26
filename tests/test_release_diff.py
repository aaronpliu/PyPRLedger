"""Tests for release diff compare / check endpoints and service.

All git provider traffic is mocked - no real Bitbucket Server is contacted.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from src.api.v1.endpoints.release_diff import get_release_diff_service
from src.core.database import get_db_session
from src.core.exceptions import GitServiceException
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
from src.schemas.release_diff import (
    ReleaseCommitCheckRequest,
    ReleaseCompareRequest,
    ReleaseRefsRequest,
)
from src.services.git_providers.base import BaseGitProvider
from src.services.release_diff_service import ReleaseDiffService


# --------------------------------------------------------------------------- #
# Mock data
# --------------------------------------------------------------------------- #

BASE_TIMESTAMP = 1_690_000_000_000


def bitbucket_commit(sha: str, message: str, author: str = "Jane Doe") -> dict[str, Any]:
    """Build a Bitbucket Server shaped commit payload."""
    return {
        "id": sha,
        "displayId": sha[:7],
        "author": {"name": author, "emailAddress": f"{author.split()[0].lower()}@example.com"},
        "authorTimestamp": BASE_TIMESTAMP,
        "message": message,
        "parents": [],
    }


C1 = "1111111111111111111111111111111111111111"
C2 = "2222222222222222222222222222222222222222"
C3 = "3333333333333333333333333333333333333333"
C4 = "4444444444444444444444444444444444444444"

COMMITS: dict[str, dict[str, Any]] = {
    C1: bitbucket_commit(C1, "chore: initial import"),
    C2: bitbucket_commit(C2, "feat: add login page"),
    C3: bitbucket_commit(C3, "fix: crash on logout", author="John Roe"),
    C4: bitbucket_commit(C4, "feat: new dashboard"),
}

# Ref -> commits reachable from that ref (oldest first)
REF_COMMITS: dict[str, list[str]] = {
    "v0.9.0": [C1],
    "v1.0.0": [C1, C2, C3],
    "v1.1.0": [C1, C2, C3, C4],
    "v2.0.0": [C1, C2, C4],
}

REF_NAMES: dict[str, list[str]] = {
    "tags": ["v0.9.0", "v1.0.0", "v1.1.0", "v2.0.0"],
    "branches": ["main", "release/1.0"],
}


class FakeGitProvider(BaseGitProvider):
    """In-memory git provider backed by REF_COMMITS."""

    def __init__(self, name: str = "bitbucket_server") -> None:
        self._name = name
        self.calls: list[tuple[str, str, str]] = []

    @property
    def name(self) -> str:
        return self._name

    def _resolve(self, ref: str) -> list[str]:
        if ref in REF_COMMITS:
            return REF_COMMITS[ref]
        if ref in COMMITS:
            return list(REF_COMMITS["v1.1.0"])  # raw sha behaves like the full history
        raise GitServiceException(f"Ref not found: {ref}")

    async def compare_commits(
        self,
        project_key: str,
        repository_slug: str,
        from_ref: str,
        to_ref: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        self.calls.append(("compare", from_ref, to_ref))
        reachable_from = set(self._resolve(from_ref))
        reachable_to = self._resolve(to_ref)
        ids = [sha for sha in reachable_to if sha not in reachable_from]
        return [COMMITS[sha] for sha in ids][:limit]

    async def list_commits_until(
        self,
        project_key: str,
        repository_slug: str,
        until_ref: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        self.calls.append(("list", "", until_ref))
        return [COMMITS[sha] for sha in self._resolve(until_ref)][:limit]

    async def list_refs(
        self,
        project_key: str,
        repository_slug: str,
        limit: int = 100,
    ) -> dict[str, list[str]]:
        self.calls.append(("refs", "", repository_slug))
        return {key: list(value) for key, value in REF_NAMES.items()}

    async def get_project_info(self, project_key: str) -> dict[str, Any] | None:
        return None

    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any] | None:
        return None

    async def get_user_info(self, username: str) -> dict[str, Any] | None:
        return None


def build_service(fake: FakeGitProvider) -> ReleaseDiffService:
    """Build a service wired to the fake provider (no Redis writes)."""
    return ReleaseDiffService(provider_factory=lambda _name: fake)


def compare_payload(**overrides: Any) -> ReleaseCompareRequest:
    payload: dict[str, Any] = {
        "project_key": "PROJ",
        "repository_slug": "my-repo",
        "old_release_ref": "v1.0.0",
        "new_release_ref": "v2.0.0",
    }
    payload.update(overrides)
    return ReleaseCompareRequest(**payload)


def check_payload(**overrides: Any) -> ReleaseCommitCheckRequest:
    payload: dict[str, Any] = {
        "project_key": "PROJ",
        "repository_slug": "my-repo",
        "target_release_ref": "v1.0.0",
        "commits": [C2, C3],
    }
    payload.update(overrides)
    return ReleaseCommitCheckRequest(**payload)


def refs_payload(**overrides: Any) -> ReleaseRefsRequest:
    payload: dict[str, Any] = {
        "project_key": "PROJ",
        "repository_slug": "my-repo",
    }
    payload.update(overrides)
    return ReleaseRefsRequest(**payload)


# --------------------------------------------------------------------------- #
# Service: compare
# --------------------------------------------------------------------------- #


async def test_compare_reports_missing_old_release_commits() -> None:
    fake = FakeGitProvider()
    service = build_service(fake)

    result = await service.compare_releases(compare_payload())

    assert result.old_commits_included is False
    assert result.status == "missing_commits"
    assert [commit.id for commit in result.missing_commits] == [C3]
    assert [commit.id for commit in result.added_commits] == [C4]
    assert result.summary["missing_count"] == 1
    assert result.summary["added_count"] == 1


async def test_compare_reports_full_inclusion() -> None:
    fake = FakeGitProvider()
    service = build_service(fake)

    result = await service.compare_releases(compare_payload(new_release_ref="v1.1.0"))

    assert result.old_commits_included is True
    assert result.status == "included"
    assert result.missing_commits == []
    assert [commit.id for commit in result.added_commits] == [C4]


async def test_compare_identical_refs() -> None:
    fake = FakeGitProvider()
    service = build_service(fake)

    result = await service.compare_releases(compare_payload(new_release_ref="v1.0.0"))

    assert result.status == "identical"
    assert result.old_commits_included is True
    assert result.summary["missing_count"] == 0


async def test_compare_with_release_base_refs_scopes_commit_sets() -> None:
    fake = FakeGitProvider()
    service = build_service(fake)

    result = await service.compare_releases(
        compare_payload(
            old_release_base_ref="v0.9.0",
            new_release_base_ref="v1.0.0",
            new_release_ref="v2.0.0",
        )
    )

    assert [commit.id for commit in result.old_release_commits] == [C2, C3]
    assert [commit.id for commit in result.new_release_commits] == [C4]
    assert [commit.id for commit in result.missing_commits] == [C3]
    assert result.old_commits_included is False


async def test_compare_include_commits_false_returns_counts_only() -> None:
    fake = FakeGitProvider()
    service = build_service(fake)

    result = await service.compare_releases(compare_payload(include_commits=False))

    assert result.missing_commits == []
    assert result.added_commits == []
    assert result.summary["missing_count"] == 1


async def test_compare_normalizes_bitbucket_commit_fields() -> None:
    fake = FakeGitProvider()
    service = build_service(fake)

    result = await service.compare_releases(compare_payload())

    missing = result.missing_commits[0]
    assert missing.id == C3
    assert missing.display_id == C3[:7]
    assert missing.author_name == "John Roe"
    assert missing.author_timestamp == BASE_TIMESTAMP
    assert missing.message == "fix: crash on logout"


async def test_compare_rejects_unknown_provider() -> None:
    service = build_service(FakeGitProvider())

    with pytest.raises(ValueError):
        await service.compare_releases(compare_payload(git_provider="gitlab"))


async def test_compare_propagates_git_service_errors() -> None:
    class FailingProvider(FakeGitProvider):
        async def compare_commits(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
            raise GitServiceException("Bitbucket is unreachable")

    service = build_service(FailingProvider())

    with pytest.raises(GitServiceException):
        await service.compare_releases(compare_payload())


# --------------------------------------------------------------------------- #
# Service: check
# --------------------------------------------------------------------------- #


async def test_check_all_commits_included() -> None:
    fake = FakeGitProvider()
    service = build_service(fake)

    result = await service.check_commits(check_payload())

    assert result.all_included is True
    assert result.summary["included_count"] == 2
    assert result.summary["missing_count"] == 0
    assert [item.matched_id for item in result.results] == [C2, C3]


async def test_check_partial_inclusion() -> None:
    fake = FakeGitProvider()
    service = build_service(fake)

    result = await service.check_commits(
        check_payload(target_release_ref="v2.0.0", commits=[C2, C3, C4])
    )

    assert result.all_included is False
    assert [item.included for item in result.results] == [True, False, True]
    assert result.summary["included_count"] == 2
    assert result.results[1].reason == "not_found_in_release_scope"
    assert result.results[1].commit_info is None


async def test_check_matches_short_sha() -> None:
    fake = FakeGitProvider()
    service = build_service(fake)

    result = await service.check_commits(check_payload(commits=[C2[:7], "  " + C3[:8] + "  "]))

    assert result.all_included is True
    assert [item.matched_id for item in result.results] == [C2, C3]


async def test_check_respects_release_scope() -> None:
    fake = FakeGitProvider()
    service = build_service(fake)

    result = await service.check_commits(
        check_payload(
            target_release_ref="v2.0.0", target_release_base_ref="v1.0.0", commits=[C1, C4]
        )
    )

    assert [item.included for item in result.results] == [False, True]
    assert result.summary["release_commit_count"] == 1


async def test_check_commits_strips_empty_entries() -> None:
    fake = FakeGitProvider()
    service = build_service(fake)

    result = await service.check_commits(check_payload(commits=[C2, "  "]))

    assert result.summary["requested"] == 1
    assert result.all_included is True


# --------------------------------------------------------------------------- #
# Service: refs
# --------------------------------------------------------------------------- #


async def test_list_refs_returns_tags_and_branches() -> None:
    service = build_service(FakeGitProvider())

    result = await service.list_refs(refs_payload())

    assert result.tags == REF_NAMES["tags"]
    assert result.branches == REF_NAMES["branches"]
    assert result.git_provider == "bitbucket_server"


async def test_list_refs_trims_and_deduplicates_names() -> None:
    class MessyProvider(FakeGitProvider):
        async def list_refs(
            self,
            project_key: str,
            repository_slug: str,
            limit: int = 100,
        ) -> dict[str, list[str]]:
            return {"tags": [" v1.0.0 ", "v1.1.0", "v1.0.0", "  "], "branches": []}

    service = build_service(MessyProvider())

    result = await service.list_refs(refs_payload())

    assert result.tags == ["v1.0.0", "v1.1.0"]
    assert result.branches == []


async def test_list_refs_rejects_unknown_provider() -> None:
    service = build_service(FakeGitProvider())

    with pytest.raises(ValueError):
        await service.list_refs(refs_payload(git_provider="gitlab"))


# --------------------------------------------------------------------------- #
# Provider HTTP layer (Bitbucket compare/commits)
# --------------------------------------------------------------------------- #


async def test_bitbucket_provider_compare_commits_paginates(monkeypatch) -> None:
    from src.services.git_providers import bitbucket_server

    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if "start=0" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "values": [COMMITS[C1]],
                    "size": 1,
                    "isLastPage": False,
                    "nextPageStart": 1,
                },
            )
        return httpx.Response(200, json={"values": [COMMITS[C2]], "size": 1, "isLastPage": True})

    real_client = httpx.AsyncClient

    def client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(bitbucket_server.httpx, "AsyncClient", client_factory)

    provider = bitbucket_server.BitbucketServerProvider()
    commits = await provider.compare_commits("PROJ", "my-repo", "v1.0.0", "v2.0.0", limit=10)

    assert [commit["id"] for commit in commits] == [C1, C2]
    assert any("compare/commits" in url for url in requested_urls)
    assert commits[0]["url"].endswith(f"/commits/{C1}")


async def test_bitbucket_provider_lists_tags_and_branches(monkeypatch) -> None:
    from src.services.git_providers import bitbucket_server

    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.path.endswith("/tags"):
            return httpx.Response(
                200, json={"values": [{"displayId": "v1.0.0"}], "size": 1, "isLastPage": True}
            )
        return httpx.Response(
            200, json={"values": [{"displayId": "main"}], "size": 1, "isLastPage": True}
        )

    real_client = httpx.AsyncClient

    def client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(bitbucket_server.httpx, "AsyncClient", client_factory)

    provider = bitbucket_server.BitbucketServerProvider()
    refs = await provider.list_refs("PROJ", "my-repo", limit=50)

    assert refs == {"tags": ["v1.0.0"], "branches": ["main"]}
    assert any("/tags" in url for url in requested_urls)
    assert any("/branches" in url for url in requested_urls)


async def test_bitbucket_provider_raises_on_http_error(monkeypatch) -> None:
    from src.services.git_providers import bitbucket_server

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"errors": []})

    real_client = httpx.AsyncClient

    def client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(bitbucket_server.httpx, "AsyncClient", client_factory)

    provider = bitbucket_server.BitbucketServerProvider()
    with pytest.raises(GitServiceException):
        await provider.compare_commits("PROJ", "my-repo", "v1.0.0", "v2.0.0")


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@pytest.fixture
def fake_provider() -> FakeGitProvider:
    return FakeGitProvider()


@pytest.fixture
def authenticated_client(fake_provider):
    """Test client with auth + release diff service dependencies overridden."""

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_release_diff_service] = lambda: build_service(fake_provider)
    yield
    app.dependency_overrides.pop(get_current_user_with_token, None)
    app.dependency_overrides.pop(get_release_diff_service, None)


async def test_endpoint_compare(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/diff/compare",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "old_release_ref": "v1.0.0",
            "new_release_ref": "v2.0.0",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "missing_commits"
    assert body["old_commits_included"] is False
    assert body["summary"]["missing_count"] == 1
    assert body["missing_commits"][0]["id"] == C3


async def test_endpoint_refs(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/diff/refs",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tags"] == REF_NAMES["tags"]
    assert body["branches"] == REF_NAMES["branches"]
    assert body["git_provider"] == "bitbucket_server"


async def test_endpoint_refs_rejects_limit_above_maximum(
    async_client, authenticated_client
) -> None:
    response = await async_client.post(
        "/api/v1/release/diff/refs",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "limit": 5000,
        },
    )

    assert response.status_code == 422


async def test_endpoint_refs_returns_502_on_git_failure(async_client) -> None:
    class FailingProvider(FakeGitProvider):
        async def list_refs(self, *args: Any, **kwargs: Any) -> dict[str, list[str]]:
            raise GitServiceException("Bitbucket is unreachable")

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_release_diff_service] = lambda: build_service(FailingProvider())
    try:
        response = await async_client.post(
            "/api/v1/release/diff/refs",
            json={
                "project_key": "PROJ",
                "repository_slug": "my-repo",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user_with_token, None)
        app.dependency_overrides.pop(get_release_diff_service, None)

    assert response.status_code == 502


async def test_endpoint_check(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/diff/check",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "target_release_ref": "v2.0.0",
            "commits": [C2, C3],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["all_included"] is False
    assert body["summary"]["included_count"] == 1
    assert body["results"][1]["included"] is False


async def test_endpoint_requires_authentication(async_client) -> None:
    async def _db_session() -> None:
        return None  # 401 is raised before any query runs

    app.dependency_overrides[get_db_session] = _db_session
    try:
        response = await async_client.post(
            "/api/v1/release/diff/compare",
            json={
                "project_key": "PROJ",
                "repository_slug": "my-repo",
                "old_release_ref": "v1.0.0",
                "new_release_ref": "v2.0.0",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 401


async def test_endpoint_rejects_empty_commit_list(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/diff/check",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "target_release_ref": "v1.0.0",
            "commits": [],
        },
    )

    assert response.status_code == 422


async def test_endpoint_returns_bad_request_for_unknown_provider(
    async_client, authenticated_client
) -> None:
    response = await async_client.post(
        "/api/v1/release/diff/compare",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "old_release_ref": "v1.0.0",
            "new_release_ref": "v2.0.0",
            "git_provider": "gitlab",
        },
    )

    assert response.status_code == 400


async def test_endpoint_end_to_end_with_mocked_bitbucket_api(async_client, monkeypatch) -> None:
    """Exercise the full stack against a mocked Bitbucket Server REST API."""
    from urllib.parse import parse_qs, urlparse

    from src.services.git_providers import bitbucket_server

    def handler(request: httpx.Request) -> httpx.Response:
        parsed = urlparse(str(request.url))
        query = parse_qs(parsed.query)

        def page(values: list[dict[str, Any]], start: int) -> httpx.Response:
            return httpx.Response(
                200,
                json={"values": values[start:], "size": len(values[start:]), "isLastPage": True},
            )

        if parsed.path.endswith("/compare/commits"):
            from_ref = query["from"][0]
            to_ref = query["to"][0]
            reachable_from = set(REF_COMMITS[from_ref])
            ids = [sha for sha in REF_COMMITS[to_ref] if sha not in reachable_from]
            return page([COMMITS[sha] for sha in ids], 0)

        if parsed.path.endswith("/commits"):
            until_ref = query["until"][0]
            return page([COMMITS[sha] for sha in REF_COMMITS[until_ref]], 0)

        if parsed.path.endswith("/tags"):
            return page([{"displayId": name} for name in REF_NAMES["tags"]], 0)

        if parsed.path.endswith("/branches"):
            return page([{"displayId": name} for name in REF_NAMES["branches"]], 0)

        return httpx.Response(404, json={"errors": []})

    real_client = httpx.AsyncClient

    def client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(bitbucket_server.httpx, "AsyncClient", client_factory)

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_release_diff_service] = lambda: ReleaseDiffService()
    try:
        compare_response = await async_client.post(
            "/api/v1/release/diff/compare",
            json={
                "project_key": "PROJ",
                "repository_slug": "my-repo",
                "old_release_ref": "v1.0.0",
                "new_release_ref": "v2.0.0",
            },
        )
        check_response = await async_client.post(
            "/api/v1/release/diff/check",
            json={
                "project_key": "PROJ",
                "repository_slug": "my-repo",
                "target_release_ref": "v2.0.0",
                "commits": [C2, C3],
            },
        )
        refs_response = await async_client.post(
            "/api/v1/release/diff/refs",
            json={
                "project_key": "PROJ",
                "repository_slug": "my-repo",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user_with_token, None)
        app.dependency_overrides.pop(get_release_diff_service, None)

    assert compare_response.status_code == 200
    compare_body = compare_response.json()
    assert compare_body["git_provider"] == "bitbucket_server"
    assert compare_body["status"] == "missing_commits"
    assert [commit["id"] for commit in compare_body["missing_commits"]] == [C3]
    assert compare_body["missing_commits"][0]["url"].startswith("http")

    assert check_response.status_code == 200
    check_body = check_response.json()
    assert check_body["all_included"] is False
    assert [item["included"] for item in check_body["results"]] == [True, False]

    assert refs_response.status_code == 200
    refs_body = refs_response.json()
    assert refs_body["tags"] == REF_NAMES["tags"]
    assert refs_body["branches"] == REF_NAMES["branches"]


async def test_endpoint_returns_502_on_git_failure(async_client, fake_provider) -> None:
    class FailingProvider(FakeGitProvider):
        async def list_commits_until(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
            raise GitServiceException("Bitbucket is unreachable")

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_release_diff_service] = lambda: build_service(FailingProvider())
    try:
        response = await async_client.post(
            "/api/v1/release/diff/compare",
            json={
                "project_key": "PROJ",
                "repository_slug": "my-repo",
                "old_release_ref": "v1.0.0",
                "new_release_ref": "v2.0.0",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user_with_token, None)
        app.dependency_overrides.pop(get_release_diff_service, None)

    assert response.status_code == 502


# --------------------------------------------------------------------------- #
# Service: Bitbucket Cloud workspace routing
# --------------------------------------------------------------------------- #


class WorkspaceRecordingProvider(FakeGitProvider):
    """Cloud provider stub recording the identifier used for remote calls."""

    def __init__(self, name: str = "bitbucket_cloud") -> None:
        super().__init__(name=name)
        self.project_keys: list[str] = []

    async def compare_commits(
        self,
        project_key: str,
        repository_slug: str,
        from_ref: str,
        to_ref: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        self.project_keys.append(project_key)
        return await super().compare_commits(project_key, repository_slug, from_ref, to_ref, limit)

    async def list_commits_until(
        self,
        project_key: str,
        repository_slug: str,
        until_ref: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        self.project_keys.append(project_key)
        return await super().list_commits_until(project_key, repository_slug, until_ref, limit)

    async def list_refs(
        self,
        project_key: str,
        repository_slug: str,
        limit: int = 100,
    ) -> dict[str, list[str]]:
        self.project_keys.append(project_key)
        return await super().list_refs(project_key, repository_slug, limit)


async def test_refs_use_cloud_workspace_slug() -> None:
    fake = WorkspaceRecordingProvider()
    service = build_service(fake)

    result = await service.list_refs(
        refs_payload(
            project_key="AI",
            git_provider="bitbucket_cloud",
            workspace_slug="aaronpliu",
        )
    )

    assert fake.project_keys == ["aaronpliu"]
    # The business key is echoed back, the workspace is only used remotely
    assert result.project_key == "AI"


async def test_compare_uses_cloud_workspace_slug() -> None:
    fake = WorkspaceRecordingProvider()
    service = build_service(fake)

    await service.compare_releases(
        compare_payload(
            project_key="AI",
            git_provider="bitbucket_cloud",
            workspace_slug="aaronpliu",
        )
    )

    assert set(fake.project_keys) == {"aaronpliu"}


async def test_check_uses_cloud_workspace_slug() -> None:
    fake = WorkspaceRecordingProvider()
    service = build_service(fake)

    await service.check_commits(
        check_payload(
            project_key="AI",
            git_provider="bitbucket_cloud",
            workspace_slug="aaronpliu",
        )
    )

    assert set(fake.project_keys) == {"aaronpliu"}


async def test_workspace_slug_is_ignored_for_server_and_github() -> None:
    server = WorkspaceRecordingProvider(name="bitbucket_server")
    github = WorkspaceRecordingProvider(name="github_enterprise")

    await build_service(server).list_refs(
        refs_payload(project_key="AI", git_provider="bitbucket_server", workspace_slug="aaronpliu")
    )
    await build_service(github).list_refs(
        refs_payload(
            project_key="acme", git_provider="github_enterprise", workspace_slug="aaronpliu"
        )
    )

    assert server.project_keys == ["AI"]
    assert github.project_keys == ["acme"]


async def test_cloud_without_workspace_slug_falls_back_to_project_key() -> None:
    fake = WorkspaceRecordingProvider()

    await build_service(fake).list_refs(
        refs_payload(project_key="aaronpliu", git_provider="bitbucket_cloud")
    )

    assert fake.project_keys == ["aaronpliu"]


# --------------------------------------------------------------------------- #
# Refs caching / explicit refresh
# --------------------------------------------------------------------------- #


async def test_refresh_bypasses_the_cache_and_picks_up_new_tags() -> None:
    """A tag created on the git side must show up after an explicit refresh."""
    fake = FakeGitProvider()
    service = build_service(fake)

    # 1. first call fills the cache
    first = await service.list_refs(refs_payload())
    assert "v9.9.9" not in first.tags

    # 2. the git side gets a new tag ...
    REF_NAMES["tags"].append("v9.9.9")
    try:
        cached = await service.list_refs(refs_payload())
        assert "v9.9.9" not in cached.tags, "cached response is expected to be stale"

        # 3. ... and an explicit refresh reads through to the provider
        refreshed = await service.list_refs(refs_payload(refresh=True))
        assert "v9.9.9" in refreshed.tags

        # 4. the cache now holds the fresh list for the automatic loads
        after = await service.list_refs(refs_payload())
        assert "v9.9.9" in after.tags
    finally:
        REF_NAMES["tags"].remove("v9.9.9")


async def test_cache_hit_avoids_the_provider_call() -> None:
    fake = FakeGitProvider()
    service = build_service(fake)

    await service.list_refs(refs_payload())
    calls_after_first = len(fake.calls)
    await service.list_refs(refs_payload())

    assert len(fake.calls) == calls_after_first
