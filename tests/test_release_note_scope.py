"""Tests for release note scope resolution.

The resolver is what keeps the tag -> commits panel honest: a tag's release scope
comes from the provider's tags, verified where it can be, and an answer that
cannot be determined is reported as such instead of being turned into a capped
enumeration of the whole history.
"""

from __future__ import annotations

from typing import Any

from src.core.exceptions import GitServiceException
from src.services.git_providers import BaseGitProvider
from src.services.release_note_scope_service import (
    REASON_FIRST_RELEASE,
    REASON_PROVIDED,
    REASON_RESOLVED,
    REASON_UNRESOLVED,
    SOURCE_ANCESTOR,
    SOURCE_EXPLICIT,
    SOURCE_NAME_ORDER,
    SOURCE_NEAREST,
    SOURCE_NONE,
    ReleaseNoteScopeService,
    nearest_tag,
    order_candidates,
    orders_above,
    predecessor_candidates,
    previous_by_name,
    previous_by_version,
    probe_budget,
    version_sort_key,
)


C1 = "a" * 40
C2 = "b" * 40
C3 = "c" * 40
C4 = "d" * 40
C5 = "e" * 40

PROJECT = "PROJ"
REPO = "my-repo"


def tag(name: str, sha: str, date: int | None = None) -> dict[str, Any]:
    """A normalized tag entry as the provider primitive returns it."""
    return {"name": name, "sha": sha, "date": date, "is_annotated": False}


class FakeProvider(BaseGitProvider):
    """Tag listing plus ancestry answers, with call counters."""

    def __init__(
        self,
        tags: list[dict[str, Any]],
        ancestors: tuple[str, ...] = (),
        *,
        fail_listing: bool = False,
        fail_probe: bool = False,
    ) -> None:
        self.tags = tags
        self.ancestors = set(ancestors)
        self.fail_listing = fail_listing
        self.fail_probe = fail_probe
        self.list_calls = 0
        self.probes: list[tuple[str, str]] = []

    @property
    def name(self) -> str:
        return "bitbucket_server"

    async def get_project_info(self, project_key: str) -> dict[str, Any] | None:
        return None

    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any] | None:
        return None

    async def get_user_info(self, username: str) -> dict[str, Any] | None:
        return None

    async def list_tags_with_commits(
        self, project_key: str, repository_slug: str, limit: int = 1000
    ) -> list[dict[str, Any]]:
        self.list_calls += 1
        if self.fail_listing:
            raise GitServiceException("tag listing failed")
        return self.tags[:limit]

    async def contains_commit(
        self, project_key: str, repository_slug: str, ref: str, commit: str
    ) -> bool:
        self.probes.append((ref, commit))
        if self.fail_probe:
            raise GitServiceException("probe failed")
        return commit in self.ancestors


class FakeCache:
    """Minimal RedisCache stand-in."""

    def __init__(self) -> None:
        self.data: dict[str, dict[str, Any]] = {}

    async def get_json(self, key: str) -> dict[str, Any] | None:
        return self.data.get(key)

    async def set_json(self, key: str, value: dict[str, Any], expire: int | None = None) -> bool:
        self.data[key] = value
        return True


class FakeMetrics:
    def __init__(self) -> None:
        self.cache_hits = 0

    def increment_cache_hit(self, cache_type: str) -> None:
        self.cache_hits += 1


def build_service(
    provider: FakeProvider,
    cache: FakeCache | None = None,
    metrics: FakeMetrics | None = None,
) -> ReleaseNoteScopeService:
    return ReleaseNoteScopeService(
        metrics=metrics or FakeMetrics(),
        cache=cache or FakeCache(),
        provider_factory=lambda name: provider,
    )


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


def test_probe_budget_scales_with_the_tag_count() -> None:
    """More tags usually mean more lines, so the walk may skip over more tags."""
    assert probe_budget(0) == 4
    assert probe_budget(12) == 4
    assert probe_budget(60) == 12
    assert probe_budget(200) == 20
    # capped: beyond the maximum the name-order fallback is a better use of latency
    assert probe_budget(5_000) == 20


