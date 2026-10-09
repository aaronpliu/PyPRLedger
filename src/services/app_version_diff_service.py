"""App Diff service.

Compares two or more releases of one application, the application itself among them.

Each release is read from the dependency source - the same one the Release
Dependency Graph draws from - and the releases are placed on their datetime
timeline. Every adjacent pair on that timeline is then compared entry by entry -
the application's own version first, then each dependency it declares: the same
question a repository comparison asks about one repository at two refs, asked
about one entry at two versions.

The application's own version is a row for the same reason it is a row of any
release comparison: a release that moved its version while every dependency
stayed put is a change, and it would otherwise read as a comparison in which
nothing happened.

A dependency that moved is then compared the same way, in the repository it lives
in: a package's versions are the tags it was released under, so they are the two
refs to compare. The dependency record names no repository for its packages - only
names and versions - so where one lives is resolved through the project registry,
and a package that resolves to none, or to several, is reported as such instead of
being left out. Which is the rule of this module applied to a second axis: what
could not be checked has to be as visible as what was.

Two rules decide most of the behaviour: a release the source holds no record for
makes its comparisons unknown rather than empty, and a pair of versions that
cannot be ordered is a change with no direction rather than a guessed upgrade.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.core.config import settings
from src.core.exceptions import DependencyGraphNotFoundException
from src.schemas.app_version_diff import (
    DIRECTION_DOWNGRADE,
    DIRECTION_UPGRADE,
    KIND_APPLICATION,
    KIND_DEPENDENCY,
    STATE_ADDED,
    STATE_CHANGED,
    STATE_REMOVED,
    STATE_UNCHANGED,
    STATES,
    VERDICT_CHANGED,
    VERDICT_IDENTICAL,
    VERDICT_INCOMPLETE,
    AppVersionDiffCode,
    AppVersionDiffInterval,
    AppVersionDiffMove,
    AppVersionDiffPackageComparison,
    AppVersionDiffRelease,
    AppVersionDiffRequest,
    AppVersionDiffResponse,
    AppVersionDiffRow,
)
from src.schemas.release_diff import VERDICT_INCONCLUSIVE, ReleaseCompareRequest
from src.services.dependency_graph_service import DependencyGraphService
from src.services.git_providers import BaseGitProvider, get_git_provider
from src.services.release_diff_service import (
    ReleaseDiffService,
    resolve_provider_name,
    resolve_remote_project_key,
)
from src.utils.log import get_logger
from src.utils.metrics import MetricsCollector
from src.utils.metrics import metrics as metrics_collector
from src.utils.redis import RedisCache


logger = get_logger(__name__)

CACHE_KEY_VERSION = "v1"
CACHE_TYPE = "app_version_diff"

# The application itself is the graph's root, and the dependencies it declares
# are what this comparison is about.
PROJECT_CATEGORY = 0

# How many commits of each direction are carried per pair. The counts are exact
# either way; only the rendered lists are capped, and the payload says so.
CODE_RENDER_LIMIT = 30

# How many dependency comparisons run at once. Each one asks the git provider for
# the commits between two versions, and a release that moved several packages
# should not be waited for one at a time.
PACKAGE_COMPARISON_CONCURRENCY = 4


@dataclass(frozen=True)
class DependencyRepository:
    """Where a package named by the dependency database lives.

    A dependency record names its packages and their versions, never their
    repositories, so where one lives is resolved outside this service - through
    the project registry. Either the coordinates are known, or the reason they are
    not is: a package that resolves to nothing, or to several repositories, has to
    be reportable rather than guessed at.
    """

    project_key: str | None = None
    repository_slug: str | None = None
    git_provider: str | None = None
    reason: str | None = None


# Given a package name out of a dependency record, where it lives.
DependencyRepositoryResolver = Callable[[str], Awaitable[DependencyRepository]]

# A version as an application declares it: an optional `v`, up to three numeric
# components, an optional pre-release, an optional build metadata suffix - and,
# because this project's releases carry one, an optional trailing `_<digits>`
# build number. Anything else - a range, a branch-like label - is left unordered
# rather than guessed at.
VERSION_PATTERN = re.compile(
    r"^[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?(?:_\d+)?$"
)

ParsedVersion = tuple[int, int, int, "tuple[str, ...] | None"]

# Every counter a summary carries: one per state, plus the two directions a
# change can take.
SUMMARY_KEYS: tuple[str, ...] = (*STATES, DIRECTION_UPGRADE, DIRECTION_DOWNGRADE)


# ---------------------------------------------------------------------- #
# Version reading
# ---------------------------------------------------------------------- #


def parse_version(value: str | None) -> ParsedVersion | None:
    """A version read into ordered components, or nothing when it is not one."""
    if value is None:
        return None

    match = VERSION_PATTERN.match(str(value).strip())
    if not match:
        return None

    major, minor, patch, prerelease = match.groups()
    identifiers = tuple(part for part in (prerelease or "").split(".") if part)
    return int(major), int(minor or 0), int(patch or 0), identifiers or None


def version_key(parsed: ParsedVersion) -> tuple[Any, ...]:
    """A sort key that orders versions the way semver precedence does.

    A pre-release sorts before the release it leads to (`1.2.0-rc.0 < 1.2.0`),
    numeric identifiers compare numerically, alphanumeric ones lexically, and a
    shorter identifier list is lower than a longer one that starts the same
    (`1.2.0-rc < 1.2.0-rc.0`).
    """
    major, minor, patch, prerelease = parsed
    if prerelease is None:
        # A release outranks any of its pre-releases.
        pre: tuple[Any, ...] = (1,)
    else:
        pre = (
            0,
            tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in prerelease),
        )
    return (major, minor, patch, pre)


def compare_versions(source: str | None, target: str | None) -> tuple[str, str | None, bool]:
    """What one package did from ``source`` to ``target``.

    Returns the state, the direction (None when there is no direction to state)
    and whether both versions could be ordered. A pair that cannot be ordered is
    reported as changed with no direction - never as an upgrade.
    """
    if source is None and target is None:
        return STATE_UNCHANGED, None, True
    if source is None:
        return STATE_ADDED, None, True
    if target is None:
        return STATE_REMOVED, None, True
    if source == target:
        return STATE_UNCHANGED, None, True

    left = parse_version(source)
    right = parse_version(target)
    if left is None or right is None:
        return STATE_CHANGED, None, False

    left_key = version_key(left)
    right_key = version_key(right)
    if left_key == right_key:
        # `1.0` and `1.0.0` are one version written twice: it changed, but
        # neither direction is true.
        return STATE_CHANGED, None, True

    direction = DIRECTION_UPGRADE if right_key > left_key else DIRECTION_DOWNGRADE
    return STATE_CHANGED, direction, True


def empty_summary() -> dict[str, int]:
    """The counters of one interval or of a whole comparison."""
    return dict.fromkeys(SUMMARY_KEYS, 0)


def package_comparison(
    move: AppVersionDiffMove,
    repository: DependencyRepository,
    code: AppVersionDiffCode,
) -> AppVersionDiffPackageComparison:
    """One dependency's comparison, in the shape the response carries it."""
    return AppVersionDiffPackageComparison(
        name=move.name,
        state=move.state,
        source_version=move.source_version,
        target_version=move.target_version,
        project_key=repository.project_key,
        repository_slug=repository.repository_slug,
        git_provider=repository.git_provider,
        code=code,
    )


