"""Release note scope resolution.

Answers one question on the server: which release ref precedes a given tag? With
that answer the commits a tag released are a provider *difference*
(``previous..version``) instead of an enumeration of everything reachable from
the tag, which is what used to cap out on a repository with years of history.

The predecessor is resolved in a defined order - an explicit ref supplied by the
caller, the previous build of the same version, the version below it, a verified
ancestor (one provider call per candidate), the previous tag in version-aware name
order, the tag closest to it, or nothing at all - and the result carries how it was
obtained, so the UI can state the scope instead of guessing it from a page-sized list
of tags.

The build of a version is a release in its own right. A repository that publishes
``3.14.0-Build23000`` … ``3.14.0-Build23005`` ships five releases of 3.14.0, and each
one is measured against the build before it: choosing ``3.14.0-Build23005`` has to
infer ``3.14.0-Build23004``, not the version below 3.14.0. When no build of the same
version precedes the tag, the version below answers instead.

A candidate has to be older than the released tag - a later build of the same version
or a higher version can never be its predecessor, however it sits in the history. This
is what kept a repository whose release lines branch apart from resolving
``3.14.0-Build23005`` against ``3.18.0-Build21000``: that tag is an ancestor of the
released commit, but it is a later release, and the commits it shares with 3.14.0 are
not the ones 3.14.0 added. The releases of the repository are then asked about before
the tags that name no version, which are cut from the same history and would otherwise
answer for a release they merely sit beside.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from src.core.config import settings
from src.core.exceptions import AppException

# The provenance values are part of the API contract, so they live with the schema
# and are imported here rather than defined twice.
from src.schemas.release_note import (
    REASON_FIRST_RELEASE,
    REASON_PROVIDED,
    REASON_RESOLVED,
    REASON_UNRESOLVED,
    SOURCE_ANCESTOR,
    SOURCE_EXPLICIT,
    SOURCE_NAME_ORDER,
    SOURCE_NEAREST,
    SOURCE_NONE,
)
from src.services.git_providers import BaseGitProvider, get_git_provider
from src.services.release_diff_service import (
    resolve_provider_name,
    resolve_remote_project_key,
)
from src.utils.log import get_logger
from src.utils.metrics import MetricsCollector
from src.utils.metrics import metrics as metrics_collector
from src.utils.redis import RedisCache


logger = get_logger(__name__)

# The ancestry walk probes candidates one provider call at a time, so the budget
# scales with the number of tags: a repository with more release lines needs to
# skip over more recent tags that are not ancestors of the released one.
PROBE_MIN = 4
PROBE_MAX = 20
TAGS_PER_PROBE = 5

# The tag listing is used for ordering and revision lookup, not as a paging
# exercise: a generous cap keeps the resolver correct on most repositories.
TAG_LIST_LIMIT = 1000

# Bumped when the resolution rules change, so a cached answer from the old rules is
# not served under the new ones. v4: the closest tag answers when the names carry no
# order, so a tag with no readable predecessor no longer reads as a full-history scan.
CACHE_KEY_VERSION = "v4"


def probe_budget(tag_count: int) -> int:
    """Probe budget for the ancestry walk, scaled by the repository's tag count."""
    scaled = max(tag_count, 0) // TAGS_PER_PROBE
    return max(PROBE_MIN, min(PROBE_MAX, scaled))


def version_sort_key(name: str) -> tuple[tuple[int, Any], ...]:
    """Numeric-aware ordering key so ``v1.10.0`` sorts after ``v1.9.0``.

    Tag names are not guaranteed to be versions, so the key only relies on the
    digits it finds: a chunk is compared as a number when it is numeric and as
    text otherwise. The same shape the UI uses (``localeCompare`` with numeric
    collation), so both sides order a tag list the same way.
    """
    chunks = re.split(r"(\d+)", (name or "").strip().lower())
    return tuple((1, int(chunk)) if chunk.isdigit() else (0, chunk) for chunk in chunks if chunk)


