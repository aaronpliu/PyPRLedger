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
    VERDICT_CONTAINED,
    VERDICT_INCONCLUSIVE,
    VERDICT_MISSING,
    CommitCheckResult,
    CommitInfo,
    ReleaseCommitCheckRequest,
    ReleaseCommitCheckResponse,
    ReleaseCompareRequest,
    ReleaseCompareResponse,
    ReleaseDiffRepository,
    ReleaseRefsRequest,
    ReleaseRefsResponse,
)
from src.services.git_providers import BaseGitProvider, get_git_provider
from src.utils.log import get_logger
from src.utils.metrics import MetricsCollector
from src.utils.metrics import metrics as metrics_collector
from src.utils.redis import RedisCache


logger = get_logger(__name__)

SHORT_SHA_LENGTH = 7

# Bumped whenever the meaning of a cached response changes. Entries written by the
# previous implementation (which derived "missing" by intersecting two capped
# commit sets) must never be served as if they carried a trustworthy verdict.
# "v3" also discards entries produced while the Bitbucket Server comparison ran
# in the reversed direction.
CACHE_KEY_VERSION = "v3"


def resolve_remote_project_key(
    project_key: str,
    provider_name: str,
    workspace_slug: str | None = None,
) -> str:
    """Resolve the identifier used to address the project/repository remotely.

    Bitbucket Cloud addresses repositories by workspace, while Bitbucket Server
    and GitHub Enterprise use the project key / organization.
    """
    if provider_name != GitProvider.BITBUCKET_CLOUD.value:
        return project_key
    workspace = (workspace_slug or "").strip()
    if not workspace or workspace == project_key:
        return project_key
    return workspace