def test_version_sort_key_orders_versions_numerically() -> None:
    names = ["v1.10.0", "v1.9.0", "v2.0.0", "v1.9.10"]
    assert sorted(names, key=version_sort_key) == ["v1.9.0", "v1.9.10", "v1.10.0", "v2.0.0"]


def test_order_candidates_prefers_commit_dates_then_names() -> None:
    """Dated tags come first (newest date), undated ones fall back to name order."""
    tags = [
        tag("v1.0.0", C1, 100),
        tag("v2.0.0", C2, 300),
        tag("alpha", C3, None),
        tag("zeta", C1, None),
    ]

    ordered = [entry["name"] for entry in order_candidates(tags)]

    assert ordered == ["v2.0.0", "v1.0.0", "zeta", "alpha"]


def test_previous_by_name_finds_the_older_neighbour() -> None:
    tags = [tag("v1.0.0", C1), tag("v1.2.0", C2), tag("v1.10.0", C3)]

    neighbour = previous_by_name("v1.10.0", tags)

    assert neighbour is not None
    assert neighbour["name"] == "v1.2.0"


def test_previous_by_name_is_none_for_the_oldest_tag() -> None:
    assert previous_by_name("v1.0.0", [tag("v1.0.0", C1), tag("v1.2.0", C2)]) is None


def test_previous_by_name_is_none_when_the_ref_is_not_a_tag() -> None:
    assert previous_by_name("main", [tag("v1.0.0", C1)]) is None


def test_previous_by_version_reads_the_build_before_a_build() -> None:
    """``3.14.0-Build23005`` follows ``3.14.0-Build23004``, another release of 3.14.0."""
    tags = [
        tag("3.14.0-Build23005", C1, 500),
        tag("3.14.0-Build23004", C2, 400),
        tag("3.14.0-Build23003", C3, 300),
        tag("Test-Build23000", C5, 250),
        tag("DEBUG-Build22010", C4, 240),
        tag("3.13.0-Build23003", C4, 100),
    ]

    previous = previous_by_version("3.14.0-Build23005", tags)

    assert previous is not None
    assert previous["name"] == "3.14.0-Build23004"


def test_previous_by_version_ignores_a_later_build_of_the_same_version() -> None:
    """A build released after the tag is not its predecessor, even if it exists."""
    tags = [
        tag("3.14.0-Build23006", C1, 600),
        tag("3.14.0-Build23005", C2, 500),
    ]

    assert previous_by_version("3.14.0-Build23005", tags) is None


def test_previous_by_version_falls_back_to_the_version_below() -> None:
    """No build of the version precedes it: the highest build below does."""
    tags = [
        tag("3.14.0", C1, 400),
        tag("3.13.0-Build23001", C2, 90),
        tag("3.13.0-Build23003", C3, 100),
        tag("3.13.0-Build23002", C4, 95),
    ]

    previous = previous_by_version("3.14.0", tags)

    assert previous is not None
    assert previous["name"] == "3.13.0-Build23003"


def test_orders_above_keeps_later_releases_out_of_the_answer() -> None:
    """A later build, or any higher version, can never precede the released tag."""
    assert orders_above("3.14.0-Build23005", "3.14.0-Build23006") is True
    assert orders_above("3.14.0-Build23005", "3.18.0-Build21000") is True
    assert orders_above("3.14.0-Build23005", "3.14.0-Build23004") is False
    assert orders_above("3.14.0-Build23005", "3.13.0-Build23003") is False
    # a tag that names no version is left to the name order, not ordered here
    assert orders_above("3.14.0-Build23005", "Test-Build23000") is False


