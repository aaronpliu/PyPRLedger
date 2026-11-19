"""Tests for the aggregate release note service.

The note one release deserves when the application pins packages: the app's
own comparison, one entry per pinned package the span moved, and the legibility
rule - a package that cannot be compared says why, it never hides and never
guessed.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.schemas.aggregate_release_note import AggregateReleaseNoteRequest
from src.schemas.release_diff import ReleaseCompareResponse
from src.services.aggregate_release_note_service import AggregateReleaseNoteService


PROJECT_KEY = "PROJ"
REPO_SLUG = "myapp"
APP_NAME = "MyApp"


def graph(ref: str, packages: list[dict[str, Any]]) -> dict[str, Any]:
    """A dependency graph payload the way DependencyGraphService.build answers.

    Categories are the graph service's integers: 0 app, 1 external, 2 workspace.
    """
    return {
        "app_name": APP_NAME,
        "project_key": PROJECT_KEY,
        "repository_slug": REPO_SLUG,
        "git_provider": "bitbucket_server",
        "packages": [{"id": APP_NAME, "category": 0, "version": ref, "dependencies": {}}, *packages],
    }


# MyApp v1.0.0 pins pkgA 1.2.0, pkgB 1.0.0 and pkgY 0.9.0 (pkgB and pkgY are
# unregistered); v2.0.0 upgrades pkgA and pkgY, adds pkgX, drops pkgB, and
# drags the external pkgC along
GRAPH_V1 = graph(
    "v1.0.0",
    [
        {"id": "pkgA", "category": 2, "version": "1.2.0", "dependencies": {}},
        {"id": "pkgB", "category": 2, "version": "1.0.0", "dependencies": {}},
        {"id": "pkgY", "category": 2, "version": "0.9.0", "dependencies": {}},
        {"id": "pkgC", "category": 1, "version": "3.1.0", "dependencies": {}},
        {"id": "pkgD", "category": 1, "version": "2.0.0", "dependencies": {}},
    ],
)
GRAPH_V2 = graph(
    "v2.0.0",
    [
        {"id": "pkgA", "category": 2, "version": "1.4.0", "dependencies": {}},
        {"id": "pkgX", "category": 2, "version": "0.1.0", "dependencies": {}},
        {"id": "pkgY", "category": 2, "version": "1.0.0", "dependencies": {}},
        {"id": "pkgC", "category": 1, "version": "3.2.0", "dependencies": {}},
        {"id": "pkgD", "category": 1, "version": "2.0.0", "dependencies": {}},
    ],
)


class StubGraph:
    """Answers the two refs with the two fixture graphs."""

    async def build(self, *, app_name: str, project_key: str, repository_slug: str, ref: str, **_: Any):
        return GRAPH_V1 if ref == "v1.0.0" else GRAPH_V2


class FakeRegistration:
    """What find_dependency_repository answers with when the name settles."""

    project_key = "PROJA"
    repository_slug = "pkgA-repo"
    git_provider = None


class StubRegistry:
    """pkgA resolves to its own repository; pkgX is not registered anywhere."""

    async def find_dependency_repository(self, name: str, preferred_project_key: str | None, db):
        if name == "pkgA":
            return FakeRegistration(), None
        return None, f"no repository is registered as '{name}'"

    async def get_dependency_app_name(self, project_key: str, repository_slug: str, db) -> str:
        return APP_NAME


class StubDiff:
    """Records the comparisons it is asked for and answers a contained verdict."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, str, str]] = []

    async def compare_releases(self, request):
        self.asked.append((request.project_key, request.source_ref, request.target_ref))
        return ReleaseCompareResponse(
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            git_provider=request.git_provider or "bitbucket_server",
            source_ref=request.source_ref,
            target_ref=request.target_ref,
            verdict="contained",
            added_commits=[{"id": f"c-{request.repository_slug}-{request.target_ref}"}],
            missing_commits=[],
        )


def make_request(**overrides) -> AggregateReleaseNoteRequest:
    return AggregateReleaseNoteRequest(
        project_key=PROJECT_KEY,
        repository_slug=REPO_SLUG,
        app_name=APP_NAME,
        source_ref="v1.0.0",
        target_ref="v2.0.0",
        **overrides,
    )


