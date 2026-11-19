"""Tests for the aggregate release note service.

The note one release deserves when the application carries packages: the app's
own comparison, one entry per package the span moved, and the legibility rule -
a package that cannot be compared says why, it never hides and never guesses.

The packages come from the project registry and their versions from their own
tag timelines, so every stub answers with real-shaped data: registrations the
registry page could have written, and tag entries the providers return.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.schemas.aggregate_release_note import AggregateReleaseNoteRequest
from src.schemas.release_diff import ReleaseCompareResponse
from src.services.aggregate_release_note_service import AggregateReleaseNoteService


PROJECT_KEY = "PROJ"
REPO_SLUG = "myapp"
APP_NAME = "MyApp"


def epoch_ms(*args: int) -> int:
    """A tag date the way the providers report them: epoch milliseconds."""
    return int(datetime(*args, tzinfo=UTC).timestamp() * 1000)


# The app shipped v1.0.0 on Jan 1 and v2.0.0 on Feb 1; a package version is
# "part of" the release whose span it was released inside.
APP_TAGS = [
    {"name": "v1.0.0", "sha": "s1", "date": epoch_ms(2026, 1, 1), "is_annotated": False},
    {"name": "v2.0.0", "sha": "s2", "date": epoch_ms(2026, 2, 1), "is_annotated": False},
]

# pkgA released 1.2.0 before the span and 1.4.0 inside it: an upgrade the span carried
PKG_A_TAGS = [
    {"name": "1.2.0", "sha": "a1", "date": epoch_ms(2025, 12, 20), "is_annotated": False},
    {"name": "1.4.0", "sha": "a2", "date": epoch_ms(2026, 1, 15), "is_annotated": False},
]

# pkgB released nothing inside the span: it held at 2.0.0
PKG_B_TAGS = [
    {"name": "2.0.0", "sha": "b1", "date": epoch_ms(2025, 12, 20), "is_annotated": False},
]

# pkgX's first release landed inside the span: the span added it
PKG_X_TAGS = [
    {"name": "0.5.0", "sha": "x1", "date": epoch_ms(2026, 1, 10), "is_annotated": False},
]


class Registration:
    """One row of the project registry, the way the page writes it."""

    def __init__(
        self,
        project_key: str,
        repository_slug: str,
        alias: str | None = None,
        kind: str | None = None,
        git_provider: str | None = "bitbucket_server",
    ) -> None:
        # a package is registered under the application it belongs to; the name
        # the outside world knows it by is the alias when there is one
        self.app_name = APP_NAME
        self.app_alias = alias
        self.registry_kind = kind
        self.project_key = project_key
        self.repository_slug = repository_slug
        self.git_provider = git_provider


class StubRegistry:
    """MyApp carries pkgA, pkgB, pkgX and pkgY; it also owns a second repository."""

    def __init__(self, registrations: list[Registration] | None = None) -> None:
        self.registrations = registrations or [
            Registration("PROJ", "myapp", kind="application"),
            Registration("PROJA", "pkgA-repo", alias="pkgA", kind="package"),
            Registration("PROJB", "pkgB", kind="package"),
            Registration("PROJX", "pkgX-repo", alias="pkgX", kind="package"),
            Registration("PROJY", "pkgY-repo", alias="pkgY", kind="package"),
            # another repository of the same application, nobody classified it:
            # it is the app, not something the app carries
            Registration("PROJ", "myapp-other"),
        ]

    async def get_dependency_app_name(self, project_key: str, repository_slug: str, db) -> str:
        return APP_NAME

    async def list_projects_by_app(self, app_name: str | None, db):
        return list(self.registrations)


class StubProvider:
    """Answers tag listings per repository; ``undated`` and ``broken`` are its moods."""

    def __init__(self, tags: dict[str, list[dict[str, Any]]], broken: set[str] | None = None) -> None:
        self.tags = tags
        self.broken = broken or set()

    async def list_tags_with_commits(self, remote_key: str, repository_slug: str):
        if repository_slug in self.broken:
            raise RuntimeError("provider down")
        return self.tags.get(repository_slug, [])


class StubDiff:
    """Records the comparisons it is asked for and answers a contained verdict."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, str, str]] = []
        self.addressed: list[tuple[str, str | None]] = []

    async def compare_releases(self, request):
        self.asked.append((request.project_key, request.source_ref, request.target_ref))
        # a Cloud repository is addressed by its workspace, never by its
        # project key - recording it keeps that rule under test
        self.addressed.append((request.project_key, request.workspace_slug))
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