def test_previous_by_version_compares_versions_as_numbers() -> None:
    """1.10 comes after 1.9: a version is read as numbers, not as text."""
    tags = [tag("v1.9.0", C1, 10), tag("v1.10.0", C2, 20), tag("v1.2.0", C3, 30)]

    previous = previous_by_version("v1.10.0", tags)

    assert previous is not None
    assert previous["name"] == "v1.9.0"


def test_previous_by_version_leaves_a_name_that_is_not_a_version_alone() -> None:
    """A tag that names no version is none of its business - the name order holds it."""
    assert previous_by_version("Test-Build23000", [tag("v1.0.0", C1)]) is None


def test_predecessor_candidates_ask_about_releases_before_debug_tags() -> None:
    """A debug tag cut after the last release is an ancestor, but it is not the release."""
    tags = [
        tag("v3.0.0", C1, 500),
        tag("DEBUG-Build23010", C4, 400),
        tag("Test-Build23000", C5, 300),
        tag("v2.0.0", C2, 200),
        tag("v1.0.0", C3, 100),
    ]

    ordered = [entry["name"] for entry in predecessor_candidates("v3.0.0", tags)]

    assert ordered == ["v2.0.0", "v1.0.0", "DEBUG-Build23010", "Test-Build23000"]


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #


async def test_resolution_uses_the_verified_ancestor() -> None:
    """A candidate is accepted only after the provider confirms the ancestry."""
    provider = FakeProvider(
        tags=[tag("v1.0.0", C1, 100), tag("v2.0.0", C2, 200), tag("v3.0.0", C3, 300)],
        ancestors=(C1,),
    )

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="v3.0.0"
    )

    assert scope.source == SOURCE_ANCESTOR
    assert scope.verified is True
    assert scope.reason == REASON_RESOLVED
    assert scope.previous_ref == "v1.0.0"
    assert scope.previous_sha == C1
    assert scope.version_sha == C3
    # the non-ancestor candidate was probed first and rejected
    assert provider.probes == [(C3, C2), (C3, C1)]


async def test_resolution_verifies_against_the_released_revision() -> None:
    """The released side is pinned to its revision, not to the moving tag name."""
    provider = FakeProvider(tags=[tag("v1.0.0", C1, 100), tag("v2.0.0", C2, 200)], ancestors=(C1,))

    await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="v2.0.0"
    )

    assert provider.probes == [(C2, C1)]


async def test_resolution_falls_back_to_name_order_and_reports_unverified() -> None:
    """Nothing verified: the previous tag by name is used, but marked inferred."""
    provider = FakeProvider(
        tags=[tag("v1.0.0", C1, 100), tag("v2.0.0", C2, 200), tag("v3.0.0", C3, 300)],
        ancestors=(),
    )

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="v3.0.0"
    )

    assert scope.source == SOURCE_NAME_ORDER
    assert scope.verified is False
    assert scope.reason == REASON_RESOLVED
    assert scope.previous_ref == "v2.0.0"


async def test_resolution_follows_the_build_before_a_build() -> None:
    """A build of a version is measured against the build released before it."""
    provider = FakeProvider(
        tags=[
            tag("3.14.0-Build23004", C1, 400),
            tag("3.14.0-Build23003", C2, 300),
            tag("Test-Build23000", C4, 250),
            tag("DEBUG-Build22010", C5, 240),
            tag("3.13.0-Build23003", C3, 100),
        ],
        # both are ancestors, so only the order decides which one precedes the release
        ancestors=(C2, C3),
    )

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="3.14.0-Build23004"
    )

    assert scope.source == SOURCE_ANCESTOR
    assert scope.verified is True
    assert scope.reason == REASON_RESOLVED
    assert scope.previous_ref == "3.14.0-Build23003"
    assert scope.previous_sha == C2
    # the build before it is the first candidate asked about
    assert provider.probes[0] == (C1, C2)


