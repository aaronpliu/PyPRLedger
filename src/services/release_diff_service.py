"""Release diff service.

Compares two release refs (tags / branches / commits) and checks whether
specific commits belong to a target release.

Backed by the git provider abstraction, so Bitbucket Server (compare/commits)
and GitHub Enterprise (compare) are both supported.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from src.core.config import settings
from src.core.git_provider import GitProvider
from src.schemas.release_diff import (
    CommitCheckResult,
    CommitInfo,
    ReleaseCommitCheckRequest,
    ReleaseCommitCheckResponse,
    ReleaseCompareRequest,
    ReleaseCompareResponse,
)
from src.services.git_providers import BaseGitProvider, get_git_provider
from src.utils.log import get_logger
from src.utils.metrics import MetricsCollector
from src.utils.metrics import metrics as metrics_collector
from src.utils.redis import RedisCache


logger = get_logger(__name__)

SHORT_SHA_LENGTH = 7


class ReleaseDiffService:
    """Business logic for release comparison and commit membership checks."""

    def __init__(
        self,
        metrics: MetricsCollector | None = None,
        cache: RedisCache | None = None,
        provider_factory: Callable[[str], BaseGitProvider] = get_git_provider,
    ) -> None:
        self.metrics = metrics or metrics_collector
        self.cache = cache or RedisCache()
        self._provider_factory = provider_factory

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def compare_releases(self, request: ReleaseCompareRequest) -> ReleaseCompareResponse:
        """Compare two releases and report whether the old release is contained.

        Args:
            request: Release compare payload

        Returns:
            ReleaseCompareResponse with missing/added commit breakdown
        """
        provider_name = self._resolve_provider_name(request.git_provider)
        provider = self._provider_factory(provider_name)

        cache_key = self._build_cache_key(
            "compare",
            provider_name,
            request.project_key,
            request.repository_slug,
            request.old_release_ref,
            request.new_release_ref,
            request.old_release_base_ref,
            request.new_release_base_ref,
            request.max_commits,
        )
        cached = await self._read_cache(cache_key)
        if cached is not None:
            self.metrics.increment_cache_hit("release_diff")
            self.metrics.increment_release_diff("compare", provider_name, "cache_hit")
            return self._apply_include_commits(
                ReleaseCompareResponse(**cached), bool(request.include_commits)
            )

        old_commits, old_truncated = await self._fetch_release_commits(
            provider=provider,
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            release_ref=request.old_release_ref,
            base_ref=request.old_release_base_ref,
            max_commits=request.max_commits,
        )
        new_commits, new_truncated = await self._fetch_release_commits(
            provider=provider,
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            release_ref=request.new_release_ref,
            base_ref=request.new_release_base_ref,
            max_commits=request.max_commits,
        )

        behind_ids, behind_truncated = await self._fetch_compare_ids(
            provider=provider,
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            from_ref=request.new_release_ref,
            to_ref=request.old_release_ref,
            max_commits=request.max_commits,
        )
        ahead_ids, ahead_truncated = await self._fetch_compare_ids(
            provider=provider,
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            from_ref=request.old_release_ref,
            to_ref=request.new_release_ref,
            max_commits=request.max_commits,
        )

        missing_commits = [commit for commit in old_commits if commit.id in behind_ids]
        added_commits = [commit for commit in new_commits if commit.id in ahead_ids]

        old_commits_included = not missing_commits
        if request.old_release_ref == request.new_release_ref:
            status = "identical"
        elif old_commits_included:
            status = "included"
        else:
            status = "missing_commits"

        response = ReleaseCompareResponse(
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            git_provider=provider_name,
            old_release_ref=request.old_release_ref,
            new_release_ref=request.new_release_ref,
            old_release_base_ref=request.old_release_base_ref,
            new_release_base_ref=request.new_release_base_ref,
            old_commits_included=old_commits_included,
            status=status,
            summary={
                "old_commit_count": len(old_commits),
                "new_commit_count": len(new_commits),
                "missing_count": len(missing_commits),
                "added_count": len(added_commits),
                "common_count": max(
                    0,
                    len(
                        {commit.id for commit in old_commits}
                        & {commit.id for commit in new_commits}
                    ),
                ),
            },
            missing_commits=missing_commits,
            added_commits=added_commits,
            old_release_commits=old_commits,
            new_release_commits=new_commits,
            truncated=old_truncated or new_truncated or behind_truncated or ahead_truncated,
        )

        await self._write_cache(cache_key, response.model_dump(mode="json"))
        self.metrics.increment_release_diff("compare", provider_name, status)
        logger.info(
            "Release comparison completed",
            extra={
                "project_key": request.project_key,
                "repository_slug": request.repository_slug,
                "old_release_ref": request.old_release_ref,
                "new_release_ref": request.new_release_ref,
                "status": status,
                "missing_count": len(missing_commits),
                "added_count": len(added_commits),
            },
        )

        return self._apply_include_commits(response, bool(request.include_commits))

    async def check_commits(self, request: ReleaseCommitCheckRequest) -> ReleaseCommitCheckResponse:
        """Check whether the given commits belong to the target release.

        Args:
            request: Commit check payload

        Returns:
            ReleaseCommitCheckResponse with per-commit membership results
        """
        provider_name = self._resolve_provider_name(request.git_provider)
        provider = self._provider_factory(provider_name)

        release_commits, truncated = await self._fetch_release_commits(
            provider=provider,
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            release_ref=request.target_release_ref,
            base_ref=request.target_release_base_ref,
            max_commits=request.max_commits,
        )

        lookup = self._build_commit_lookup(release_commits)
        results: list[CommitCheckResult] = []

        for raw_commit in request.commits:
            matched = self._match_commit(raw_commit, lookup)
            if matched is None:
                results.append(
                    CommitCheckResult(
                        commit=raw_commit,
                        included=False,
                        reason="not_found_in_release_scope",
                    )
                )
            else:
                results.append(
                    CommitCheckResult(
                        commit=raw_commit,
                        included=True,
                        matched_id=matched.id,
                        commit_info=matched,
                        reason="matched",
                    )
                )

        included_count = sum(1 for result in results if result.included)
        response = ReleaseCommitCheckResponse(
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            git_provider=provider_name,
            target_release_ref=request.target_release_ref,
            target_release_base_ref=request.target_release_base_ref,
            all_included=included_count == len(results),
            summary={
                "requested": len(results),
                "included_count": included_count,
                "missing_count": len(results) - included_count,
                "release_commit_count": len(release_commits),
            },
            results=results,
            truncated=truncated,
        )

        self.metrics.increment_release_diff(
            "check", provider_name, "all_included" if response.all_included else "missing_commits"
        )
        logger.info(
            "Release commit check completed",
            extra={
                "project_key": request.project_key,
                "repository_slug": request.repository_slug,
                "target_release_ref": request.target_release_ref,
                "requested": len(results),
                "included_count": included_count,
            },
        )

        return response

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _resolve_provider_name(self, git_provider: str | None) -> str:
        """Resolve provider name from request or fall back to configured default."""
        if git_provider:
            if not GitProvider.is_valid(git_provider):
                raise ValueError(
                    f"Unknown git provider '{git_provider}'. "
                    f"Valid providers: {', '.join(sorted(GitProvider.values()))}"
                )
            return git_provider
        return GitProvider.default().value

    async def _fetch_release_commits(
        self,
        provider: BaseGitProvider,
        project_key: str,
        repository_slug: str,
        release_ref: str,
        base_ref: str | None,
        max_commits: int,
    ) -> tuple[list[CommitInfo], bool]:
        """Fetch commits belonging to a release.

        When ``base_ref`` is provided the release scope is
        ``base_ref..release_ref`` (compare/commits). Otherwise every commit
        reachable from ``release_ref`` is returned (capped by ``max_commits``).
        """
        if base_ref:
            raw_commits = await provider.compare_commits(
                project_key=project_key,
                repository_slug=repository_slug,
                from_ref=base_ref,
                to_ref=release_ref,
                limit=max_commits,
            )
            truncated = len(raw_commits) >= max_commits
        else:
            raw_commits = await provider.list_commits_until(
                project_key=project_key,
                repository_slug=repository_slug,
                until_ref=release_ref,
                limit=max_commits,
            )
            truncated = len(raw_commits) >= max_commits

        return [self._normalize_commit(raw) for raw in raw_commits], truncated

    async def _fetch_compare_ids(
        self,
        provider: BaseGitProvider,
        project_key: str,
        repository_slug: str,
        from_ref: str,
        to_ref: str,
        max_commits: int,
    ) -> tuple[set[str], bool]:
        """Return commit ids reachable from ``to_ref`` but not from ``from_ref``."""
        if from_ref == to_ref:
            return set(), False

        raw_commits = await provider.compare_commits(
            project_key=project_key,
            repository_slug=repository_slug,
            from_ref=from_ref,
            to_ref=to_ref,
            limit=max_commits,
        )
        ids = {self._normalize_commit(raw).id for raw in raw_commits}
        return ids, len(raw_commits) >= max_commits

    @staticmethod
    def _normalize_commit(raw: dict[str, Any]) -> CommitInfo:
        """Normalize provider-specific commit payloads into CommitInfo."""
        if "sha" in raw:
            commit = raw.get("commit") or {}
            author = commit.get("author") or {}
            return CommitInfo(
                id=raw.get("sha", ""),
                display_id=raw.get("sha", "")[:SHORT_SHA_LENGTH] or None,
                author_name=author.get("name"),
                author_email=author.get("email"),
                author_timestamp=ReleaseDiffService._to_epoch_ms(author.get("date")),
                message=commit.get("message"),
                url=raw.get("html_url"),
            )

        author = raw.get("author") or {}
        commit_id = raw.get("id", "")
        return CommitInfo(
            id=commit_id,
            display_id=raw.get("displayId") or (commit_id[:SHORT_SHA_LENGTH] or None),
            author_name=author.get("name") or author.get("displayName"),
            author_email=author.get("emailAddress"),
            author_timestamp=raw.get("authorTimestamp"),
            message=raw.get("message"),
            url=raw.get("url"),
        )

    @staticmethod
    def _to_epoch_ms(value: str | None) -> int | None:
        """Convert an ISO-8601 timestamp to epoch milliseconds."""
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return int(parsed.timestamp() * 1000)

    @staticmethod
    def _build_commit_lookup(commits: list[CommitInfo]) -> dict[str, CommitInfo]:
        """Index commits by full sha, display sha and short sha prefixes."""
        lookup: dict[str, CommitInfo] = {}
        for commit in commits:
            candidates = {commit.id.lower()}
            if commit.display_id:
                candidates.add(commit.display_id.lower())
            if len(commit.id) >= SHORT_SHA_LENGTH:
                candidates.add(commit.id.lower()[:SHORT_SHA_LENGTH])
            for candidate in candidates:
                lookup.setdefault(candidate, commit)
        return lookup

    @staticmethod
    def _match_commit(value: str, lookup: dict[str, CommitInfo]) -> CommitInfo | None:
        """Resolve a user supplied commit reference to a release commit."""
        normalized = value.strip().lower()
        if not normalized:
            return None

        exact = lookup.get(normalized)
        if exact is not None:
            return exact

        if len(normalized) < SHORT_SHA_LENGTH:
            return None

        for key, commit in lookup.items():
            if key.startswith(normalized):
                return commit

        return None

    @staticmethod
    def _apply_include_commits(
        response: ReleaseCompareResponse, include_commits: bool
    ) -> ReleaseCompareResponse:
        """Strip commit details from the response when the caller opted out."""
        if include_commits:
            return response

        return response.model_copy(
            update={
                "missing_commits": [],
                "added_commits": [],
                "old_release_commits": [],
                "new_release_commits": [],
            }
        )

    @staticmethod
    def _build_cache_key(operation: str, *parts: Any) -> str:
        """Build a stable cache key for a release diff operation."""
        digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()
        return f"release_diff:{operation}:{digest[:32]}"

    async def _read_cache(self, cache_key: str) -> dict | None:
        """Read a cached response, tolerating cache failures."""
        try:
            return await self.cache.get_json(cache_key)
        except Exception as e:
            logger.warning(
                "Release diff cache read failed",
                extra={"cache_key": cache_key, "error": str(e)},
            )
            return None

    async def _write_cache(self, cache_key: str, payload: dict) -> None:
        """Write a response to the cache, tolerating cache failures."""
        try:
            await self.cache.set_json(cache_key, payload, expire=settings.CACHE_TTL_RELEASE_DIFF)
        except Exception as e:
            logger.warning(
                "Release diff cache write failed",
                extra={"cache_key": cache_key, "error": str(e)},
            )
