"""Release note scope resolution.

Answers one question on the server: which release ref precedes a given tag? With
that answer the commits a tag released are a provider *difference*
(``previous..version``) instead of an enumeration of everything reachable from
the tag, which is what used to cap out on a repository with years of history.

The predecessor is resolved in a defined order - an explicit ref supplied by the
caller, a verified ancestor (one provider call per candidate), the previous tag
in version-aware name order, or nothing at all - and the result carries how it was
obtained, so the UI can state the scope instead of guessing it from a page-sized
list of tags.
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

# Bumped when the Bitbucket Server comparison direction was corrected: the
# ancestry probes behind a cached resolution used the reversed direction too.
CACHE_KEY_VERSION = "v2"


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

        budget = probe_budget(len(tags))
        probes = 0
        for candidate in order_candidates(
            [tag for tag in tags if str(tag.get("name") or "") != version]
        ):
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

        neighbour = previous_by_name(version, tags)
        if neighbour is not None:
            # a legitimate answer, just not a proven one - the UI warns about it
            return ReleaseScope(
                version=version,
                previous_ref=str(neighbour.get("name") or ""),
                previous_sha=str(neighbour.get("sha") or "") or None,
                version_sha=version_sha,
                source=SOURCE_NAME_ORDER,
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