async def test_unverified_scope_follows_the_build_before_as_well() -> None:
    """With nothing to verify, the build before it still beats the name order."""
    provider = FakeProvider(
        tags=[
            tag("3.14.0-Build23004", C1, 400),
            tag("3.14.0-Build23003", C2, 300),
            tag("3.13.0-Build23003", C3, 100),
        ],
        ancestors=(),
    )

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="3.14.0-Build23004"
    )

    assert scope.source == SOURCE_NAME_ORDER
    assert scope.verified is False
    assert scope.previous_ref == "3.14.0-Build23003"


def test_nearest_tag_takes_the_closest_older_tag_by_date() -> None:
    """No order to read: the tag cut just before it is the base."""
    tags = [
        tag("aaa-23005", C1, 500),
        tag("build-23004", C2, 450),
        tag("build-22990", C3, 100),
    ]

    nearest = nearest_tag("aaa-23005", tags)

    assert nearest is not None
    assert nearest["name"] == "build-23004"


def test_nearest_tag_never_takes_a_later_release() -> None:
    """A higher version is closer in time, and still cannot precede the release."""
    tags = [
        tag("3.14.0", C1, 500),
        tag("3.18.0-Build21000", C2, 490),
        tag("3.13.0-Build23003", C3, 100),
    ]

    nearest = nearest_tag("3.14.0", tags)

    assert nearest is not None
    assert nearest["name"] == "3.13.0-Build23003"


def test_nearest_tag_without_dates_takes_the_nearest_name_below() -> None:
    """No dates to compare (GitHub reports none): the nearest name answers."""
    tags = [tag("aaa", C1), tag("aab", C2)]

    nearest = nearest_tag("aab", tags)

    assert nearest is not None
    assert nearest["name"] == "aaa"


def test_nearest_tag_is_none_when_every_tag_is_newer() -> None:
    tags = [tag("aaa-23005", C1, 100), tag("build-23004", C2, 450)]

    assert nearest_tag("aaa-23005", tags) is None


def test_nearest_tag_is_none_for_a_ref_that_is_not_a_tag() -> None:
    assert nearest_tag("main", [tag("v1.0.0", C1, 100)]) is None


def test_predecessor_candidates_leave_out_later_releases() -> None:
    """A later build, and any higher version, are never worth asking about."""
    tags = [
        tag("3.14.0-Build23005", C1, 500),
        tag("3.14.0-Build23004", C2, 400),
        tag("3.14.0-Build23006", C3, 600),
        tag("3.18.0-Build21000", C4, 700),
    ]

    ordered = [entry["name"] for entry in predecessor_candidates("3.14.0-Build23005", tags)]

    assert ordered == ["3.14.0-Build23004"]


async def test_a_release_line_does_not_follow_a_later_one() -> None:
    """``3.14.0-Build23005`` follows its own build, not the later 3.18.0-Build21000.

    The later tag is an ancestor of the released commit - the 3.14.0 line was branched
    off it - which is what used to make it the answer. It names a later release, though,
    and the commits it shares with 3.14.0 are not the ones 3.14.0 added.
    """
    provider = FakeProvider(
        tags=[
            tag("3.14.0-Build23005", C1, 500),
            tag("3.14.0-Build23004", C2, 400),
            tag("3.14.0-Build23003", C3, 300),
            tag("3.18.0-Build21000", C4, 200),
        ],
        ancestors=(C2, C4),
    )

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="3.14.0-Build23005"
    )

    assert scope.reason == REASON_RESOLVED
    assert scope.previous_ref == "3.14.0-Build23004"
    assert scope.previous_sha == C2
    # the later release was never even asked about
    assert all(probe[1] != C4 for probe in provider.probes)


