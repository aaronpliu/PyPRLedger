"""Tests for release diff compare / check endpoints and service.

All git provider traffic is mocked - no real Bitbucket Server is contacted.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from src.api.v1.endpoints.release_diff import (
    get_baseline_service,
    get_rbac_service,
    get_release_diff_service,
)
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
from src.services.release_check_baseline_service import ReleaseCheckBaselineService
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

# Ancestry of a raw commit (a ref may point at a merge, a commit may not).
SHA_ANCESTORS: dict[str, list[str]] = {
    C1: [C1],
    C2: [C1, C2],
    C3: [C1, C2, C3],
    C4: [C1, C2, C4],
}


def reachable(ref: str) -> list[str]:
    """Commits reachable from a named ref or a raw commit SHA (oldest first)."""
    if ref in REF_COMMITS:
        return REF_COMMITS[ref]
    if ref in SHA_ANCESTORS:
        return SHA_ANCESTORS[ref]
    raise GitServiceException(f"Ref not found: {ref}")


class FakeGitProvider(BaseGitProvider):
    """In-memory git provider backed by REF_COMMITS."""

    def __init__(self, name: str = "bitbucket_server") -> None:
        self._name = name
        self.calls: list[tuple[str, str, str]] = []

    @property
    def name(self) -> str:
        return self._name

    def _resolve(self, ref: str) -> list[str]:
        return reachable(ref)

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


class StubCache:
    """Cache stub serving a fixed payload, standing in for Redis."""

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload
        self.writes: list[tuple[str, dict[str, Any]]] = []

    async def get_json(self, key: str) -> dict[str, Any] | None:
        return self.payload

    async def set_json(self, key: str, value: dict[str, Any], expire: int | None = None) -> bool:
        self.writes.append((key, value))
        self.payload = value
        return True


def compare_payload(**overrides: Any) -> ReleaseCompareRequest:
    payload: dict[str, Any] = {
        "project_key": "PROJ",
        "repository_slug": "my-repo",
        "source_ref": "v1.0.0",
        "target_ref": "v2.0.0",
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
# Service: compare (verdict + missing + added in one call)
# --------------------------------------------------------------------------- #


async def test_compare_reports_the_missing_and_added_commits() -> None:
    service = build_service(FakeGitProvider())

    result = await service.compare_releases(compare_payload())

    assert result.verdict == "missing"
    assert [commit.id for commit in result.missing_commits] == [C3]
    assert [commit.id for commit in result.added_commits] == [C4]
    assert result.missing_count == 1
    assert result.added_count == 1
    assert result.scan_complete is True
    assert result.added_complete is True
    assert result.narrowed is False
    assert result.baseline_ref is None


async def test_compare_reports_full_inclusion() -> None:
    service = build_service(FakeGitProvider())

    result = await service.compare_releases(compare_payload(target_ref="v1.1.0"))

    assert result.verdict == "contained"
    assert result.missing_commits == []
    assert result.missing_count == 0
    assert [commit.id for commit in result.added_commits] == [C4]


async def test_compare_identical_refs_are_contained() -> None:
    service = build_service(FakeGitProvider())

    result = await service.compare_releases(compare_payload(target_ref="v1.0.0"))

    assert result.verdict == "contained"
    assert result.missing_count == 0
    assert result.added_count == 0
    assert result.scan_complete is True


async def test_compare_does_not_report_shared_history() -> None:
    """Only work that never reached the other line is a difference."""
    service = build_service(FakeGitProvider())

    result = await service.compare_releases(
        compare_payload(source_ref="v1.1.0", target_ref="v2.0.0")
    )

    assert [commit.id for commit in result.missing_commits] == [C3]
    assert result.missing_count == 1
    # C4 exists on both lines, so it is neither missing nor added
    assert result.added_count == 0


async def test_compare_narrows_both_directions_by_the_baseline() -> None:
    """A baseline drops difference commits that already existed at the starting point."""
    service = build_service(FakeGitProvider())

    result = await service.compare_releases(
        compare_payload(source_ref="v1.1.0", target_ref="v2.0.0", baseline_ref="v1.0.0")
    )

    # C3 was already there at the baseline, so it no longer counts as missing
    assert result.verdict == "contained"
    assert result.narrowed is True
    assert result.baseline_ref == "v1.0.0"
    assert result.baseline_stored is False
    assert result.filtered_by_baseline_count == 1


async def test_compare_uses_the_stored_baseline_when_none_is_given() -> None:
    service = build_service(FakeGitProvider())

    result = await service.compare_releases(
        compare_payload(source_ref="v1.1.0", target_ref="v2.0.0"),
        baseline_ref="v1.0.0",
    )

    assert result.verdict == "contained"
    assert result.baseline_ref == "v1.0.0"
    assert result.baseline_stored is True
    assert result.narrowed is True


async def test_compare_ignores_the_stored_baseline_when_told_to() -> None:
    service = build_service(FakeGitProvider())

    result = await service.compare_releases(
        compare_payload(source_ref="v1.1.0", target_ref="v2.0.0", use_stored_baseline=False),
        baseline_ref="v1.0.0",
    )

    assert result.verdict == "missing"
    assert result.baseline_ref is None
    assert result.baseline_stored is False
    assert result.narrowed is False


async def test_compare_is_inconclusive_when_the_scan_is_capped() -> None:
    """A capped scan must never be reported as a pass."""
    service = build_service(FakeGitProvider())

    result = await service.compare_releases(compare_payload(scan_limit=1))

    assert result.verdict == "inconclusive"
    assert result.scan_complete is False
    assert result.scan_limit == 1
    # the count is honest about being a lower bound
    assert result.missing_count == 1


async def test_compare_verdict_does_not_depend_on_a_release_listing() -> None:
    """Regression: a capped / empty release listing used to hide a missing commit."""

    class CappedListingProvider(FakeGitProvider):
        async def list_commits_until(
            self,
            project_key: str,
            repository_slug: str,
            until_ref: str,
            limit: int = 1000,
        ) -> list[dict[str, Any]]:
            return []

    service = build_service(CappedListingProvider())

    result = await service.compare_releases(compare_payload())

    assert result.verdict == "missing"
    assert [commit.id for commit in result.missing_commits] == [C3]


async def test_compare_marks_rendered_details_as_truncated_without_touching_counts() -> None:
    """Two added commits, render_limit=1: the count stays complete, the list does not."""

    class TwoAddedProvider(FakeGitProvider):
        async def compare_commits(
            self,
            project_key: str,
            repository_slug: str,
            from_ref: str,
            to_ref: str,
            limit: int = 1000,
        ) -> list[dict[str, Any]]:
            if from_ref == "v1.0.0" and to_ref == "v2.0.0":
                return [COMMITS[C3], COMMITS[C4]][:limit]
            return await super().compare_commits(
                project_key, repository_slug, from_ref, to_ref, limit
            )

    service = build_service(TwoAddedProvider())

    result = await service.compare_releases(compare_payload(render_limit=1))

    assert result.added_count == 2
    assert len(result.added_commits) == 1
    assert result.rendered_truncated is True


async def test_compare_include_commits_false_returns_counts_only() -> None:
    service = build_service(FakeGitProvider())

    result = await service.compare_releases(compare_payload(include_commits=False))

    assert result.missing_commits == []
    assert result.added_commits == []
    assert result.missing_count == 1
    assert result.added_count == 1


def test_normalize_commit_extracts_the_bitbucket_author_account() -> None:
    """Server keeps the account slug in ``name`` and the human name in ``displayName``."""
    info = ReleaseDiffService._normalize_commit(
        {
            "id": C1,
            "displayId": C1[:7],
            "author": {"name": "aaronpliu", "displayName": "Aaron Liu"},
            "message": "feat: add login page",
        }
    )

    assert info.author_name == "Aaron Liu"
    assert info.author_username == "aaronpliu"
    # the profile URL is not part of the payload: the provider builds it
    assert info.author_url is None


def test_normalize_commit_does_not_mistake_a_display_name_for_an_account() -> None:
    info = ReleaseDiffService._normalize_commit(bitbucket_commit(C1, "chore: initial import"))

    assert info.author_name == "Jane Doe"
    assert info.author_username is None


def test_normalize_commit_extracts_the_github_author_account() -> None:
    info = ReleaseDiffService._normalize_commit(
        {
            "sha": C1,
            "commit": {"message": "feat: add login page", "author": {"name": "Aaron Liu"}},
            "author": {"login": "aaronpliu", "html_url": "https://github.local/aaronpliu"},
            "html_url": f"https://github.local/commits/{C1[:7]}",
        }
    )

    assert info.author_name == "Aaron Liu"
    assert info.author_username == "aaronpliu"
    assert info.author_url == "https://github.local/aaronpliu"


def test_normalize_commit_survives_a_github_commit_without_a_linked_account() -> None:
    info = ReleaseDiffService._normalize_commit(
        {
            "sha": C1,
            "commit": {"message": "feat: add login page", "author": {"name": "Jane Doe"}},
            "author": None,
        }
    )

    assert info.author_name == "Jane Doe"
    assert info.author_username is None
    assert info.author_url is None


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
    assert result.verdict == "missing"
    assert result.results[1].reason == "not_reachable_from_target"
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


class StubRBAC:
    """RBAC stub: grants everything unless a test says otherwise."""

    def __init__(self) -> None:
        self.allowed = True
        self.checks: list[dict[str, Any]] = []

    async def check_permission(self, **kwargs: Any) -> bool:
        self.checks.append(kwargs)
        return self.allowed


class StubBaselineService:
    """Baseline store stub: no stored baseline unless a test says otherwise."""

    def __init__(self, baseline_ref: str | None = None) -> None:
        self.baseline_ref = baseline_ref

    async def get_ref(self, **kwargs: Any) -> str | None:
        return self.baseline_ref


@pytest.fixture
def authenticated_client(fake_provider, db_session):
    """Test client with auth, the diff service and the baseline store overridden."""

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    async def _db_session() -> Any:
        yield db_session

    rbac = StubRBAC()
    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    app.dependency_overrides[get_release_diff_service] = lambda: build_service(fake_provider)
    app.dependency_overrides[get_baseline_service] = lambda: ReleaseCheckBaselineService(db_session)
    app.dependency_overrides[get_rbac_service] = lambda: rbac
    yield rbac
    for dependency in (
        get_current_user_with_token,
        get_db_session,
        get_release_diff_service,
        get_baseline_service,
        get_rbac_service,
    ):
        app.dependency_overrides.pop(dependency, None)


async def test_endpoint_compare(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/diff/compare",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "source_ref": "v1.0.0",
            "target_ref": "v2.0.0",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "missing"
    assert body["missing_count"] == 1
    assert body["added_count"] == 1
    assert body["missing_commits"][0]["id"] == C3
    assert body["added_commits"][0]["id"] == C4
    assert body["scan_complete"] is True
    assert body["baseline_ref"] is None


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
                "source_ref": "v1.0.0",
                "target_ref": "v2.0.0",
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
            "source_ref": "v1.0.0",
            "target_ref": "v2.0.0",
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
            # Bitbucket Server streams the commits reachable from "from" that are
            # not reachable from "to" (git log to..from).
            from_ref = query["from"][0]
            to_ref = query["to"][0]
            reachable_to = set(reachable(to_ref))
            ids = [sha for sha in reachable(from_ref) if sha not in reachable_to]
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
    app.dependency_overrides[get_baseline_service] = lambda: StubBaselineService()
    try:
        compare_response = await async_client.post(
            "/api/v1/release/diff/compare",
            json={
                "project_key": "PROJ",
                "repository_slug": "my-repo",
                "source_ref": "v1.0.0",
                "target_ref": "v2.0.0",
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
    assert compare_body["verdict"] == "missing"
    assert compare_body["missing_count"] == 1
    assert [commit["id"] for commit in compare_body["missing_commits"]] == [C3]
    assert compare_body["missing_commits"][0]["url"].startswith("http")
    # The newer release adds its own work; it must not be reported as missing it.
    assert compare_body["added_count"] == 1
    assert [commit["id"] for commit in compare_body["added_commits"]] == [C4]

    assert check_response.status_code == 200
    check_body = check_response.json()
    assert check_body["all_included"] is False
    assert [item["included"] for item in check_body["results"]] == [True, False]

    assert refs_response.status_code == 200
    refs_body = refs_response.json()
    assert refs_body["tags"] == REF_NAMES["tags"]
    assert refs_body["branches"] == REF_NAMES["branches"]


# --------------------------------------------------------------------------- #
# Service: the per-build merge check (missing)
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Service: the verdict no longer depends on a capped listing
# --------------------------------------------------------------------------- #


async def test_check_reports_a_contained_commit_beyond_the_release_listing() -> None:
    """Regression: a capped listing used to turn a contained commit into a miss."""

    class CappedListingProvider(FakeGitProvider):
        async def list_commits_until(
            self,
            project_key: str,
            repository_slug: str,
            until_ref: str,
            limit: int = 1000,
        ) -> list[dict[str, Any]]:
            return []

    service = build_service(CappedListingProvider())

    result = await service.check_commits(
        check_payload(target_release_ref="v2.0.0", commits=[C1, C3])
    )

    assert [item.included for item in result.results] == [True, False]
    assert result.results[0].reason == "matched"
    assert result.results[0].matched_id is None  # no details without a listing
    assert result.results[1].reason == "not_reachable_from_target"
    assert result.verdict == "missing"


async def test_check_excludes_commits_before_the_release_base() -> None:
    service = build_service(FakeGitProvider())

    result = await service.check_commits(
        check_payload(
            target_release_ref="v2.0.0", target_release_base_ref="v1.0.0", commits=[C2, C4]
        )
    )

    assert [item.included for item in result.results] == [False, True]
    assert result.results[0].reason == "excluded_by_release_base"


# --------------------------------------------------------------------------- #
# Service: stored baselines
# --------------------------------------------------------------------------- #


async def test_baseline_service_upserts_and_normalizes_the_project_key(db_session) -> None:
    service = ReleaseCheckBaselineService(db_session)

    saved = await service.save(
        git_provider="bitbucket_server",
        project_key="proj",
        repository_slug="my-repo",
        baseline_ref="v1.0.0",
        note="fork point of the 1.x line",
        updated_by="tester",
    )

    assert saved.project_key == "PROJ"
    assert saved.note == "fork point of the 1.x line"
    assert (
        await service.get_ref(
            git_provider="bitbucket_server", project_key="PROJ", repository_slug="my-repo"
        )
        == "v1.0.0"
    )
    # a different casing addresses the same baseline
    assert (
        await service.get_ref(
            git_provider="bitbucket_server", project_key="proj", repository_slug="my-repo"
        )
        == "v1.0.0"
    )

    await service.save(
        git_provider="bitbucket_server",
        project_key="PROJ",
        repository_slug="my-repo",
        baseline_ref="v1.2.0",
        updated_by="tester",
    )

    assert (
        await service.get_ref(
            git_provider="bitbucket_server", project_key="PROJ", repository_slug="my-repo"
        )
        == "v1.2.0"
    )

    assert (
        await service.clear(
            git_provider="bitbucket_server", project_key="PROJ", repository_slug="my-repo"
        )
        is True
    )
    assert (
        await service.get_ref(
            git_provider="bitbucket_server", project_key="PROJ", repository_slug="my-repo"
        )
        is None
    )
    assert (
        await service.clear(
            git_provider="bitbucket_server", project_key="PROJ", repository_slug="my-repo"
        )
        is False
    )


# --------------------------------------------------------------------------- #
# Endpoints: missing check and baseline
# --------------------------------------------------------------------------- #


async def test_endpoint_baseline_round_trip(async_client, authenticated_client) -> None:
    saved = await async_client.put(
        "/api/v1/release/diff/baseline",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "baseline_ref": "  v1.0.0  ",
            "note": "fork point of the 1.x line",
        },
    )

    assert saved.status_code == 200
    saved_body = saved.json()
    assert saved_body["baseline_ref"] == "v1.0.0"
    assert saved_body["exists"] is True
    assert saved_body["updated_by"] == "tester"

    fetched = await async_client.get(
        "/api/v1/release/diff/baseline",
        params={"project_key": "proj", "repository_slug": "my-repo"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["project_key"] == "PROJ"
    assert fetched.json()["baseline_ref"] == "v1.0.0"

    cleared = await async_client.delete(
        "/api/v1/release/diff/baseline",
        params={"project_key": "PROJ", "repository_slug": "my-repo"},
    )
    assert cleared.status_code == 200
    assert cleared.json()["exists"] is False

    after = await async_client.get(
        "/api/v1/release/diff/baseline",
        params={"project_key": "PROJ", "repository_slug": "my-repo"},
    )
    assert after.json()["exists"] is False
    assert after.json()["baseline_ref"] is None


async def test_endpoint_baseline_write_requires_the_manage_permission(
    async_client, authenticated_client
) -> None:
    rbac: StubRBAC = authenticated_client
    rbac.allowed = False

    denied = await async_client.put(
        "/api/v1/release/diff/baseline",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "baseline_ref": "v1.0.0",
        },
    )

    assert denied.status_code == 403
    assert rbac.checks and rbac.checks[0]["action"] == "manage"

    # reading a baseline stays open to any authenticated user
    allowed_read = await async_client.get(
        "/api/v1/release/diff/baseline",
        params={"project_key": "PROJ", "repository_slug": "my-repo"},
    )
    assert allowed_read.status_code == 200


async def test_endpoint_returns_502_on_git_failure(async_client, fake_provider) -> None:
    class FailingProvider(FakeGitProvider):
        async def compare_commits(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
            raise GitServiceException("Bitbucket is unreachable")

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_release_diff_service] = lambda: build_service(FailingProvider())
    app.dependency_overrides[get_baseline_service] = lambda: StubBaselineService()
    try:
        response = await async_client.post(
            "/api/v1/release/diff/compare",
            json={
                "project_key": "PROJ",
                "repository_slug": "my-repo",
                "source_ref": "v1.0.0",
                "target_ref": "v2.0.0",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user_with_token, None)
        app.dependency_overrides.pop(get_release_diff_service, None)
        app.dependency_overrides.pop(get_baseline_service, None)

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


async def test_cached_refs_are_cleaned_of_repeated_entries() -> None:
    """A payload written by an older revision must not render duplicate refs."""
    service = ReleaseDiffService(
        provider_factory=lambda _name: FakeGitProvider(),
        cache=StubCache(
            {
                "project_key": "PROJ",
                "repository_slug": "my-repo",
                "git_provider": "bitbucket_server",
                "tags": ["v0.1.0", "v0.1.0", "v0.2.0"],
                "branches": ["main", "main"],
            }
        ),
    )

    refs = await service.list_refs(refs_payload())

    assert refs.tags == ["v0.1.0", "v0.2.0"]
    assert refs.branches == ["main"]


# --------------------------------------------------------------------------- #
# Request validation and the removed second endpoint
# --------------------------------------------------------------------------- #


def test_scan_and_render_limits_are_validated() -> None:
    with pytest.raises(ValueError):
        compare_payload(scan_limit=0)
    with pytest.raises(ValueError):
        compare_payload(scan_limit=10001)
    with pytest.raises(ValueError):
        compare_payload(render_limit=0)
    with pytest.raises(ValueError):
        compare_payload(render_limit=2001)
    with pytest.raises(ValueError):
        compare_payload(source_ref="   ")


async def test_endpoint_missing_route_is_gone(async_client, authenticated_client) -> None:
    """The two tools were folded into one comparison: the old route must not exist."""
    response = await async_client.post(
        "/api/v1/release/diff/missing",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "source_ref": "v1.0.0",
            "target_ref": "v1.1.0",
        },
    )

    assert response.status_code == 404