def package_not_compared(
    move: AppVersionDiffMove, reason: str
) -> AppVersionDiffPackageComparison:
    """A package there was nothing to compare for, and why.

    It says so in the same place a comparison says how it went, so that what could
    not be checked is as visible as what was - a check that silently skipped a
    package reads as a pass it never earned.
    """
    return package_comparison(
        move,
        DependencyRepository(),
        AppVersionDiffCode(verdict=VERDICT_INCONCLUSIVE, unavailable=reason),
    )


async def _no_dependency_repository(name: str) -> DependencyRepository:
    """The resolver of a caller that has none: no package can be compared."""
    return DependencyRepository(reason="the dependency's repository cannot be resolved here")


# ---------------------------------------------------------------------- #
# Service
# ---------------------------------------------------------------------- #


class AppVersionDiffService:
    """Business logic for comparing the releases of one application."""

    def __init__(
        self,
        metrics: MetricsCollector | None = None,
        cache: RedisCache | None = None,
        graph_service: DependencyGraphService | None = None,
        diff_service: ReleaseDiffService | None = None,
        provider_factory: Callable[[str], BaseGitProvider] = get_git_provider,
    ) -> None:
        self.metrics = metrics or metrics_collector
        self.cache = cache or RedisCache()
        self.graph_service = graph_service or DependencyGraphService(metrics=self.metrics)
        # The code axis is the repository comparison, called rather than rewritten.
        self.diff_service = diff_service or ReleaseDiffService(metrics=self.metrics)
        self._provider_factory = provider_factory

    async def compare(
        self,
        request: AppVersionDiffRequest,
        app_name: str,
        resolve_dependency_repository: DependencyRepositoryResolver | None = None,
    ) -> AppVersionDiffResponse:
        """Compare the requested releases of one application.

        Args:
            request: The repository coordinates, the releases and the refresh flag
            app_name: The application the repository resolved to
            resolve_dependency_repository: Where a package a release moved lives.
                The dependency record names packages and versions, never their
                repositories, so this is what lets a moved package be compared in
                the repository it lives in; without it, packages are reported as
                not compared rather than quietly dropped

        Returns:
            The releases in datetime order, the version matrix, and one comparison
            per adjacent pair - the application's own refs, and then each
            dependency that moved.
        """
        provider_name = resolve_provider_name(request.git_provider)
        cache_key = self._cache_key(request, app_name, provider_name)

        if not request.refresh:
            cached = await self._read_cache(cache_key)
            if cached is not None:
                self.metrics.increment_cache_hit(CACHE_TYPE)
                return AppVersionDiffResponse(**cached)
        self.metrics.increment_cache_miss(CACHE_TYPE)

        reads = await self._read_releases(request, app_name, provider_name)
        release_entries = await self._place_on_timeline(request, reads, provider_name)

        rows = self._build_matrix(release_entries, app_name)
        intervals = self._compare_intervals(release_entries, rows)
        if request.include_code:
            await self._attach_code(request, release_entries, intervals, provider_name)
            await self._attach_dependency_code(
                request,
                intervals,
                provider_name,
                resolve_dependency_repository or _no_dependency_repository,
            )
        response = self._build_response(
            request=request,
            app_name=app_name,
            provider_name=provider_name,
            releases=release_entries,
            rows=rows,
            intervals=intervals,
        )

        await self._write_cache(cache_key, response)
        self.metrics.increment_release_diff("app_compare", provider_name, response.verdict)
        logger.info(
            "Application releases compared",
            extra={
                "app_name": app_name,
                "project_key": request.project_key,
                "repository_slug": request.repository_slug,
                "releases": [entry["ref"] for entry in release_entries],
                "rows": len(rows),
                "verdict": response.verdict,
                "summary": response.summary,
            },
        )
        return response

    # ------------------------------------------------------------------ #
    # Reading the releases
    # ------------------------------------------------------------------ #

    async def _read_releases(
        self, request: AppVersionDiffRequest, app_name: str, provider_name: str
    ) -> list[dict[str, Any]]:
        """Read every selected release, a missing record being an outcome.

        A dependency source that cannot be reached is not an outcome: it is
        raised, so the comparison reports a failure instead of an empty - and
        therefore all-unchanged - result.
        """
        reads: list[dict[str, Any]] = []
        for index, ref in enumerate(request.refs):
            try:
                graph = await self.graph_service.build(
                    app_name=app_name,
                    project_key=request.project_key,
                    repository_slug=request.repository_slug,
                    ref=ref,
                    git_provider=provider_name,
                )
            except DependencyGraphNotFoundException:
                logger.info(
                    "No dependency record for this release",
                    extra={"app_name": app_name, "ref": ref},
                )
                reads.append(
                    {
                        "ref": ref,
                        "index": index,
                        "has_record": False,
                        "declared": {},
                        "app_version": None,
                        "recorded_at": None,
                    }
                )
                continue

            reads.append(
                {
                    "ref": ref,
                    "index": index,
                    "has_record": True,
                    "declared": self._declared_dependencies(graph),
                    # the application's own version, which is the key its record is held under
                    "app_version": str(self._application_node(graph).get("version") or ref),
                    "recorded_at": graph.get("generated_at"),
                }
            )
        return reads

    @staticmethod
    def _application_node(graph: dict[str, Any]) -> dict[str, Any]:
        """The application's own node out of a graph of one release."""
        for node in graph.get("packages") or []:
            if node.get("category") == PROJECT_CATEGORY:
                return node
        return {}

    @classmethod
    def _declared_dependencies(cls, graph: dict[str, Any]) -> dict[str, str]:
        """What the application itself pinned, out of a graph of one release.

        Only the root node's map is read: the packages the source reports further
        down the closure are what the application pulls in, which is a different
        question and deliberately not compared here.
        """
        declared = cls._application_node(graph).get("dependencies") or {}
        return {str(name): str(version) for name, version in declared.items()}

    # ------------------------------------------------------------------ #
    # Placing the releases on their timeline
    # ------------------------------------------------------------------ #

    async def _place_on_timeline(
        self,
        request: AppVersionDiffRequest,
        reads: list[dict[str, Any]],
        provider_name: str,
    ) -> list[dict[str, Any]]:
        """Order the releases by release datetime, never by the order supplied.

        The datetime is the dependency record's own timestamp when there is one,
        otherwise the tag's date as the git provider reports it. A release with
        neither keeps its position among the other such releases, at the end -
        where a branch without a record naturally falls.
        """
        entries: list[dict[str, Any]] = []
        for read in reads:
            recorded = _to_epoch(read["recorded_at"])
            entries.append(
                {
                    **read,
                    "sort_key": recorded,
                    "released_at": str(read["recorded_at"]) if read["recorded_at"] else None,
                }
            )

        if any(entry["sort_key"] is None for entry in entries):
            tag_dates = await self._tag_dates(request, provider_name)
            for entry in entries:
                if entry["sort_key"] is not None:
                    continue
                tag_date = tag_dates.get(entry["ref"])
                if tag_date is None:
                    continue
                entry["sort_key"] = tag_date[0]
                entry["released_at"] = tag_date[1]

        # Dated releases first, in date order; the undated ones keep the order
        # they were chosen in instead of being given a date they do not have.
        return sorted(
            entries,
            key=lambda entry: (
                entry["sort_key"] is None,
                entry["sort_key"] or 0.0,
                entry["index"],
            ),
        )

    async def _tag_dates(
        self, request: AppVersionDiffRequest, provider_name: str
    ) -> dict[str, tuple[float, str]]:
        """Tag dates by tag name, so a release without a record can still be placed.

        Best effort: a provider that cannot be listed leaves the releases it would
        have dated undated, which the ordering already handles.
        """
        try:
            provider = self._provider_factory(provider_name)
            remote_key = resolve_remote_project_key(
                request.project_key, provider_name, request.workspace_slug
            )
            entries = await provider.list_tags_with_commits(remote_key, request.repository_slug)
        except Exception as e:
            logger.warning(
                "Could not read the tag dates, leaving those releases undated",
                extra={
                    "project_key": request.project_key,
                    "repository_slug": request.repository_slug,
                    "error": str(e),
                },
            )
            return {}

        dates: dict[str, tuple[float, str]] = {}
        for entry in entries:
            name = str(entry.get("name") or "").strip()
            moment = _to_epoch_ms(entry.get("date"))
            if not name or moment is None:
                continue
            dates[name] = (moment, datetime.fromtimestamp(moment, tz=UTC).date().isoformat())
        return dates

    # ------------------------------------------------------------------ #
    # The matrix and the comparisons
    # ------------------------------------------------------------------ #

    def _build_matrix(
        self, releases: list[dict[str, Any]], app_name: str
    ) -> list[AppVersionDiffRow]:
        """The application's own version first, then one row per direct dependency.

        The dependency row set is the union of what the releases with records
        declare, so a package only a later release added still has a row - with
        empty cells before it - instead of appearing twice. Nothing is compared
        before some release has a record: until then there is nothing to say.
        """
        rows: list[AppVersionDiffRow] = []
        if not any(release["has_record"] for release in releases):
            return rows

        rows.append(
            AppVersionDiffRow(
                kind=KIND_APPLICATION,
                name=app_name,
                versions=[
                    release["app_version"] if release["has_record"] else None
                    for release in releases
                ],
                moves=[],
            )
        )

        names = {
            name for release in releases if release["has_record"] for name in release["declared"]
        }
        for name in sorted(names, key=lambda name: (name.lower(), name)):
            versions: list[str | None] = [
                release["declared"].get(name) if release["has_record"] else None
                for release in releases
            ]
            rows.append(
                AppVersionDiffRow(kind=KIND_DEPENDENCY, name=name, versions=versions, moves=[])
            )
        return rows

    def _compare_intervals(
        self,
        releases: list[dict[str, Any]],
        rows: list[AppVersionDiffRow],
    ) -> list[AppVersionDiffInterval]:
        """Compare every adjacent pair, and fill each row's moves.

        A pair that involves a release with no record has no moves: what that
        release declared is unknown, so reporting "unchanged" would be a guess.
        The summary counts every row, the application's own included;
        ``dependencies_moved`` is decided over the dependency rows alone, which
        is what the rebuild reading is built on.
        """
        intervals: list[AppVersionDiffInterval] = []

        for boundary in range(len(releases) - 1):
            source = releases[boundary]
            target = releases[boundary + 1]
            complete = bool(source["has_record"] and target["has_record"])
            summary = empty_summary()
            changes: list[AppVersionDiffMove] = []
            dependencies_moved = False

            for row in rows:
                if not complete:
                    row.moves.append(None)
                    continue

                source_version = row.versions[boundary]
                target_version = row.versions[boundary + 1]
                state, direction, orderable = compare_versions(source_version, target_version)
                summary[state] += 1
                if direction:
                    summary[direction] += 1

                move = AppVersionDiffMove(
                    name=row.name,
                    kind=row.kind,
                    source_version=source_version,
                    target_version=target_version,
                    state=state,
                    direction=direction,
                    orderable=orderable,
                )
                row.moves.append(move)
                if state != STATE_UNCHANGED:
                    changes.append(move)
                    if row.kind == KIND_DEPENDENCY:
                        dependencies_moved = True

            intervals.append(
                AppVersionDiffInterval(
                    source_ref=source["ref"],
                    target_ref=target["ref"],
                    complete=complete,
                    summary=summary,
                    dependencies_moved=dependencies_moved,
                    changes=changes,
                )
            )

        return intervals

    async def _attach_code(
        self,
        request: AppVersionDiffRequest,
        releases: list[dict[str, Any]],
        intervals: list[AppVersionDiffInterval],
        provider_name: str,
    ) -> None:
        """Read the commits between every pair that can be compared.

        The refs compared are the ones each release's record names - the
        ``tagOrBranch`` the build was made from, which the graph carries as the
        application's version - rather than the ref the reader picked, which names
        a release the way this page lists it.

        One pair at a time, and a pair that cannot be read is recorded as such
        with the reason. A provider that is down, or that does not know a release
        ref, must not cost the comparison its dependency axis, and must never read
        as a pair that had no commits.
        """
        for boundary, interval in enumerate(intervals):
            if not interval.complete:
                continue
            source_ref = str(releases[boundary]["app_version"])
            target_ref = str(releases[boundary + 1]["app_version"])
            try:
                comparison = await self.diff_service.compare_releases(
                    ReleaseCompareRequest(
                        project_key=request.project_key,
                        repository_slug=request.repository_slug,
                        git_provider=provider_name,
                        workspace_slug=request.workspace_slug,
                        refresh=request.refresh,
                        source_ref=source_ref,
                        target_ref=target_ref,
                        render_limit=CODE_RENDER_LIMIT,
                    )
                )
            except Exception as e:
                logger.warning(
                    "Could not read the commits between two releases",
                    extra={
                        "project_key": request.project_key,
                        "repository_slug": request.repository_slug,
                        "source_ref": source_ref,
                        "target_ref": target_ref,
                        "error": str(e),
                    },
                )
                interval.code = AppVersionDiffCode(verdict=VERDICT_INCONCLUSIVE, unavailable=str(e))
                continue

            interval.code = AppVersionDiffCode(
                verdict=comparison.verdict,
                scan_complete=comparison.scan_complete,
                added_count=comparison.added_count,
                missing_count=comparison.missing_count,
                added_commits=comparison.added_commits,
                missing_commits=comparison.missing_commits,
                truncated=comparison.rendered_truncated,
            )

    async def _attach_dependency_code(
        self,
        request: AppVersionDiffRequest,
        intervals: list[AppVersionDiffInterval],
        provider_name: str,
        resolve_repository: DependencyRepositoryResolver,
    ) -> None:
        """Compare every dependency that moved, in the repository it lives in.

        A package's version is the tag it was released under, so the two versions a
        release moved between are the two refs to compare: the same question a
        repository comparison asks, asked about a package.

        Each of those is a provider request, so they run a few at a time and only
        up to a ceiling. What the ceiling leaves out is reported as not compared,
        which is a different thing from a package that was compared and matched.
        """
        budget = max(settings.APP_DIFF_MAX_PACKAGE_COMPARISONS, 0)
        semaphore = asyncio.Semaphore(PACKAGE_COMPARISON_CONCURRENCY)

        for interval in intervals:
            if not interval.complete:
                continue
            moves = [move for move in interval.changes if move.kind == KIND_DEPENDENCY]
            if not moves:
                continue

            comparable = [move for move in moves if move.state == STATE_CHANGED]
            within_budget = comparable[:budget]
            budget -= len(within_budget)

            async def compare(move: AppVersionDiffMove) -> AppVersionDiffPackageComparison:
                async with semaphore:
                    return await self._compare_package(
                        request, move, provider_name, resolve_repository
                    )

            compared = await asyncio.gather(*(compare(move) for move in within_budget))
            by_name = {entry.name: entry for entry in compared}

            for move in moves:
                if move.name in by_name:
                    interval.packages.append(by_name[move.name])
                    continue
                interval.packages.append(
                    package_not_compared(
                        move,
                        (
                            f"not compared: {len(comparable)} packages moved and the ceiling "
                            f"is {settings.APP_DIFF_MAX_PACKAGE_COMPARISONS}"
                            if move.state == STATE_CHANGED
                            else "only one version is recorded, so there is no pair to compare"
                        ),
                    )
                )

    async def _compare_package(
        self,
        request: AppVersionDiffRequest,
        move: AppVersionDiffMove,
        provider_name: str,
        resolve_repository: DependencyRepositoryResolver,
    ) -> AppVersionDiffPackageComparison:
        """One moved package, compared between the two versions it moved between."""
        repository = await resolve_repository(move.name)
        if repository.reason or not repository.repository_slug:
            return package_not_compared(
                move, repository.reason or f"no repository is known for '{move.name}'"
            )

        # A repository on Cloud is addressed by its workspace, which a dependency
        # record does not name: the comparison is asked for in the workspace the
        # application itself is read in. A package that lives elsewhere answers with
        # an error, and an error is reported as one - never as a package that
        # contains nothing.
        dependency_provider = repository.git_provider or provider_name
        try:
            comparison = await self.diff_service.compare_releases(
                ReleaseCompareRequest(
                    project_key=repository.project_key or "",
                    repository_slug=repository.repository_slug,
                    git_provider=dependency_provider,
                    workspace_slug=request.workspace_slug,
                    refresh=request.refresh,
                    source_ref=str(move.source_version),
                    target_ref=str(move.target_version),
                    render_limit=CODE_RENDER_LIMIT,
                )
            )
        except Exception as e:
            logger.warning(
                "Could not compare two versions of a dependency",
                extra={
                    "package": move.name,
                    "project_key": repository.project_key,
                    "repository_slug": repository.repository_slug,
                    "source_version": move.source_version,
                    "target_version": move.target_version,
                    "error": str(e),
                },
            )
            return package_comparison(
                move,
                repository,
                AppVersionDiffCode(verdict=VERDICT_INCONCLUSIVE, unavailable=str(e)),
            )

        return package_comparison(
            move,
            repository,
            AppVersionDiffCode(
                verdict=comparison.verdict,
                scan_complete=comparison.scan_complete,
                added_count=comparison.added_count,
                missing_count=comparison.missing_count,
                added_commits=comparison.added_commits,
                missing_commits=comparison.missing_commits,
                truncated=comparison.rendered_truncated,
            ),
        )

    def _build_response(
        self,
        *,
        request: AppVersionDiffRequest,
        app_name: str,
        provider_name: str,
        releases: list[dict[str, Any]],
        rows: list[AppVersionDiffRow],
        intervals: list[AppVersionDiffInterval],
    ) -> AppVersionDiffResponse:
        """Assemble the answer, including the one part that must never be faked."""
        incomplete = any(not release["has_record"] for release in releases)

        # Totals come from the intervals that could be compared. An incomplete
        # interval contributes nothing, because nothing is what is known about it.
        summary = empty_summary()
        for interval in intervals:
            if not interval.complete:
                continue
            for state in summary:
                summary[state] += interval.summary.get(state, 0)

        moved = any(summary[state] for state in (STATE_CHANGED, STATE_ADDED, STATE_REMOVED))
        if incomplete:
            verdict = VERDICT_INCOMPLETE
        elif moved:
            verdict = VERDICT_CHANGED
        else:
            verdict = VERDICT_IDENTICAL

        return AppVersionDiffResponse(
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            app_name=app_name,
            git_provider=provider_name,
            releases=[
                AppVersionDiffRelease(
                    ref=release["ref"],
                    released_at=release["released_at"],
                    has_record=release["has_record"],
                )
                for release in releases
            ],
            verdict=verdict,
            summary=summary,
            rows=rows,
            intervals=intervals,
        )

    # ------------------------------------------------------------------ #
    # Cache
    # ------------------------------------------------------------------ #

    def _cache_key(self, request: AppVersionDiffRequest, app_name: str, provider_name: str) -> str:
        """Keyed by the set of releases, so the order they were chosen in is not a key.

        Whether the code axis was read is part of the key: a comparison answered
        without the commits is not the answer to a request that asked for them.
        """
        parts = [
            app_name,
            request.project_key,
            request.repository_slug,
            provider_name,
            str(request.include_code),
            *sorted(request.refs),
        ]
        digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()
        return f"{CACHE_TYPE}:{CACHE_KEY_VERSION}:{digest[:32]}"

    async def _read_cache(self, cache_key: str) -> dict[str, Any] | None:
        try:
            return await self.cache.get_json(cache_key)
        except Exception as e:
            logger.warning(
                "App Diff cache read failed",
                extra={"cache_key": cache_key, "error": str(e)},
            )
            return None

    async def _write_cache(self, cache_key: str, response: AppVersionDiffResponse) -> None:
        try:
            await self.cache.set_json(
                cache_key,
                response.model_dump(mode="json"),
                expire=settings.CACHE_TTL_DEPENDENCY_GRAPH,
            )
        except Exception as e:
            logger.warning(
                "App Diff cache write failed",
                extra={"cache_key": cache_key, "error": str(e)},
            )


# ---------------------------------------------------------------------- #
# Datetime helpers
# ---------------------------------------------------------------------- #


def _to_epoch(value: Any) -> float | None:
    """A record's timestamp as an epoch, or nothing when it is not one."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return _to_epoch_ms(value)
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.timestamp()


def _to_epoch_ms(value: Any) -> float | None:
    """An epoch-millisecond timestamp as an epoch, or nothing."""
    if value is None:
        return None
    try:
        milliseconds = int(value)
    except (TypeError, ValueError):
        return None
    return milliseconds / 1000.0
