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
    SOURCE_NONE,
    ReleaseNoteScopeService,
    order_candidates,
    previous_by_name,
    probe_budget,
    version_sort_key,
)


C1 = "a" * 40
C2 = "b" * 40
C3 = "c" * 40

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