def make_service(
    diff: StubDiff | None = None,
    registry: StubRegistry | None = None,
    provider: StubProvider | None = None,
) -> AggregateReleaseNoteService:
    return AggregateReleaseNoteService(
        diff=diff or StubDiff(),
        registry=registry or StubRegistry(),
        provider_factory=lambda name: provider
        or StubProvider(
            {
                "myapp": APP_TAGS,
                "pkgA-repo": PKG_A_TAGS,
                "pkgB": PKG_B_TAGS,
                "pkgX-repo": PKG_X_TAGS,
            },
            broken={"pkgY-repo"},
        ),
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
async def test_places_each_package_on_the_span_timeline() -> None:
    diff = StubDiff()
    service = make_service(diff=diff)
    note = await service.build(make_request(), db=None)

    moved = {(entry.name, entry.change, entry.from_version, entry.to_version) for entry in note.packages}
    assert moved == {
        # 1.2.0 was out before v1.0.0 shipped, 1.4.0 landed inside the span
        ("pkgA", "upgraded", "1.2.0", "1.4.0"),
        # 0.5.0 is pkgX's first release and it landed inside the span
        ("pkgX", "added", "", "0.5.0"),
        # the tag listing failed: the note says so instead of guessing
        ("pkgY", "upgraded", "", ""),
    }
    # pkgB released nothing inside the span: the unchanged line carries it
    assert note.unchanged_packages == ["pkgB@2.0.0"]
    assert all(entry.name != "pkgB" for entry in note.packages)


@pytest.mark.asyncio
async def test_application_repositories_are_not_packages() -> None:
    service = make_service()
    note = await service.build(make_request(), db=None)

    # the app's own second repository and the application registration itself
    # share the grouping; neither is something the application carries
    names = {entry.name for entry in note.packages}
    assert "myapp-other" not in names
    assert APP_NAME not in names


@pytest.mark.asyncio
async def test_added_package_skips_with_where_it_came_from() -> None:
    service = make_service()
    note = await service.build(make_request(), db=None)

    pkgx = next(entry for entry in note.packages if entry.name == "pkgX")
    assert pkgx.status == "skipped"
    assert "was not part of v1.0.0" in (pkgx.reason or "")
    assert pkgx.comparison is None


@pytest.mark.asyncio
async def test_tag_read_failure_is_the_package_status() -> None:
    provider = StubProvider(
        {"myapp": APP_TAGS, "pkgA-repo": PKG_A_TAGS, "pkgB": PKG_B_TAGS, "pkgX-repo": PKG_X_TAGS},
        broken={"pkgY-repo"},
    )
    service = make_service(provider=provider)
    note = await service.build(make_request(), db=None)

    pkgy = next(entry for entry in note.packages if entry.name == "pkgY")
    assert pkgy.status == "failed"
    assert "could not be read" in (pkgy.reason or "")
    assert pkgy.comparison is None


@pytest.mark.asyncio
async def test_moved_package_is_compared_between_its_versions() -> None:
    diff = StubDiff()
    service = make_service(diff=diff)
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
    service = make_service(diff=diff)
    note = await service.build(make_request(), db=None)

    assert (PROJECT_KEY, "v1.0.0", "v2.0.0") in diff.asked
    assert note.application.verdict == "contained"
    assert note.summary.app_commits == 1


@pytest.mark.asyncio
async def test_summary_counts_reflect_what_happened() -> None:
    service = make_service()
    note = await service.build(make_request(), db=None)

    assert note.summary.packages_changed == 3  # pkgA, pkgX, pkgY
    assert note.summary.packages_compared == 1  # only pkgA moved with two versions to compare
    assert note.summary.packages_skipped == 1  # pkgX added
    assert note.summary.packages_failed == 1  # pkgY unreadable
    assert note.summary.package_commits == 1


@pytest.mark.asyncio
async def test_undated_span_leaves_every_package_legible() -> None:
    # a span end that is not a dated tag cannot place any package version, and
    # the note says so per package instead of pretending the span has no calendar
    provider = StubProvider(
        {
            "myapp": [{"name": "v1.0.0", "sha": "s1", "date": None, "is_annotated": False}],
            "pkgA-repo": PKG_A_TAGS,
            "pkgB": PKG_B_TAGS,
            "pkgX-repo": PKG_X_TAGS,
        }
    )
    service = make_service(provider=provider)
    note = await service.build(make_request(), db=None)

    assert note.packages
    assert all(entry.status == "skipped" for entry in note.packages)
    assert all("cannot be timed" in (entry.reason or "") for entry in note.packages)


@pytest.mark.asyncio
async def test_cloud_workspace_addresses_every_comparison() -> None:
    diff = StubDiff()
    service = make_service(diff=diff)
    note = await service.build(make_request(workspace_slug="aaronpliu"), db=None)

    # the application and every package it carries are asked for in the
    # workspace the request was filled with - a project key is not a workspace
    assert ("PROJ", "aaronpliu") in diff.addressed
    assert ("PROJA", "aaronpliu") in diff.addressed
    assert all(workspace == "aaronpliu" for _, workspace in diff.addressed)


@pytest.mark.asyncio
async def test_no_registered_package_says_so() -> None:
    registry = StubRegistry(
        registrations=[
            Registration("PROJ", "myapp", kind="application"),
            Registration("PROJ", "myapp-other"),
        ]
    )
    service = make_service(registry=registry)
    note = await service.build(make_request(), db=None)

    assert len(note.packages) == 1
    assert note.packages[0].status == "skipped"
    assert "no package is registered under 'MyApp'" in (note.packages[0].reason or "")
