"""The aggregate release note: one note for a release and the packages it moved.

A release note for an application is incomplete when the application pins
packages: the app's own commits tell half the story, and each pinned package
that moved carries the rest. This service assembles both halves into one
document.

How it reads:

1. **Graph span diff** - ``DependencyGraphService.build`` answers "what does
   this ref pin" for both refs; a dict comparison classifies every package as
   upgraded, added, removed or unchanged. No provider is touched here.
2. **Scope** - only the packages the application *declares* (its workspace
   pins) are compared commit by commit. The transitive closure is summarized
   as the unchanged list, because a change two levels down says nothing about
   this release unless the application pins it.
3. **Resolution** - a package name is a name in the project registry;
   ``find_dependency_repository`` answers with the registration or with the
   reason there is none. "Cannot say" stays legible in the note - it is never
   read as a package that contains what it should.
4. **Per-package comparison** - the same ``ReleaseDiffService.compare_releases``
   the release pages use, source version → target version, run in parallel and
   cached. A provider failure on one package is that package's ``failed`` entry;
   it never takes the note down.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import GitServiceException
from src.schemas.aggregate_release_note import (
    AggregatePackageEntry,
    AggregatePackageRepository,
    AggregateReleaseNoteRequest,
    AggregateReleaseNoteResponse,
    AggregateReleaseNoteSummary,
)
from src.schemas.release_diff import ReleaseCompareRequest, ReleaseCompareResponse
from src.services.dependency_graph_service import (
    PROJECT,
    WORKSPACE,
    DependencyGraphService,
)
from src.services.project_registry_service import ProjectRegistryService
from src.services.release_diff_service import ReleaseDiffService
from src.utils.log import get_logger
from src.utils.metrics import metrics as metrics_collector


logger = get_logger(__name__)


class AggregateReleaseNoteService:
    """Business logic for the combined application + packages release note."""

    def __init__(
        self,
        graph: DependencyGraphService | None = None,
        diff: ReleaseDiffService | None = None,
        registry: ProjectRegistryService | None = None,
        metrics: Any = metrics_collector,
    ) -> None:
        self.graph = graph or DependencyGraphService()
        self.diff = diff or ReleaseDiffService()
        self.registry = registry or ProjectRegistryService()
        self.metrics = metrics

    async def build(
        self, request: AggregateReleaseNoteRequest, db: AsyncSession
    ) -> AggregateReleaseNoteResponse:
        """Assemble the note for one application version span.

        Args:
            request: The application coordinates and the two refs of the span
            db: Database session for the registry lookups

        Returns:
            The application's comparison, one entry per moved package, and the
            unchanged summary
        """
        app_name = request.app_name or await self.registry.get_dependency_app_name(
            request.project_key, request.repository_slug, db
        )

        graph_args = {
            "app_name": app_name,
            "project_key": request.project_key,
            "repository_slug": request.repository_slug,
            "git_provider": request.git_provider,
        }
        graph_source, graph_target = await asyncio.gather(
            self.graph.build(ref=request.source_ref, **graph_args),
            self.graph.build(ref=request.target_ref, **graph_args),
        )

        old_versions = self._version_map(graph_source)
        new_versions = self._version_map(graph_target)
        pinned = self._pinned_names(graph_source, graph_target)

        unchanged_packages = sorted(
            f"{name}@{version}"
            for name, version in new_versions.items()
            if name != app_name
            and version
            and name not in pinned
            and old_versions.get(name) == version
        )

        moved = self._classify(app_name, pinned, old_versions, new_versions)

        # resolution is a database walk: sequential by design, so one session
        # serves every lookup
        entries = []
        for name, change, from_version, to_version, is_pinned in moved:
            entry = await self._resolve_package(
                request, db, name, change, from_version, to_version, is_pinned
            )
            entries.append(entry)

        compared = [entry for entry in entries if entry.status == "compared"]
        # the comparisons are provider calls with their own caches: they fan out
        if compared:
            await asyncio.gather(*(self._compare_package(request, entry) for entry in compared))

        application = await self._compare_application(request)

        summary = AggregateReleaseNoteSummary(
            packages_changed=len(entries),
            packages_compared=sum(1 for entry in entries if entry.status == "compared"),
            packages_skipped=sum(1 for entry in entries if entry.status == "skipped"),
            packages_failed=sum(1 for entry in entries if entry.status == "failed"),
            app_commits=len(application.added_commits),
            package_commits=sum(
                len(entry.comparison.added_commits)
                for entry in entries
                if entry.comparison is not None
            ),
        )
        self.metrics.increment_release_diff("aggregate_note", request.git_provider or "default", "built")

        return AggregateReleaseNoteResponse(
            app_name=app_name,
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            git_provider=request.git_provider,
            source_ref=request.source_ref,
            target_ref=request.target_ref,
            application=application,
            packages=entries,
            unchanged_packages=unchanged_packages,
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    # Graph reading
    # ------------------------------------------------------------------ #

    def _version_map(self, graph_payload: dict[str, Any]) -> dict[str, str]:
        """``{package name: version}`` of one ref, the app node excluded."""
        return {
            str(entry["id"]): str(entry.get("version") or "")
            for entry in graph_payload.get("packages", [])
            if entry.get("category") != PROJECT
        }

    def _pinned_names(self, graph_source: dict[str, Any], graph_target: dict[str, Any]) -> set[str]:
        """The packages either version of the application declares (the scope)."""
        pinned: set[str] = set()
        for payload in (graph_source, graph_target):
            for entry in payload.get("packages", []):
                if entry.get("category") == WORKSPACE:
                    pinned.add(str(entry["id"]))
        return pinned

    def _classify(
        self,
        app_name: str,
        pinned: set[str],
        old_versions: dict[str, str],
        new_versions: dict[str, str],
    ) -> list[tuple[str, str, str, str, bool]]:
        """Every package that moved, as ``(name, change, from, to, pinned)`` tuples.

        Moved-but-unpinned packages ride along as skipped entries: they are
        part of what this release carries, and a note that silently drops them
        would read as if the closure had not changed at all.
        """
        moved: list[tuple[str, str, str, str, bool]] = []
        for name in sorted((set(old_versions) | set(new_versions)) - {app_name}):
            from_version = old_versions.get(name, "")
            to_version = new_versions.get(name, "")
            if from_version == to_version:
                continue  # held at the same version: the unchanged summary covers it
            if not from_version:
                change = "added"
            elif not to_version:
                change = "removed"
            else:
                change = "upgraded"
            moved.append((name, change, from_version, to_version, name in pinned))
        return moved

    # ------------------------------------------------------------------ #
    # Package entries
    # ------------------------------------------------------------------ #

    async def _resolve_package(
        self,
        request: AggregateReleaseNoteRequest,
        db: AsyncSession,
        name: str,
        change: str,
        from_version: str,
        to_version: str,
        is_pinned: bool,
    ) -> AggregatePackageEntry:
        """Resolve one moved package to its repository, or say why not."""
        entry = AggregatePackageEntry(
            name=name, change=change, from_version=from_version, to_version=to_version, status="skipped"
        )

        if not is_pinned:
            entry.reason = "the application does not pin this package (transitive dependency)"
            return entry
        if change == "removed":
            entry.reason = f"the package is no longer part of {request.target_ref}"
            return entry
        if not from_version:
            entry.reason = f"the package was not part of {request.source_ref}"
            return entry

        registration, reason = await self.registry.find_dependency_repository(
            name, preferred_project_key=request.project_key, db=db
        )
        if registration is None:
            entry.reason = reason
            return entry

        entry.repository = AggregatePackageRepository(
            project_key=registration.project_key,
            repository_slug=registration.repository_slug,
            git_provider=registration.git_provider,
        )
        entry.status = "compared"
        return entry

    async def _compare_package(
        self, request: AggregateReleaseNoteRequest, entry: AggregatePackageEntry
    ) -> None:
        """Fill one package's comparison in place; a failure is its status."""
        assert entry.repository is not None  # only compared entries arrive here
        try:
            entry.comparison = await self.diff.compare_releases(
                ReleaseCompareRequest(
                    project_key=entry.repository.project_key,
                    repository_slug=entry.repository.repository_slug,
                    git_provider=entry.repository.git_provider,
                    source_ref=entry.from_version,
                    target_ref=entry.to_version,
                    include_commits=request.include_commits,
                    refresh=request.refresh,
                )
            )
        except GitServiceException as exc:
            entry.status = "failed"
            entry.reason = str(getattr(exc, "detail", None) or exc)
            logger.warning(
                "Package comparison failed",
                extra={
                    "package": entry.name,
                    "from_version": entry.from_version,
                    "to_version": entry.to_version,
                    "detail": entry.reason,
                },
            )

    async def _compare_application(self, request: AggregateReleaseNoteRequest) -> ReleaseCompareResponse:
        """The application's own half of the note, the ordinary comparison."""
        return await self.diff.compare_releases(
            ReleaseCompareRequest(
                project_key=request.project_key,
                repository_slug=request.repository_slug,
                git_provider=request.git_provider,
                source_ref=request.source_ref,
                target_ref=request.target_ref,
                include_commits=request.include_commits,
                refresh=request.refresh,
            )
        )
