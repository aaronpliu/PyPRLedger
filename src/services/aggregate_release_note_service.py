"""The aggregate release note: one note for a release and the packages it moved.

A release note for an application is incomplete when the application carries
packages: the app's own commits tell half the story, and each package that
moved during the release carries the rest. This service assembles both halves
into one document - without asking the dependency database for anything.

How it reads:

1. **Packages** - the project registry answers "what does this application
   carry": the registrations grouped under the application's name that an
   administrator marked as packages. The database session serves every lookup,
   sequential by design.
2. **Versions** - a package's versions are the tags it was released under, so
   ``list_tags_with_commits`` reads them with the commit each points at, for
   the application and for every package. Nothing is guessed: what the
   provider holds is what the note works with.
3. **The span** - the application's two refs are placed on their tag dates,
   and each package's ``from`` and ``to`` are the versions it had released by
   each end of the span. A package that released nothing in between did not
   move; one that released its first version in the span was added by it.
4. **Per-package comparison** - the same ``ReleaseDiffService.compare_releases``
   the release pages use, source version → target version, run in parallel and
   cached. A provider failure on one package is that package's ``failed``
   entry; it never takes the note down.

What cannot be placed stays legible: an undated span ref, a package without
tags, a tag listing the provider would not give - each is a ``skipped`` entry
with its reason, never a silent hole in the note.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
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
from src.services.git_providers import BaseGitProvider, get_git_provider
from src.services.project_registry_service import ProjectRegistryService
from src.services.release_diff_service import (
    ReleaseDiffService,
    resolve_provider_name,
    resolve_remote_project_key,
)
from src.utils.log import get_logger
from src.utils.metrics import metrics as metrics_collector


logger = get_logger(__name__)


class AggregateReleaseNoteService:
    """Business logic for the combined application + packages release note."""

    def __init__(
        self,
        diff: ReleaseDiffService | None = None,
        registry: ProjectRegistryService | None = None,
        provider_factory: Callable[[str], BaseGitProvider] = get_git_provider,
        metrics: Any = None,
    ) -> None:
        self.diff = diff or ReleaseDiffService()
        self.registry = registry or ProjectRegistryService()
        self.provider_factory = provider_factory
        self.metrics = metrics or metrics_collector

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

        # the span's ends on the calendar: every package version is placed
        # against these two moments, and an end without a date cannot place any
        span = await self._span_dates(request)
        entries: list[AggregatePackageEntry] = []
        unchanged: list[str] = []

        if span is None:
            span_error = (
                "the span cannot be timed: the application's tag dates could not be "
                "read, so no package version can be placed against the span"
            )
        elif span.get("source") is None or span.get("target") is None:
            unplaced = request.source_ref if span.get("source") is None else request.target_ref
            span_error = (
                f"the span cannot be timed: '{unplaced}' is not a dated tag of "
                f"{request.repository_slug}, so no package version can be placed against it"
            )
        else:
            span_error = None

        # the packages the application carries, out of the registry
        registrations = await self._packages_of(app_name, request, db)
        if not registrations:
            entries.append(
                AggregatePackageEntry(
                    name=app_name,
                    change="upgraded",
                    from_version="",
                    to_version="",
                    status="skipped",
                    reason=(
                        f"no package is registered under '{app_name}' in the project "
                        "registry (mark package registrations on the registry page)"
                    ),
                )
            )
        elif span_error:
            for registration in registrations:
                entries.append(
                    AggregatePackageEntry(
                        name=self._package_name(registration),
                        change="upgraded",
                        from_version="",
                        to_version="",
                        status="skipped",
                        reason=span_error,
                    )
                )
        else:
            # resolution and tag listings are provider calls: they fan out
            entries = list(
                await asyncio.gather(
                    *(
                        self._package_entry(request, registration, span)
                        for registration in registrations
                    )
                )
            )
            unchanged = [
                f"{entry.name}@{entry.to_version}"
                for entry in entries
                if entry.status == "unchanged"
            ]
            entries = [entry for entry in entries if entry.status != "unchanged"]

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
            unchanged_packages=unchanged,
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    # Packages and their versions
    # ------------------------------------------------------------------ #

    @staticmethod
    def _package_name(registration: Any) -> str:
        """The name the note shows a package by.

        A package is registered under the application it belongs to, so the
        name the outside world knows it by is the alias when there is one, and
        the repository it lives in when there is not.
        """
        alias = (getattr(registration, "app_alias", None) or "").strip()
        return alias or str(registration.repository_slug)

    async def _packages_of(
        self, app_name: str, request: AggregateReleaseNoteRequest, db: AsyncSession
    ) -> list[Any]:
        """The registrations under the application that are marked packages.

        The application's own repositories share the grouping and are left out:
        they are the application, not what it carries. A registration nobody
        classified stays out too - it may be another repository of the
        application, and guessing would put commits in the note that belong to
        the app's own section.
        """
        registrations = await self.registry.list_projects_by_app(app_name, db)
        packages = [
            entry
            for entry in registrations
            if entry.registry_kind == "package"
            and not (
                entry.project_key == request.project_key
                and entry.repository_slug == request.repository_slug
            )
        ]
        return sorted(packages, key=lambda entry: self._package_name(entry))

    async def _span_dates(
        self, request: AggregateReleaseNoteRequest
    ) -> dict[str, int | None] | None:
        """When each end of the span shipped, from the application's own tags.

        Returns ``None`` when the tag listing itself failed - the caller says
        so once instead of pretending the span has no calendar.
        """
        provider_name = resolve_provider_name(request.git_provider)
        provider = self.provider_factory(provider_name)
        # A repository on Cloud is addressed by its workspace, and a project key
        # is not one: the span is read in the workspace the request was filled
        # with (from the repository's own URL), never in the project key.
        remote_key = resolve_remote_project_key(
            request.project_key, provider_name, request.workspace_slug
        )
        try:
            tags = await provider.list_tags_with_commits(remote_key, request.repository_slug)
        except Exception as e:
            logger.warning(
                "Could not read the application's tag dates",
                extra={
                    "project_key": request.project_key,
                    "repository_slug": request.repository_slug,
                    "error": str(e),
                },
            )
            return None
        dates = self._tag_dates(tags)
        return {"source": dates.get(request.source_ref), "target": dates.get(request.target_ref)}

    @staticmethod
    def _tag_dates(tags: list[dict[str, Any]]) -> dict[str, int]:
        """``{tag name: epoch ms}`` of every dated tag; undated tags cannot be placed."""
        dates: dict[str, int] = {}
        for entry in tags or []:
            name = str(entry.get("name") or "").strip()
            moment = entry.get("date")
            if not name or moment is None:
                continue
            dates[name] = int(moment)
        return dates

    async def _package_entry(
        self,
        request: AggregateReleaseNoteRequest,
        registration: Any,
        span: dict[str, int | None],
    ) -> AggregatePackageEntry:
        """Place one package on the span's timeline, or say why there is nothing to place."""
        name = self._package_name(registration)
        entry = AggregatePackageEntry(
            name=name, change="upgraded", from_version="", to_version="", status="skipped"
        )

        provider_name = resolve_provider_name(registration.git_provider)
        provider = self.provider_factory(provider_name)
        # A package may live in another project of the same workspace, so the
        # request's workspace addresses it remotely the same way the application
        # itself is addressed.
        remote_key = resolve_remote_project_key(
            registration.project_key, provider_name, request.workspace_slug
        )
        try:
            tags = await provider.list_tags_with_commits(remote_key, registration.repository_slug)
        except Exception as e:
            entry.status = "failed"
            entry.reason = f"the package's tags could not be read: {e}"
            logger.warning(
                "Package tag listing failed",
                extra={
                    "package": name,
                    "project_key": registration.project_key,
                    "repository_slug": registration.repository_slug,
                    "error": str(e),
                },
            )
            return entry

        dates = self._tag_dates(tags)
        if not dates:
            entry.reason = "the package repository holds no dated tag"
            return entry

        ordered = sorted(dates.items(), key=lambda item: (item[1], item[0]))
        source_date = span.get("source")
        target_date = span.get("target")
        from_version = self._version_at(ordered, source_date)
        to_version = self._version_at(ordered, target_date)

        if not to_version:
            entry.change = "added"
            entry.reason = "the package had released nothing when the release shipped"
            return entry
        if not from_version:
            entry.change = "added"
            entry.from_version = ""
            entry.to_version = to_version
            entry.reason = f"the package was not part of {request.source_ref}"
            return entry
        if from_version == to_version:
            # held at the same version: the unchanged summary covers it
            entry.from_version = from_version
            entry.to_version = to_version
            entry.status = "unchanged"
            return entry

        entry.change = "upgraded"
        entry.from_version = from_version
        entry.to_version = to_version
        entry.repository = AggregatePackageRepository(
            project_key=registration.project_key,
            repository_slug=registration.repository_slug,
            git_provider=registration.git_provider,
        )
        entry.status = "compared"
        return entry

    @staticmethod
    def _version_at(ordered: list[tuple[str, int]], moment: int | None) -> str | None:
        """The newest version released by ``moment``, or ``None`` before any."""
        if moment is None:
            return None
        candidate: str | None = None
        for name, date in ordered:
            if date <= moment:
                candidate = name
            else:
                break
        return candidate

    # ------------------------------------------------------------------ #
    # Comparisons
    # ------------------------------------------------------------------ #

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
                    # a package on Cloud is read in the workspace the request
                    # was filled with, the way the application itself is
                    workspace_slug=request.workspace_slug,
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
                workspace_slug=request.workspace_slug,
                source_ref=request.source_ref,
                target_ref=request.target_ref,
                include_commits=request.include_commits,
                refresh=request.refresh,
            )
        )