@pytest.mark.asyncio
async def test_classifies_the_packages_the_span_moved() -> None:
    diff = StubDiff()
    service = AggregateReleaseNoteService(
        graph=StubGraph(), diff=diff, registry=StubRegistry()
    )
    note = await service.build(make_request(), db=None)

    moved = {(entry.name, entry.change, entry.from_version, entry.to_version) for entry in note.packages}
    assert moved == {
        ("pkgA", "upgraded", "1.2.0", "1.4.0"),
        ("pkgY", "upgraded", "0.9.0", "1.0.0"),
        ("pkgX", "added", "", "0.1.0"),
        ("pkgB", "removed", "1.0.0", ""),
        ("pkgC", "upgraded", "3.1.0", "3.2.0"),
    }


@pytest.mark.asyncio
async def test_scope_is_the_application_pins_only() -> None:
    # pkgC moved too (3.1.0 -> 3.2.0) but MyApp never pins it: it stays in the
    # note as a skipped entry so the closure change is legible, while only the
    # pinned packages earn a commit comparison
    diff = StubDiff()
    service = AggregateReleaseNoteService(
        graph=StubGraph(), diff=diff, registry=StubRegistry()
    )
    note = await service.build(make_request(), db=None)

    pkgc = next(entry for entry in note.packages if entry.name == "pkgC")
    assert pkgc.status == "skipped"
    assert "does not pin" in (pkgc.reason or "")
    assert "pkgD@2.0.0" in note.unchanged_packages


@pytest.mark.asyncio
async def test_unregistered_package_is_skipped_with_the_reason() -> None:
    service = AggregateReleaseNoteService(
        graph=StubGraph(), diff=StubDiff(), registry=StubRegistry()
    )
    note = await service.build(make_request(), db=None)

    # pkgY upgraded but registered nowhere: the note says why it cannot compare
    pkgy = next(entry for entry in note.packages if entry.name == "pkgY")
    assert pkgy.status == "skipped"
    assert "no repository is registered as 'pkgY'" in (pkgy.reason or "")
    assert pkgy.comparison is None


@pytest.mark.asyncio
async def test_added_package_skips_with_where_it_came_from() -> None:
    # an added package has no earlier version to compare against, so the skip
    # reason names that instead of walking a comparison that cannot exist
    service = AggregateReleaseNoteService(
        graph=StubGraph(), diff=StubDiff(), registry=StubRegistry()
    )
    note = await service.build(make_request(), db=None)

    pkgx = next(entry for entry in note.packages if entry.name == "pkgX")
    assert pkgx.status == "skipped"
    assert "was not part of v1.0.0" in (pkgx.reason or "")
    assert pkgx.comparison is None


@pytest.mark.asyncio
async def test_registered_package_is_compared_between_its_versions() -> None:
    diff = StubDiff()
    service = AggregateReleaseNoteService(
        graph=StubGraph(), diff=diff, registry=StubRegistry()
    )
    note = await service.build(make_request(), db=None)

    pkga = next(entry for entry in note.packages if entry.name == "pkgA")
    assert pkga.status == "compared"
    assert pkga.comparison is not None
    assert pkga.comparison.verdict == "contained"
    # the comparison runs between the package's own versions, in its own repo
    assert ("PROJA", "1.2.0", "1.4.0") in diff.asked


@pytest.mark.asyncio
async def test_application_section_compares_the_app_repository() -> None:
    diff = StubDiff()
    service = AggregateReleaseNoteService(
        graph=StubGraph(), diff=diff, registry=StubRegistry()
    )
    note = await service.build(make_request(), db=None)

    assert (PROJECT_KEY, "v1.0.0", "v2.0.0") in diff.asked
    assert note.application.verdict == "contained"
    assert note.summary.app_commits == 1


@pytest.mark.asyncio
async def test_summary_counts_reflect_what_happened() -> None:
    service = AggregateReleaseNoteService(
        graph=StubGraph(), diff=StubDiff(), registry=StubRegistry()
    )
    note = await service.build(make_request(), db=None)

    assert note.summary.packages_changed == 5
    assert note.summary.packages_compared == 1  # only pkgA is pinned and registered
    assert note.summary.packages_skipped == 4  # pkgY unregistered, pkgX added, pkgB removed, pkgC unpinned
    assert note.summary.packages_failed == 0


@pytest.mark.asyncio
async def test_removed_package_never_runs_a_comparison() -> None:
    diff = StubDiff()
    service = AggregateReleaseNoteService(
        graph=StubGraph(), diff=diff, registry=StubRegistry()
    )
    note = await service.build(make_request(), db=None)

    pkgb = next(entry for entry in note.packages if entry.name == "pkgB")
    # nothing to compare against - the package is gone from the target ref
    assert pkgb.status == "skipped"
    assert "no longer part of v2.0.0" in (pkgb.reason or "")
    assert all(source != "1.0.0" for _, source, _ in diff.asked)