# A tag that releases a version leads with it: ``3.14.0-Build23004`` releases 3.14.0.
# What follows is the build of that release, so it orders within the version rather
# than deciding which version the tag belongs to.
VERSION_PATTERN = re.compile(r"^[vV]?(\d+(?:\.\d+)*)")


def version_of(name: str) -> tuple[int, ...] | None:
    """The version a tag name leads with, or ``None`` when it does not read as one.

    ``3.14.0-Build23004`` reads as ``(3, 14, 0)``. A name like ``Test-Build23000``
    reads as nothing at all: it takes no part in version ordering and is left to the
    name order, which is what keeps the tags a repository keeps beside its releases
    from being read as releases of their own.
    """
    match = VERSION_PATTERN.match((name or "").strip())
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def previous_build(version: str, tags: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The build of the same version released just before ``version``.

    ``3.14.0-Build23005`` follows ``3.14.0-Build23004``: the builds of one version are
    releases in their own right, each covering what it added over the build before it.
    Only tags that name the same version qualify, and only those that order below the
    released tag - a later build of 3.14.0 is a later release, not a predecessor.
    """
    current_version = version_of(version)
    if current_version is None:
        return None

    current_key = version_sort_key(version)
    lower = [
        tag
        for tag in tags
        if str(tag.get("name") or "") != version
        and version_of(str(tag.get("name") or "")) == current_version
        and version_sort_key(str(tag.get("name") or "")) < current_key
    ]
    if not lower:
        return None

    return max(lower, key=lambda tag: version_sort_key(str(tag.get("name") or "")))


def orders_above(version: str, candidate: str) -> bool:
    """Whether ``candidate`` names a later release than ``version``.

    An answer has to be older than the question. A later build of the same version, or
    a higher version altogether, is never the predecessor of a tag - even when it is an
    ancestor of the commit that tag points at, which is exactly the case for a release
    line that was branched off a later one.
    """
    current = version_of(version)
    other = version_of(candidate)
    if current is None or other is None:
        return False
    if other != current:
        return other > current
    return version_sort_key(candidate) > version_sort_key(version)


def previous_by_version(version: str, tags: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The tag a release follows: the build before it, else the version below it.

    The builds of a version come first. A repository that publishes
    ``3.14.0-Build23000`` … ``3.14.0-Build23005`` ships five releases of 3.14.0, so
    ``3.14.0-Build23005`` is measured against ``3.14.0-Build23004``.

    Only when no build of the same version precedes the tag does the version below
    answer, where the highest tag of that version wins, read by name and then by date:
    ``3.13.0-Build23003`` is taken over ``3.13.0-Build23002``.

    Returns ``None`` when the tag names no version, and when neither a build nor a lower
    version is known: the caller falls back to the name order in the first case and to
    the remaining candidates in the second.
    """
    build = previous_build(version, tags)
    if build is not None:
        return build

    current = version_of(version)
    if current is None:
        return None

    lower: list[tuple[tuple[int, ...], dict[str, Any]]] = []
    for candidate in tags:
        if str(candidate.get("name") or "") == version:
            continue
        candidate_version = version_of(str(candidate.get("name") or ""))
        if candidate_version is not None and candidate_version < current:
            lower.append((candidate_version, candidate))
    if not lower:
        return None

    best = max(candidate_version for candidate_version, _ in lower)
    same_version = [
        candidate for candidate_version, candidate in lower if candidate_version == best
    ]
    return max(
        same_version,
        key=lambda tag: (
            version_sort_key(str(tag.get("name") or "")),
            tag.get("date") or 0,
        ),
    )


def order_candidates(tags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order tag candidates newest first, for the ancestry walk.

    Dated tags come first (newest by commit date), because a predecessor is
    usually recent; tags whose provider reports no date fall back to name order
    rather than being dropped, so the walk still has something to probe.
    """
    return sorted(
        tags,
        key=lambda tag: (
            1 if tag.get("date") is not None else 0,
            tag.get("date") or 0,
            version_sort_key(str(tag.get("name") or "")),
        ),
        reverse=True,
    )


def predecessor_candidates(version: str, tags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The tags worth asking about, in the order they are worth asking about.

    Three groups, the provider being asked about the first group before the next:

    1. the release before it - its previous build, or the version below when no build
       of the same version precedes the tag;
    2. the other tags that name a version, newest first;
    3. the tags that name no version, newest first.

    Tags that name a later release are left out altogether: they can be ancestors of
    the released commit and still be the wrong answer.

    That order is what keeps a repository's debug and test tags from answering for its
    releases. Those tags are cut from the same history as the release beside them, so by
    ancestry alone a ``DEBUG-`` tag newer than the last release *is* an ancestor of the
    released tag and is accepted as its predecessor - and the notes then carry only what
    was committed after that debug tag. A tag that names a version is a release, so the
    releases are asked about first, and the tags that name none are asked about when no
    release precedes the tag at all: a repository whose releases are named irregularly
    keeps resolving by ancestry exactly as it did.
    """
    released_before = previous_by_version(version, tags)
    others = order_candidates(
        [
            tag
            for tag in tags
            if str(tag.get("name") or "") != version
            and not orders_above(version, str(tag.get("name") or ""))
        ]
    )
    if released_before is not None:
        others = [tag for tag in others if tag is not released_before]

    named = [tag for tag in others if version_of(str(tag.get("name") or "")) is not None]
    unnamed = [tag for tag in others if version_of(str(tag.get("name") or "")) is None]
    return ([released_before] if released_before is not None else []) + named + unnamed


def previous_by_name(version: str, tags: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The tag released just before ``version`` in version-aware name order.

    Returns ``None`` both when the tag is the oldest one known and when ``version``
    is not part of the tag list at all - the caller distinguishes those two.
    """
    ordered = sorted(
        tags, key=lambda tag: version_sort_key(str(tag.get("name") or "")), reverse=True
    )
    names = [str(tag.get("name") or "") for tag in ordered]
    if version not in names:
        return None

    index = names.index(version)
    return ordered[index + 1] if index + 1 < len(ordered) else None


def nearest_tag(version: str, tags: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The tag closest to ``version``, for a repository no ordering can be read from.

    Tags are named by hand in such a repository - debug, test and temporary tags sit
    beside the releases - so neither the version nor the name order names a
    predecessor. Taking the tag closest to it still keeps the commits of the release
    a difference instead of a scan of the whole history; the answer is unverified and
    reported as such.

    Closeness is time: the newest tag cut before the released one. A repository
    whose providers report no dates falls back to the nearest name below it. A tag
    that names a later release is never chosen, and a tag with nothing older around
    it has no neighbour at all.

    Returns ``None`` when ``version`` is not part of the tag list, so a ref that is
    not a tag is left to the caller's 'unknown' rather than guessed at.
    """
    current = next((tag for tag in tags if str(tag.get("name") or "") == version), None)
    if current is None:
        return None

    candidates = [
        tag
        for tag in tags
        if str(tag.get("name") or "") != version
        and not orders_above(version, str(tag.get("name") or ""))
    ]
    if not candidates:
        return None

    current_date = current.get("date")
    if current_date:
        older = [
            tag
            for tag in candidates
            if tag.get("date") is not None and tag.get("date") < current_date
        ]
        if older:
            return max(
                older,
                key=lambda tag: (
                    tag.get("date"),
                    version_sort_key(str(tag.get("name") or "")),
                ),
            )
        if any(tag.get("date") is not None for tag in candidates):
            # every comparable tag is newer: this one is the oldest release
            return None

    current_key = version_sort_key(version)
    below = [
        tag
        for tag in candidates
        if version_sort_key(str(tag.get("name") or "")) < current_key
    ]
    if not below:
        return None
    return max(below, key=lambda tag: version_sort_key(str(tag.get("name") or "")))


@dataclass(frozen=True)
class ReleaseScope:
    """The release ref a tag is measured against, and how it was obtained."""

    version: str
    previous_ref: str | None = None
    previous_sha: str | None = None
    version_sha: str | None = None
    source: str = SOURCE_NONE
    verified: bool = False
    reason: str = REASON_UNRESOLVED

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ReleaseScope:
        return cls(
            version=str(payload.get("version") or ""),
            previous_ref=payload.get("previous_ref") or None,
            previous_sha=payload.get("previous_sha") or None,
            version_sha=payload.get("version_sha") or None,
            source=str(payload.get("source") or SOURCE_NONE),
            verified=bool(payload.get("verified")),
            reason=str(payload.get("reason") or REASON_UNRESOLVED),
        )


class ReleaseNoteScopeService:
    """Resolve the previous release ref of a tag on the server."""

    def __init__(
        self,
        metrics: MetricsCollector | None = None,
        cache: RedisCache | None = None,
        provider_factory: Callable[[str], BaseGitProvider] = get_git_provider,
    ) -> None:
        self.metrics = metrics or metrics_collector
        self.cache = cache or RedisCache()
        self._provider_factory = provider_factory

    async def resolve(
        self,
        *,
        project_key: str,
        repository_slug: str,
        version: str,
        git_provider: str | None = None,
        workspace_slug: str | None = None,
        previous_ref: str | None = None,
        refresh: bool = False,
    ) -> ReleaseScope:
        """Resolve the release scope of ``version``.

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            version: Released ref (normally a tag)
            git_provider: Optional provider override
            workspace_slug: Optional Bitbucket Cloud workspace
            previous_ref: Caller-supplied predecessor, used as-is when present
            refresh: Bypass the cached resolution

        Returns:
            A :class:`ReleaseScope`; never raises for a provider failure - an
            unresolvable scope is reported instead, so the notes request survives.
        """
        tag = (version or "").strip()
        explicit = (previous_ref or "").strip()

        if explicit:
            # The caller's answer is authoritative: it is not re-derived, and it
            # is not cached (its inputs vary with the caller, not with the repo).
            return ReleaseScope(
                version=tag,
                previous_ref=explicit,
                source=SOURCE_EXPLICIT,
                verified=True,
                reason=REASON_PROVIDED,
            )

        if not tag:
            return ReleaseScope(version=tag, reason=REASON_UNRESOLVED)

        provider_name = resolve_provider_name(git_provider)
        provider = self._provider_factory(provider_name)
        remote_key = resolve_remote_project_key(project_key, provider_name, workspace_slug)

        cache_key = self._build_cache_key(provider_name, remote_key, repository_slug, tag)
        if not refresh:
            cached = await self._read_cache(cache_key)
            if cached is not None:
                self.metrics.increment_cache_hit("release_note_scope")
                return ReleaseScope.from_dict(cached)

        try:
            tags = await provider.list_tags_with_commits(
                project_key=remote_key,
                repository_slug=repository_slug,
                limit=TAG_LIST_LIMIT,
            )
        except (AppException, NotImplementedError) as e:
            logger.warning(
                "Release note scope resolution could not list the tags",
                extra={
                    "project_key": project_key,
                    "repository_slug": repository_slug,
                    "git_provider": provider_name,
                    "error": str(e),
                },
            )
            return ReleaseScope(version=tag, reason=REASON_UNRESOLVED)

        scope = await self._resolve_from_tags(
            provider=provider,
            project_key=remote_key,
            repository_slug=repository_slug,
            version=tag,
            tags=tags,
        )
        # An unresolved scope is deliberately not cached: it is the answer a failure
        # produces, and caching it would freeze a transient provider problem for the
        # whole TTL instead of letting the next request try again.
        if scope.reason != REASON_UNRESOLVED:
            await self._write_cache(cache_key, scope.as_dict())
        return scope

    # ------------------------------------------------------------------ #
    # Resolution
    # ------------------------------------------------------------------ #

    async def _resolve_from_tags(
        self,
        *,
        provider: BaseGitProvider,
        project_key: str,
        repository_slug: str,
        version: str,
        tags: list[dict[str, Any]],
    ) -> ReleaseScope:
        """Pick the predecessor using the tag list, verifying where it can."""
        if not tags:
            return ReleaseScope(version=version, reason=REASON_UNRESOLVED)

        version_sha = (
            next(
                (
                    str(tag.get("sha") or "")
                    for tag in tags
                    if str(tag.get("name") or "") == version
                ),
                "",
            )
            or None
        )
        # Pin the released revision when it is known: verifying against the sha
        # keeps a tag that is moved between calls from changing the answer.
        pinned_ref = version_sha or version

        # Releases are asked about before the debug and test tags that share their
        # history, and the release before the tag - its own build first - before either.
        released_before = previous_by_version(version, tags)
        candidates = predecessor_candidates(version, tags)

        budget = probe_budget(len(tags))
        probes = 0
        for candidate in candidates:
            if probes >= budget:
                logger.info(
                    "Release note scope probe budget reached",
                    extra={
                        "project_key": project_key,
                        "repository_slug": repository_slug,
                        "version": version,
                        "probes": probes,
                    },
                )
                break

            sha = str(candidate.get("sha") or "").strip()
            if not sha:
                # without a revision the provider cannot be asked; the tag stays
                # usable as a name-order base but never as a verified one
                continue

            probes += 1
            try:
                is_ancestor = await provider.contains_commit(
                    project_key=project_key,
                    repository_slug=repository_slug,
                    ref=pinned_ref,
                    commit=sha,
                )
            except (AppException, NotImplementedError) as e:
                logger.warning(
                    "Release note scope verification failed - falling back to name order",
                    extra={
                        "project_key": project_key,
                        "repository_slug": repository_slug,
                        "version": version,
                        "candidate": str(candidate.get("name") or ""),
                        "error": str(e),
                    },
                )
                break

            if is_ancestor:
                return ReleaseScope(
                    version=version,
                    previous_ref=str(candidate.get("name") or ""),
                    previous_sha=sha,
                    version_sha=version_sha,
                    source=SOURCE_ANCESTOR,
                    verified=True,
                    reason=REASON_RESOLVED,
                )

        # Nothing could be verified: the version below is still the likelier answer than
        # the name order, which knows nothing of versions at all.
        neighbour = released_before or previous_by_name(version, tags)
        source = SOURCE_NAME_ORDER
        if neighbour is None:
            # Tags a repository names by hand carry no order to read, and the walk
            # found no ancestor: the tag closest to this one keeps the commits a
            # difference instead of a scan of the whole history.
            neighbour = nearest_tag(version, tags)
            source = SOURCE_NEAREST
        if neighbour is not None:
            # a legitimate answer, just not a proven one - the UI warns about it
            return ReleaseScope(
                version=version,
                previous_ref=str(neighbour.get("name") or ""),
                previous_sha=str(neighbour.get("sha") or "") or None,
                version_sha=version_sha,
                source=source,
                verified=False,
                reason=REASON_RESOLVED,
            )

        if version_sha is not None:
            # the released tag is the oldest one this repository has
            return ReleaseScope(
                version=version,
                version_sha=version_sha,
                source=SOURCE_NONE,
                verified=False,
                reason=REASON_FIRST_RELEASE,
            )

        # the released ref is not a tag of this repository (a branch, or a tag
        # that no longer exists): its predecessor is genuinely unknown
        return ReleaseScope(version=version, reason=REASON_UNRESOLVED)

    # ------------------------------------------------------------------ #
    # Cache
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_cache_key(*parts: Any) -> str:
        digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()
        return f"release_note_scope:{CACHE_KEY_VERSION}:{digest[:32]}"

    async def _read_cache(self, cache_key: str) -> dict[str, Any] | None:
        """Read a cached resolution, tolerating cache failures."""
        try:
            return await self.cache.get_json(cache_key)
        except Exception as e:
            logger.warning(
                "Release note scope cache read failed",
                extra={"cache_key": cache_key, "error": str(e)},
            )
            return None

    async def _write_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        """Write a resolution to the cache, tolerating cache failures."""
        try:
            await self.cache.set_json(
                cache_key,
                payload,
                expire=settings.CACHE_TTL_RELEASE_REFS,
            )
        except Exception as e:
            logger.warning(
                "Release note scope cache write failed",
                extra={"cache_key": cache_key, "error": str(e)},
            )