async def test_a_tag_with_no_readable_order_falls_back_to_the_closest_tag() -> None:
    """Names carry no order and nothing is an ancestor: the closest tag still bounds it."""
    provider = FakeProvider(
        tags=[
            tag("aaa-23005", C1, 500),
            tag("build-23004", C2, 450),
            tag("build-22990", C3, 100),
        ],
        ancestors=(),
    )

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="aaa-23005"
    )

    assert scope.reason == REASON_RESOLVED
    assert scope.source == SOURCE_NEAREST
    assert scope.verified is False
    assert scope.previous_ref == "build-23004"
    assert scope.previous_sha == C2


async def test_a_tag_that_names_no_version_keeps_the_name_order() -> None:
    """``Test-Build23001`` releases no version, so the tag before it by name precedes it."""
    provider = FakeProvider(
        tags=[tag("Test-Build23001", C1, 300), tag("Test-Build23000", C2, 200)],
        ancestors=(),
    )

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="Test-Build23001"
    )

    assert scope.source == SOURCE_NAME_ORDER
    assert scope.previous_ref == "Test-Build23000"


async def test_the_walk_asks_about_releases_before_debug_tags() -> None:
    """A debug tag newer than the last release must not answer for that release."""
    provider = FakeProvider(
        tags=[
            tag("v3.0.0", C1, 500),
            tag("DEBUG-Build23010", C4, 400),
            tag("Test-Build23000", C5, 350),
            # the version below the released one, but on another line - not an ancestor
            tag("v2.1.0", C2, 300),
            tag("v2.0.0", C3, 200),
        ],
        # the debug and test tags are ancestors of the release; the release below is not
        ancestors=(C4, C5, C3),
    )

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="v3.0.0"
    )

    assert scope.source == SOURCE_ANCESTOR
    assert scope.previous_ref == "v2.0.0"
    assert scope.previous_sha == C3


async def test_a_repository_of_irregular_tags_still_resolves_by_ancestry() -> None:
    """No release names at all: the newest ancestor answers, as it always did."""
    provider = FakeProvider(
        tags=[
            tag("Test-Build23001", C1, 300),
            tag("Test-Build23000", C2, 200),
            tag("DEBUG-Build22010", C3, 100),
        ],
        ancestors=(C2, C3),
    )

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="Test-Build23001"
    )

    assert scope.source == SOURCE_ANCESTOR
    assert scope.previous_ref == "Test-Build23000"


async def test_the_first_tag_of_a_branch_follows_the_release_it_was_cut_from() -> None:
    """A tag that names no version still follows the last release under it."""
    provider = FakeProvider(
        tags=[
            tag("feature/2026Dec", C1, 500),
            tag("feature/2026Nov-3", C4, 450),
            tag("v2.1.0", C2, 400),
            tag("v2.0.0", C3, 300),
        ],
        # another branch's tag is an ancestor too, and more recent than the release
        ancestors=(C4, C2, C3),
    )

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="feature/2026Dec"
    )

    assert scope.source == SOURCE_ANCESTOR
    assert scope.previous_ref == "v2.1.0"
    assert scope.previous_sha == C2


async def test_resolution_reports_a_first_release() -> None:
    """The oldest tag of a repository has no predecessor - and that is an answer."""
    provider = FakeProvider(tags=[tag("v1.0.0", C1, 100)])

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="v1.0.0"
    )

    assert scope.reason == REASON_FIRST_RELEASE
    assert scope.source == SOURCE_NONE
    assert scope.previous_ref is None
    assert scope.version_sha == C1


async def test_resolution_is_unresolved_when_the_ref_is_not_a_tag() -> None:
    """A ref the repository does not have as a tag cannot be scoped."""
    provider = FakeProvider(tags=[tag("v1.0.0", C1, 100)], ancestors=())

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="main"
    )

    assert scope.reason == REASON_UNRESOLVED
    assert scope.previous_ref is None


async def test_resolution_is_unresolved_when_the_repository_has_no_tags() -> None:
    """Nothing to resolve against - and the fallback says so instead of guessing."""
    provider = FakeProvider(tags=[])

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="v1.0.0"
    )

    assert scope.reason == REASON_UNRESOLVED
    assert scope.source == SOURCE_NONE
    assert provider.probes == []


