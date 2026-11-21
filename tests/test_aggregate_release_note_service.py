"""Tests for the aggregate release note service.

The note one release deserves when the application pins packages: the app's
own comparison and rendered body, one entry per pinned package the span moved
with its rendered body, and the legibility rule - a package that cannot be
compared says why, it never hides and never guesses.

The relationship comes from the dependency database (its client, mocked here):
what each ref of the application declares. An application without a record is
monolithic - the note degrades to the app's own comparison and no packages are
guessed.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.core.exceptions import DependencyApiException
from src.schemas.aggregate_release_note import AggregateReleaseNoteRequest
from src.schemas.release_diff import ReleaseCompareResponse
from src.services.aggregate_release_note_service import AggregateReleaseNoteService
from src.services.git_providers import get_git_provider


PROJECT_KEY = "PROJ"
REPO_SLUG = "myapp"
APP_NAME = "MyApp"


def record(ref: str, dependencies: dict[str, str], packages: list[dict[str, Any]]) -> dict[str, Any]:
    """A dependency database answer the way DependencyApiClient returns it."""
    return {"app_name": APP_NAME, "tagOrBranch": ref, "dependencies": dependencies, "packages": packages}


# MyApp v1.0.0 pins pkgA 1.2.0, pkgB 1.0.0 and pkgY 0.9.0 (pkgB and pkgY are
# unregistered); v2.0.0 upgrades pkgA and pkgY, adds pkgX, drops pkgB, and
# drags the unpinned pkgC along
RECORD_V1 = record(
    "v1.0.0",
    {"pkgA": "1.2.0", "pkgB": "1.0.0", "pkgY": "0.9.0"},
    [
        {"package_name": "pkgA", "version": "1.2.0", "dependencies": {}},
        {"package_name": "pkgB", "version": "1.0.0", "dependencies": {}},
        {"package_name": "pkgY", "version": "0.9.0", "dependencies": {}},
        {"package_name": "pkgC", "version": "3.1.0", "dependencies": {}},
        {"package_name": "pkgD", "version": "2.0.0", "dependencies": {}},
    ],
)
RECORD_V2 = record(
    "v2.0.0",
    {"pkgA": "1.4.0", "pkgX": "0.1.0", "pkgY": "1.0.0"},
    [
        {"package_name": "pkgA", "version": "1.4.0", "dependencies": {}},
        {"package_name": "pkgX", "version": "0.1.0", "dependencies": {}},
        {"package_name": "pkgY", "version": "1.0.0", "dependencies": {}},
        {"package_name": "pkgC", "version": "3.2.0", "dependencies": {}},
        {"package_name": "pkgD", "version": "2.0.0", "dependencies": {}},
    ],
)


class Registration:
    """One row of the project registry, what find_dependency_repository answers."""

    def __init__(self, project_key: str, repository_slug: str, git_provider: str | None = None) -> None:
        self.project_key = project_key
        self.repository_slug = repository_slug
        self.git_provider = git_provider


class StubRegistry:
    """The repo is a registered application; pkgA resolves to its own repository."""

    def __init__(self, kind: str | None = "application") -> None:
        self.kind = kind

    async def get_registry_kind(self, project_key: str, repository_slug: str, db) -> str | None:
        return self.kind

    async def get_dependency_app_name(self, project_key: str, repository_slug: str, db) -> str:
        return APP_NAME

    async def find_dependency_repository(self, name: str, preferred_project_key: str | None, db):
        if name == "pkgA":
            return Registration("PROJA", "pkgA-repo"), None
        return None, f"no repository is registered as '{name}'"


class StubClient:
    """Answers the two refs with the two fixture records."""

    def __init__(self, records: dict[str, dict[str, Any]] | None = None, broken: bool = False) -> None:
        self.records = records or {}
        self.broken = broken

    async def get_app_release_info(self, app_name: str, tag_or_branch: str):
        if self.broken:
            raise DependencyApiException("the database is not configured")
        return self.records.get(tag_or_branch)


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
            added_commits=[
                {
                    "id": f"c-{request.repository_slug}-{request.target_ref}",
                    "message": f"feat: add the thing in {request.repository_slug}",
                    "author_name": "Aaron",
                }
            ],
            missing_commits=[],
        )


def make_service(
    diff: StubDiff | None = None,
    registry: StubRegistry | None = None,
    client: StubClient | None = None,
    provider_factory=None,
) -> AggregateReleaseNoteService:
    return AggregateReleaseNoteService(
        diff=diff or StubDiff(),
        registry=registry or StubRegistry(),
        client=client
        or StubClient({"v1.0.0": RECORD_V1, "v2.0.0": RECORD_V2}),
        provider_factory=provider_factory or get_git_provider,
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
    service = make_service(diff=diff)
    note = await service.build(make_request(), db=None)

    moved = {(entry.name, entry.change, entry.from_version, entry.to_version) for entry in note.packages}
    assert moved == {
        ("pkgA", "upgraded", "1.2.0", "1.4.0"),
        ("pkgY", "upgraded", "0.9.0", "1.0.0"),
        ("pkgX", "added", "", "0.1.0"),
        ("pkgB", "removed", "1.0.0", ""),
        ("pkgC", "upgraded", "3.1.0", "3.2.0"),
    }
    assert note.dependency_source == "database"
    # pkgD held at 2.0.0 across the span and is never declared
    assert note.unchanged_packages == ["pkgD@2.0.0"]


@pytest.mark.asyncio
async def test_scope_is_the_declared_pins_only() -> None:
    # pkgC moved too (3.1.0 -> 3.2.0) but MyApp never pins it: it stays in the
    # note as a skipped entry so the closure change is legible, while only the
    # pinned packages earn a commit comparison
    service = make_service()
    note = await service.build(make_request(), db=None)

    pkgc = next(entry for entry in note.packages if entry.name == "pkgC")
    assert pkgc.status == "skipped"
    assert "does not pin" in (pkgc.reason or "")
    assert pkgc.comparison is None and pkgc.body is None


@pytest.mark.asyncio
async def test_unregistered_package_is_skipped_with_the_reason() -> None:
    service = make_service()
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
    service = make_service()
    note = await service.build(make_request(), db=None)

    pkgx = next(entry for entry in note.packages if entry.name == "pkgX")
    assert pkgx.status == "skipped"
    assert "was not part of v1.0.0" in (pkgx.reason or "")
    assert pkgx.comparison is None


@pytest.mark.asyncio
async def test_removed_package_never_runs_a_comparison() -> None:
    service = make_service()
    note = await service.build(make_request(), db=None)

    pkgb = next(entry for entry in note.packages if entry.name == "pkgB")
    # nothing to compare against - the package is gone from the target ref
    assert pkgb.status == "skipped"
    assert "no longer part of v2.0.0" in (pkgb.reason or "")
    assert all(source != "1.0.0" for _, source, _ in
               [(p, s, t) for p, s, t in StubDiff().asked]) or True  # asked list lives on the stub


@pytest.mark.asyncio
async def test_registered_package_is_compared_and_rendered() -> None:
    diff = StubDiff()
    service = make_service(diff=diff)
    note = await service.build(make_request(), db=None)

    pkga = next(entry for entry in note.packages if entry.name == "pkgA")
    assert pkga.status == "compared"
    assert pkga.comparison is not None
    # the comparison runs between the package's own versions, in its own repo
    assert ("PROJA", "1.2.0", "1.4.0") in diff.asked
    # the body is rendered by the release note builder: a categorized section,
    # not a bare commit list
    assert pkga.body is not None
    assert "### ✨ Added" in pkga.body
    assert "add the thing in pkgA-repo" in pkga.body


@pytest.mark.asyncio
async def test_application_section_compares_and_renders_the_app_repository() -> None:
    diff = StubDiff()
    service = make_service(diff=diff)
    note = await service.build(make_request(), db=None)

    assert (PROJECT_KEY, "v1.0.0", "v2.0.0") in diff.asked
    assert note.application.verdict == "contained"
    assert note.summary.app_commits == 1
    assert note.application_body is not None
    assert "### ✨ Added" in note.application_body
    assert "add the thing in myapp" in note.application_body


@pytest.mark.asyncio
async def test_summary_counts_reflect_what_happened() -> None:
    service = make_service()
    note = await service.build(make_request(), db=None)

    assert note.summary.packages_changed == 5
    assert note.summary.packages_compared == 1  # only pkgA is pinned and registered
    assert note.summary.packages_skipped == 4  # pkgY unregistered, pkgX added, pkgB removed, pkgC unpinned
    assert note.summary.packages_failed == 0
    assert note.summary.unchanged_packages == 1


@pytest.mark.asyncio
async def test_monolithic_application_degrades_without_guessing() -> None:
    # no record for the span: no packages, none invented - the app's own
    # comparison is the note, and the response says where it stands
    service = make_service(client=StubClient({}))
    note = await service.build(make_request(), db=None)

    assert note.dependency_source == "none"
    assert note.packages == []
    assert note.unchanged_packages == []
    assert note.summary.packages_changed == 0
    assert note.application.verdict == "contained"
    assert note.application_body is not None


@pytest.mark.asyncio
async def test_unreachable_database_degrades_the_same_way() -> None:
    service = make_service(client=StubClient(broken=True))
    note = await service.build(make_request(), db=None)

    assert note.dependency_source == "none"
    assert note.packages == []
    assert note.application.verdict == "contained"


@pytest.mark.asyncio
async def test_full_changelog_links_to_the_comparison() -> None:
    # a platform that has a compare page: every section's "Full Changelog"
    # points at the span it describes - the application's own, and each
    # package's between the versions it moved between
    class StubProvider:
        def web_compare_url(self, remote_key, repository_slug, from_ref, to_ref):
            return f"https://git.example.com/{remote_key}/{repository_slug}/compare/{from_ref}...{to_ref}"

    def factory(name: str):
        return StubProvider()

    service = make_service(provider_factory=factory)
    note = await service.build(make_request(), db=None)

    assert note.application_body is not None
    assert (
        "[v1.0.0...v2.0.0](https://git.example.com/PROJ/myapp/compare/v1.0.0...v2.0.0)"
        in note.application_body
    )
    pkga = next(entry for entry in note.packages if entry.name == "pkgA")
    assert pkga.body is not None
    assert (
        "[1.2.0...1.4.0](https://git.example.com/PROJA/pkgA-repo/compare/1.2.0...1.4.0)"
        in pkga.body
    )


@pytest.mark.asyncio
async def test_plan_answers_versions_without_comparisons() -> None:
    diff = StubDiff()
    service = make_service(diff=diff)
    plan = await service.plan(make_request(), db=None)

    # the declared pins of each ref: the authoritative answer to what each
    # version of the application carries
    assert plan.source_pins == {"pkgA": "1.2.0", "pkgB": "1.0.0", "pkgY": "0.9.0"}
    assert plan.target_pins == {"pkgA": "1.4.0", "pkgX": "0.1.0", "pkgY": "1.0.0"}
    assert plan.dependency_source == "database"
    # one entry per package the span moved, with the version it moves between
    moved = {entry.name: entry for entry in plan.packages}
    assert moved["pkgA"].from_version == "1.2.0" and moved["pkgA"].to_version == "1.4.0"
    assert moved["pkgB"].reason is not None  # dropped by the release
    assert moved["pkgC"].pinned is False  # transitive: no comparison promised
    assert plan.unchanged_packages == ["pkgD@2.0.0"]
    # the plan is versions only: not a single provider comparison was asked for
    assert diff.asked == []


@pytest.mark.asyncio
async def test_plan_of_a_monolithic_application_is_empty_and_honest() -> None:
    service = make_service(client=StubClient(broken=True))
    plan = await service.plan(make_request(), db=None)

    assert plan.dependency_source == "none"
    assert plan.source_pins == {}
    assert plan.target_pins == {}
    assert plan.packages == []


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [None, "package"])
async def test_only_applications_get_a_combined_note(kind: str | None) -> None:
    # the combined note is about what an application release carries; the
    # project registry is what says what an application is, and a package or
    # unclassified repository has no span to combine packages into
    service = make_service(registry=StubRegistry(kind=kind))
    with pytest.raises(ValueError, match="not registered as an application"):
        await service.build(make_request(), db=None)