def resolve_provider_name(git_provider: str | None) -> str:
    """Resolve a provider name from a request value or the configured default."""
    if git_provider:
        if not GitProvider.is_valid(git_provider):
            raise ValueError(
                f"Unknown git provider '{git_provider}'. "
                f"Valid providers: {', '.join(sorted(GitProvider.values()))}"
            )
        return git_provider
    return GitProvider.default().value


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

    async def compare_releases(
        self,
        request: ReleaseCompareRequest,
    ) -> ReleaseCompareResponse:
        """Compare two releases: is the source contained, and what does the target add?

        Both answers are provider differences - ``source \\ target`` for the verdict
        and ``target \\ source`` for the additions - which are small by construction,
        so neither depends on how much history the repository holds and neither walks
        a release listing. One optional baseline narrows both directions; the commit
        lists are rendered material and never decide the verdict.

        Args:
            request: Release compare payload, its optional baseline included

        Returns:
            ReleaseCompareResponse with the verdict plus the missing and added commits
        """
        provider_name = self._resolve_provider_name(request.git_provider)
        provider = self._provider_factory(provider_name)
        remote_key = self._remote_project_key(request, provider_name)

        # The baseline belongs to this comparison: a repository holds several
        # release lines, and each line forks from its own point
        effective_baseline = request.baseline_ref

        cache_key = self._build_cache_key(
            "compare",
            provider_name,
            remote_key,
            request.repository_slug,
            request.source_ref,
            request.target_ref,
            effective_baseline,
            request.scan_limit,
            request.render_limit,
            bool(request.include_commits),
        )
        cached = None if request.refresh else await self._read_cache(cache_key)
        if cached is not None:
            self.metrics.increment_cache_hit("release_diff")
            self.metrics.increment_release_diff("compare", provider_name, "cache_hit")
            return self._apply_include_commits(
                ReleaseCompareResponse(**cached), bool(request.include_commits)
            )

        # The containment answer comes from the provider difference in the missing
        # direction: shared history cancels out, so it is enumerated completely or
        # explicitly reported as inconclusive - never inferred from a capped listing.
        missing_raw, missing_complete = await self._scan_release_difference(
            provider=provider,
            project_key=remote_key,
            repository_slug=request.repository_slug,
            source_ref=request.source_ref,
            target_ref=request.target_ref,
            scan_limit=request.scan_limit,
        )
        added_raw, added_complete = await self._scan_release_difference(
            provider=provider,
            project_key=remote_key,
            repository_slug=request.repository_slug,
            source_ref=request.target_ref,
            target_ref=request.source_ref,
            scan_limit=request.scan_limit,
        )

        # One baseline narrows both directions: it drops the commits that already
        # existed at the starting point, which is what "the work this line did since
        # the fork point" means.
        missing_raw, missing_filtered = await self._filter_by_base(
            provider=provider,
            project_key=remote_key,
            repository_slug=request.repository_slug,
            commits=missing_raw,
            base_ref=effective_baseline,
        )
        added_raw, added_filtered = await self._filter_by_base(
            provider=provider,
            project_key=remote_key,
            repository_slug=request.repository_slug,
            commits=added_raw,
            base_ref=effective_baseline,
        )

        if request.source_ref.strip() == request.target_ref.strip():
            verdict = VERDICT_CONTAINED
        elif not missing_complete:
            # never claim a pass from an incomplete scan
            verdict = VERDICT_INCONCLUSIVE
        elif missing_raw:
            verdict = VERDICT_MISSING
        else:
            verdict = VERDICT_CONTAINED

        render_limit = request.render_limit
        missing_commits = [self._normalize_commit(raw) for raw in missing_raw[:render_limit]]
        added_commits = [self._normalize_commit(raw) for raw in added_raw[:render_limit]]

        response = ReleaseCompareResponse(
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            git_provider=provider_name,
            source_ref=request.source_ref,
            target_ref=request.target_ref,
            baseline_ref=effective_baseline,
            narrowed=bool(effective_baseline),
            verdict=verdict,
            scan_complete=missing_complete,
            scan_limit=request.scan_limit,
            filtered_by_baseline_count=missing_filtered + added_filtered,
            missing_count=len(missing_raw),
            missing_commits=missing_commits,
            added_count=len(added_raw),
            added_commits=added_commits,
            added_complete=added_complete,
            rendered_truncated=len(missing_raw) > len(missing_commits)
            or len(added_raw) > len(added_commits),
        )

        await self._write_cache(cache_key, response.model_dump(mode="json"))
        self.metrics.increment_release_diff("compare", provider_name, verdict)
        logger.info(
            "Release comparison completed",
            extra={
                "project_key": request.project_key,
                "repository_slug": request.repository_slug,
                "source_ref": request.source_ref,
                "target_ref": request.target_ref,
                "verdict": verdict,
                "missing_count": len(missing_raw),
                "added_count": len(added_raw),
                "baseline_ref": effective_baseline,
            },
        )

        return self._apply_include_commits(response, bool(request.include_commits))

    async def list_refs(self, request: ReleaseRefsRequest) -> ReleaseRefsResponse:
        """List the tags and branches of a repository.

        Used by the UI to suggest release refs - users can still type any ref
        (tag, branch or commit sha) that is not part of the list.

        Args:
            request: Ref listing payload

        Returns:
            ReleaseRefsResponse with tag and branch names
        """
        provider_name = self._resolve_provider_name(request.git_provider)
        provider = self._provider_factory(provider_name)
        remote_key = self._remote_project_key(request, provider_name)

        cache_key = self._build_cache_key(
            "refs",
            provider_name,
            remote_key,
            request.repository_slug,
            request.limit,
        )
        # An explicit refresh must observe tags / branches created on the git side
        cached = None if request.refresh else await self._read_cache(cache_key)
        if cached is not None:
            self.metrics.increment_cache_hit("release_diff")
            self.metrics.increment_release_diff("refs", provider_name, "cache_hit")
            response = ReleaseRefsResponse(**cached)
            # A payload written by an older revision may hold repeated refs, which
            # would render one identical row per occurrence in the UI
            response.tags = self._clean_refs(response.tags)
            response.branches = self._clean_refs(response.branches)
            return response

        raw_refs = await provider.list_refs(
            project_key=remote_key,
            repository_slug=request.repository_slug,
            limit=request.limit,
        )

        response = ReleaseRefsResponse(
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            git_provider=provider_name,
            tags=self._clean_refs(raw_refs.get("tags")),
            branches=self._clean_refs(raw_refs.get("branches")),
        )

        await self._write_cache(
            cache_key,
            response.model_dump(mode="json"),
            ttl=settings.CACHE_TTL_RELEASE_REFS,
        )
        self.metrics.increment_release_diff("refs", provider_name, "success")
        logger.info(
            "Release refs listed",
            extra={
                "project_key": request.project_key,
                "repository_slug": request.repository_slug,
                "tag_count": len(response.tags),
                "branch_count": len(response.branches),
            },
        )

        return response

    async def check_commits(self, request: ReleaseCommitCheckRequest) -> ReleaseCommitCheckResponse:
        """Check whether the given commits belong to the target release.

        Each commit is answered by the provider against the target ref (and, when a
        release base ref is supplied, against that base as well), so the verdict is
        exact however large the release is. The commit listing of the release is
        only used to attach details to the matches.

        Args:
            request: Commit check payload

        Returns:
            ReleaseCommitCheckResponse with per-commit membership results
        """
        provider_name = self._resolve_provider_name(request.git_provider)
        provider = self._provider_factory(provider_name)
        remote_key = self._remote_project_key(request, provider_name)

        release_commits, truncated = await self._fetch_release_commits(
            provider=provider,
            project_key=remote_key,
            repository_slug=request.repository_slug,
            release_ref=request.target_release_ref,
            base_ref=request.target_release_base_ref,
            max_commits=request.max_commits,
        )

        lookup = self._build_commit_lookup(release_commits)
        base_ref = (request.target_release_base_ref or "").strip() or None
        results: list[CommitCheckResult] = []

        for raw_commit in request.commits:
            # The listing above only enriches the answer. Membership is asked from the
            # provider, so a commit that fell outside a capped listing is still answered
            # correctly instead of being reported as missing.
            matched = self._match_commit(raw_commit, lookup)
            candidate = matched.id if matched else raw_commit.strip()

            contained = matched is not None or await provider.contains_commit(
                project_key=remote_key,
                repository_slug=request.repository_slug,
                ref=request.target_release_ref,
                commit=candidate,
            )
            if not contained:
                results.append(
                    CommitCheckResult(
                        commit=raw_commit,
                        included=False,
                        reason="not_reachable_from_target",
                    )
                )
                continue

            if base_ref and await provider.contains_commit(
                project_key=remote_key,
                repository_slug=request.repository_slug,
                ref=base_ref,
                commit=candidate,
            ):
                results.append(
                    CommitCheckResult(
                        commit=raw_commit,
                        included=False,
                        matched_id=matched.id if matched else None,
                        commit_info=matched,
                        reason="excluded_by_release_base",
                    )
                )
                continue

            results.append(
                CommitCheckResult(
                    commit=raw_commit,
                    included=True,
                    matched_id=matched.id if matched else None,
                    commit_info=matched,
                    reason="matched",
                )
            )

        included_count = sum(1 for result in results if result.included)
        all_included = included_count == len(results)
        response = ReleaseCommitCheckResponse(
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            git_provider=provider_name,
            target_release_ref=request.target_release_ref,
            target_release_base_ref=request.target_release_base_ref,
            all_included=all_included,
            verdict=VERDICT_CONTAINED if all_included else VERDICT_MISSING,
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

    async def list_release_commits(
        self,
        *,
        project_key: str,
        repository_slug: str,
        ref: str,
        git_provider: str | None = None,
        workspace_slug: str | None = None,
        limit: int = 500,
    ) -> tuple[list[CommitInfo], bool]:
        """Return every commit reachable from ``ref`` (newest first).

        Used to draft release notes for a version that has no previous version to
        compare against.

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            ref: Tag, branch or commit the release is built from
            git_provider: Optional provider override
            workspace_slug: Optional Bitbucket Cloud workspace
            limit: Maximum number of commits returned

        Returns:
            Tuple of normalized commits and whether the result was truncated.
        """
        provider_name = self._resolve_provider_name(git_provider)
        provider = self._provider_factory(provider_name)
        request = ReleaseDiffRepository(
            project_key=project_key,
            repository_slug=repository_slug,
            git_provider=git_provider,
            workspace_slug=workspace_slug,
        )
        remote_key = self._remote_project_key(request, provider_name)

        return await self._fetch_release_commits(
            provider=provider,
            project_key=remote_key,
            repository_slug=repository_slug,
            release_ref=ref,
            base_ref=None,
            max_commits=limit,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _remote_project_key(request: ReleaseDiffRepository, provider_name: str) -> str:
        """Resolve the identifier used to address the repository remotely.

        When the request carries a ``workspace_slug`` and the provider is Cloud,
        the workspace is used for the remote calls while ``project_key`` stays the
        business key echoed back in the response.
        """
        return resolve_remote_project_key(
            request.project_key, provider_name, request.workspace_slug
        )

    def _resolve_provider_name(self, git_provider: str | None) -> str:
        """Resolve provider name from request or fall back to configured default."""
        return resolve_provider_name(git_provider)

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

    async def _scan_release_difference(
        self,
        provider: BaseGitProvider,
        project_key: str,
        repository_slug: str,
        *,
        source_ref: str,
        target_ref: str,
        scan_limit: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Enumerate the commits the target release is missing.

        ``source \\ target`` is small by construction - the history both releases
        share cancels out, so only the work that never reached the target remains.
        That is what makes a complete enumeration possible (and what lets the
        caller be told when it was not possible).

        Returns:
            Tuple of (raw commits, complete).
        """
        if source_ref.strip() == target_ref.strip():
            return [], True

        return await provider.compare_commits_complete(
            project_key=project_key,
            repository_slug=repository_slug,
            from_ref=target_ref,
            to_ref=source_ref,
            limit=scan_limit,
        )

    async def _filter_by_base(
        self,
        provider: BaseGitProvider,
        project_key: str,
        repository_slug: str,
        commits: list[dict[str, Any]],
        *,
        base_ref: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Drop difference commits that already existed at ``base_ref``.

        A baseline narrows the answer to the release's own work (for example the
        work of a maintenance line since the fork point). Membership of the base is
        answered by the provider per commit, which stays exact on any repository
        size - and the number of candidates is the number of missing commits, not
        the size of a release.

        Returns:
            Tuple of (kept commits, number of commits filtered out).
        """
        base = (base_ref or "").strip()
        if not base or not commits:
            return list(commits), 0

        kept: list[dict[str, Any]] = []
        filtered = 0
        for raw in commits:
            commit_id = self._normalize_commit(raw).id
            if not commit_id:
                continue
            if await provider.contains_commit(
                project_key=project_key,
                repository_slug=repository_slug,
                ref=base,
                commit=commit_id,
            ):
                filtered += 1
                continue
            kept.append(raw)

        return kept, filtered

    @staticmethod
    def _clean_refs(values: list[str] | None) -> list[str]:
        """Trim ref names and drop duplicates while preserving provider order."""
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values or []:
            name = str(value).strip()
            if name and name not in seen:
                seen.add(name)
                cleaned.append(name)
        return cleaned

    @staticmethod
    def _normalize_commit(raw: dict[str, Any]) -> CommitInfo:
        """Normalize provider-specific commit payloads into CommitInfo."""
        if "sha" in raw:
            # GitHub: the commit author is in commit.author, the linked account in author
            commit = raw.get("commit") or {}
            author = commit.get("author") or {}
            user = raw.get("author") or {}
            return CommitInfo(
                id=raw.get("sha", ""),
                display_id=raw.get("sha", "")[:SHORT_SHA_LENGTH] or None,
                author_name=author.get("name") or user.get("login"),
                author_username=user.get("login"),
                author_url=user.get("html_url"),
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
            author_name=author.get("displayName") or author.get("name"),
            author_username=ReleaseDiffService._author_username(author),
            author_email=author.get("emailAddress"),
            author_timestamp=raw.get("authorTimestamp"),
            message=raw.get("message"),
            url=raw.get("url"),
        )

    @staticmethod
    def _author_username(author: dict[str, Any]) -> str | None:
        """Provider account of a Bitbucket style commit author, when there is one.

        Bitbucket Server reports the account slug in ``name`` while the display name
        lives in ``displayName``; the Cloud adapter translates the Cloud user object
        into the same shape and may state the account explicitly.
        """
        explicit = author.get("username") or author.get("nickname")
        if explicit:
            return str(explicit)

        name = author.get("name")
        # a slug never contains whitespace, a display name usually does
        if isinstance(name, str) and name.strip() and " " not in name.strip():
            return name.strip()
        return None

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
        """Strip commit details from the response when the caller opted out.

        The verdict and the counts are untouched: only the rendered lists are dropped.
        """
        if include_commits:
            return response

        return response.model_copy(update={"missing_commits": [], "added_commits": []})

    @staticmethod
    def _build_cache_key(operation: str, *parts: Any) -> str:
        """Build a stable cache key for a release diff operation.

        The key carries a version segment so responses computed by an older
        implementation are never replayed with a different meaning.
        """
        digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()
        return f"release_diff:{CACHE_KEY_VERSION}:{operation}:{digest[:32]}"

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

    async def _write_cache(self, cache_key: str, payload: dict, ttl: int | None = None) -> None:
        """Write a response to the cache, tolerating cache failures."""
        try:
            await self.cache.set_json(
                cache_key,
                payload,
                expire=ttl if ttl is not None else settings.CACHE_TTL_RELEASE_DIFF,
            )
        except Exception as e:
            logger.warning(
                "Release diff cache write failed",
                extra={"cache_key": cache_key, "error": str(e)},
            )
