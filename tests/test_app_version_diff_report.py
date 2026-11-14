"""Tests for the CI-facing App Diff report endpoint and its HTML renderer.

The dependency source is answered from the canned data of the client, so no
third-party service is contacted. The renderer tests feed the response shape
directly, one hostile string included.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.api.v1.endpoints.app_version_diff import (
    get_app_version_diff_service,
    get_registry_service,
)
from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token, get_repository_access
from src.main import app
from src.models.auth_user import AuthUser
from src.schemas.app_version_diff import AppVersionDiffResponse
from src.schemas.release_diff import ReleaseCompareRequest, ReleaseCompareResponse
from src.services.app_diff_report import render_app_diff_report
from src.services.app_version_diff_service import AppVersionDiffService
from src.services.dependency_graph_service import DependencyGraphService
from src.services.dependency_mock_data import MOCK_APP_NAME, MOCK_BRANCH, MOCK_TAG
from src.services.project_registry_service import ProjectRegistryService


class FakeCache:
    def __init__(self) -> None:
        self.stored: dict[str, Any] = {}

    async def get_json(self, key: str) -> Any:
        return self.stored.get(key)

    async def set_json(self, key: str, value: Any, expire: int | None = None) -> None:
        self.stored[key] = value


class FakeRegistry(ProjectRegistryService):
    async def get_app_name(self, project_key: str, repository_slug: str, db: Any) -> str:
        return MOCK_APP_NAME

    async def get_dependency_app_name(
        self, project_key: str, repository_slug: str, db: Any
    ) -> str:
        return MOCK_APP_NAME


class FakeDiff:
    async def compare_releases(self, request: ReleaseCompareRequest) -> ReleaseCompareResponse:
        return ReleaseCompareResponse(
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            git_provider="bitbucket_server",
            source_ref=request.source_ref,
            target_ref=request.target_ref,
            verdict="contained",
            scan_complete=True,
            added_count=4,
        )


@pytest.fixture
def authenticated_client(db_session):
    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    async def _db_session() -> Any:
        yield db_session

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    app.dependency_overrides[get_registry_service] = lambda: FakeRegistry()
    app.dependency_overrides[get_repository_access] = lambda: {("CORE", "app")}
    app.dependency_overrides[get_app_version_diff_service] = lambda: AppVersionDiffService(
        cache=FakeCache(),
        graph_service=DependencyGraphService(cache=FakeCache()),
        diff_service=FakeDiff(),
    )
    yield
    for dependency in (
        get_current_user_with_token,
        get_db_session,
        get_registry_service,
        get_app_version_diff_service,
    ):
        app.dependency_overrides.pop(dependency, None)


def payload(*refs: str, **extra: Any) -> dict[str, Any]:
    return {
        "project_key": "CORE",
        "repository_slug": "app",
        "git_provider": "bitbucket_server",
        "refs": list(refs),
        **extra,
    }


async def test_report_endpoint_returns_html(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/apps/diff/report", json=payload(MOCK_TAG, MOCK_BRANCH)
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    assert MOCK_APP_NAME in html
    assert MOCK_TAG in html and MOCK_BRANCH in html
    # the version matrix carries the application row
    assert "Version Matrix" in html
    # every pair gets its own section; the heading spells the refs with an arrow entity
    assert f"{MOCK_TAG} &rarr; {MOCK_BRANCH}" in html


async def test_report_endpoint_download_header(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/apps/diff/report",
        params={"download": "true"},
        json=payload(MOCK_TAG, MOCK_BRANCH),
    )

    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment; filename=\"app-diff-CORE-app-")
    assert disposition.endswith(".html\"")


async def test_report_endpoint_json_format(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/apps/diff/report",
        params={"format": "json"},
        json=payload(MOCK_TAG, MOCK_BRANCH),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_key"] == "CORE"
    assert [release["ref"] for release in body["releases"]] == [MOCK_TAG, MOCK_BRANCH]


async def test_report_endpoint_requires_granted_pair(async_client, authenticated_client) -> None:
    app.dependency_overrides[get_repository_access] = lambda: {("OTHER", "other")}
    response = await async_client.post(
        "/api/v1/release/apps/diff/report", json=payload(MOCK_TAG, MOCK_BRANCH)
    )
    assert response.status_code == 403


def test_renderer_escapes_hostile_values() -> None:
    result = AppVersionDiffResponse(
        project_key="CORE",
        repository_slug="app",
        app_name="<script>alert(1)</script>",
        git_provider="bitbucket_server",
        verdict="changed",
        summary={},
        releases=[{"ref": "v1.0.0", "released_at": None, "has_record": True}],
        rows=[
            {
                "kind": "application",
                "name": "<img src=x onerror=alert(2)>",
                "versions": ["1.0.0"],
                "moves": [None],
            }
        ],
        intervals=[],
        package_comparisons={"per_pair": 1, "page_total": 1, "batch": 1, "remaining": 0},
    )

    html = render_app_diff_report(result)
    assert "<script>alert" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html


def test_renderer_highlights_missing_commits() -> None:
    result = AppVersionDiffResponse(
        project_key="CORE",
        repository_slug="app",
        app_name="App",
        git_provider="bitbucket_server",
        verdict="changed",
        summary={},
        releases=[
            {"ref": "v1.0.0", "released_at": None, "has_record": True},
            {"ref": "v1.1.0", "released_at": None, "has_record": True},
        ],
        rows=[],
        intervals=[
            {
                "source_ref": "v1.0.0",
                "target_ref": "v1.1.0",
                "complete": True,
                "summary": {},
                "dependencies_moved": True,
                "changes": [],
                "packages": [],
                "code": {
                    "verdict": "missing",
                    "scan_complete": True,
                    "added_count": 0,
                    "missing_count": 1,
                    "added_commits": [],
                    "missing_commits": [
                        {
                            "id": "abc123",
                            "display_id": "abc123",
                            "author_name": "Bob",
                            "author_username": None,
                            "author_email": None,
                            "author_timestamp": None,
                            "message": "Fix the parser",
                            "url": None,
                        }
                    ],
                    "truncated": False,
                    "unavailable": None,
                    "deferred": False,
                },
            }
        ],
        package_comparisons={"per_pair": 1, "page_total": 1, "batch": 1, "remaining": 0},
    )

    html = render_app_diff_report(result)
    # the not-contained commit is painted as a defect: red row, red heading
    assert "commit-tr missing" in html
    assert "Not contained (1)" in html
    assert "Fix the parser" in html