async def test_resolution_is_unresolved_when_the_tag_listing_fails() -> None:
    """A provider failure degrades to 'unknown' - it never fails the request."""
    provider = FakeProvider(tags=[], fail_listing=True)

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="v3.0.0"
    )

    assert scope.reason == REASON_UNRESOLVED


async def test_resolution_falls_back_when_a_probe_fails() -> None:
    provider = FakeProvider(tags=[tag("v1.0.0", C1, 100), tag("v2.0.0", C2, 200)], fail_probe=True)

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="v2.0.0"
    )

    assert scope.source == SOURCE_NAME_ORDER
    assert scope.verified is False
    assert scope.previous_ref == "v1.0.0"


async def test_resolution_stops_at_the_probe_budget() -> None:
    """The walk is bounded, and reaching the bound falls through to name order."""
    tags = [tag(f"v{index}.0.0", C1, index) for index in range(1, 41)]
    provider = FakeProvider(tags=tags, ancestors=())

    scope = await build_service(provider).resolve(
        project_key=PROJECT, repository_slug=REPO, version="v40.0.0"
    )

    assert len(provider.probes) == probe_budget(len(tags)) == 8
    assert scope.source == SOURCE_NAME_ORDER
    assert scope.previous_ref == "v39.0.0"


async def test_explicit_predecessor_is_authoritative() -> None:
    """A supplied predecessor is used as-is, without asking the provider."""
    provider = FakeProvider(tags=[tag("v1.0.0", C1, 100)], ancestors=(C1,))

    scope = await build_service(provider).resolve(
        project_key=PROJECT,
        repository_slug=REPO,
        version="v2.0.0",
        previous_ref="v1.0.0",
    )

    assert scope.source == SOURCE_EXPLICIT
    assert scope.verified is True
    assert scope.reason == REASON_PROVIDED
    assert scope.previous_ref == "v1.0.0"
    assert provider.list_calls == 0


# --------------------------------------------------------------------------- #
# Caching
# --------------------------------------------------------------------------- #


async def test_cached_resolution_avoids_the_tag_listing() -> None:
    provider = FakeProvider(tags=[tag("v1.0.0", C1, 100), tag("v2.0.0", C2, 200)], ancestors=(C1,))
    cache = FakeCache()
    metrics = FakeMetrics()
    service = build_service(provider, cache=cache, metrics=metrics)

    first = await service.resolve(project_key=PROJECT, repository_slug=REPO, version="v2.0.0")
    second = await service.resolve(project_key=PROJECT, repository_slug=REPO, version="v2.0.0")

    assert first == second
    assert provider.list_calls == 1
    assert metrics.cache_hits == 1


async def test_refresh_bypasses_the_cached_resolution() -> None:
    provider = FakeProvider(tags=[tag("v1.0.0", C1, 100), tag("v2.0.0", C2, 200)], ancestors=(C1,))
    service = build_service(provider)

    await service.resolve(project_key=PROJECT, repository_slug=REPO, version="v2.0.0")
    await service.resolve(project_key=PROJECT, repository_slug=REPO, version="v2.0.0", refresh=True)

    assert provider.list_calls == 2


async def test_the_resolution_is_scoped_per_tag() -> None:
    """One tag's resolution must not answer for another."""
    provider = FakeProvider(
        tags=[tag("v1.0.0", C1, 100), tag("v2.0.0", C2, 200), tag("v3.0.0", C3, 300)],
        ancestors=(C1, C2),
    )
    service = build_service(provider)

    first = await service.resolve(project_key=PROJECT, repository_slug=REPO, version="v2.0.0")
    second = await service.resolve(project_key=PROJECT, repository_slug=REPO, version="v3.0.0")

    assert first.previous_ref == "v1.0.0"
    assert second.previous_ref == "v2.0.0"
    assert provider.list_calls == 2
