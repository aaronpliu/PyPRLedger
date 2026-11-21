"""The aggregate release note: one note for a release and the packages it moved.

A release note for an application is incomplete when the application is a
shell over packages - the app's own commits tell half the story, and each
pinned package that moved carries the rest. This service assembles both
halves into one document.

Where the relationship comes from:

1. **The dependency database** is the only source of what an application
   version declares: which packages it pins and at which exact version. The
   application's two refs are each asked once
   (``DependencyApiClient.get_app_release_info``); a dict comparison
   classifies every package as upgraded, added, removed or unchanged. No
   provider is touched for the classification itself.
2. **Monolithic fallback** - an application the database holds no record for
   has no declared packages, and none are guessed: the note degrades to the
   application's own comparison and says so
   (``dependency_source = "none"``). A release note for a monolithic
   application and one for a shell are served by the same pipeline.
3. **Scope** - only the packages the application *declares* are compared
   commit by commit. A moved package the application does not pin is a
   transitive dependency: it stays in the note as a skipped entry, because a
   change two levels down still says nothing about this release unless the
   application pins it.
4. **Resolution** - a package name is a name in the project registry;
   ``find_dependency_repository`` answers with the registration or with the
   reason there is none. "Cannot say" stays legible in the note - it is never
   read as a package that contains what it should.
5. **Per-package comparison and body** - the same
   ``ReleaseDiffService.compare_releases`` the release pages use, source
   version → target version, run in parallel and cached; the section body is
   rendered by the same ``build_release_notes_markdown`` the Release Notes
   page generates with, so the combined note reads like a release note, not
   like a commit listing. A provider failure on one package is that package's
   ``failed`` entry; it never takes the note down.
6. **The summary** - the optional LLM pass runs once, for the application's
   own scope, and its section hints are applied to the application's commits
   before the body is rendered. The commit list stays the source of truth and
   a failed pass degrades to the deterministic notes.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import DependencyApiException, GitServiceException
from src.schemas.aggregate_release_note import (
    AggregateNotePlanEntry,
    AggregateNotePlanResponse,
    AggregatePackageEntry,
    AggregatePackageRepository,
    AggregateReleaseNoteRequest,
    AggregateReleaseNoteResponse,
    AggregateReleaseNoteSummary,
)
from src.schemas.release_diff import ReleaseCompareRequest, ReleaseCompareResponse
from src.schemas.release_note import (
    SUMMARY_DETERMINISTIC,
    SUMMARY_NOTICE_FAILED,
    SUMMARY_LLM,
)
from src.services.dependency_api_client import DependencyApiClient
from src.services.git_providers import BaseGitProvider, get_git_provider
from src.services.project_registry_service import ProjectRegistryService
from src.services.release_diff_service import (
    ReleaseDiffService,
    resolve_provider_name,
    resolve_remote_project_key,
)
from src.services.release_note_llm_service import ReleaseNoteLlmService
from src.services.release_note_service import (
    build_release_notes_markdown,
    jira_settings,
)
from src.utils.log import get_logger
from src.utils.metrics import metrics as metrics_collector


logger = get_logger(__name__)

# Where the package relationship came from, as the response states it.
SOURCE_DATABASE = "database"
SOURCE_NONE = "none"


class AggregateReleaseNoteService:
    """Business logic for the combined application + packages release note."""

    def __init__(
        self,
        diff: ReleaseDiffService | None = None,
        registry: ProjectRegistryService | None = None,
        client: DependencyApiClient | None = None,
        metrics: Any = metrics_collector,
        provider_factory: Callable[[str], BaseGitProvider] = get_git_provider,
    ) -> None:
        self.diff = diff or ReleaseDiffService()
        self.registry = registry or ProjectRegistryService()
        self.client = client or DependencyApiClient()
        self.metrics = metrics
        self.provider_factory = provider_factory

    def compare_url(
        self,
        request: AggregateReleaseNoteRequest,
        source_ref: str,
        target_ref: str,
        *,
        project_key: str | None = None,
        repository_slug: str | None = None,
    ) -> str | None:
        """Browsable comparison link for one section's span, when the platform has one.

        The application section links to the application's own comparison; each
        package section links to the comparison between the two versions that
        package moved between, on the package's repository. Best effort, like
        the release page's link: an unknown provider or a missing host leaves
        the range plain text rather than failing the note.
        """
        try:
            provider_name = resolve_provider_name(request.git_provider)
            provider = self.provider_factory(provider_name)
            remote_key = resolve_remote_project_key(
                project_key or request.project_key,
                provider_name,
                request.workspace_slug,
            )
            return provider.web_compare_url(
                remote_key,
                repository_slug or request.repository_slug,
                source_ref,
                target_ref,
            )
        except Exception as e:  # noqa: BLE001 - a link is never worth a note
            logger.warning(f"Could not build the release comparison link: {e}")
            return None

    async def plan(
        self, request: AggregateReleaseNoteRequest, db: AsyncSession
    ) -> AggregateNotePlanResponse:
        """What the dependency database says the span carries - versions only.

        No repository resolution, no commit comparison, no AI: two dependency
        lookups and a classification, cheap enough to run while the release is
        still being typed. The declared pins of each ref are the authoritative
        answer to what that version of the application carries; a monolithic
        application answers with empty pins and no packages.

        Raises:
            ValueError: If the repository is not registered as an application
        """
        app_name = await self._require_application(request, db)

        source_record, target_record = await self._dependency_records(app_name, request)
        plan = AggregateNotePlanResponse(
            app_name=app_name,
            source_ref=request.source_ref,
            target_ref=request.target_ref,
        )
        if not source_record or not target_record:
            return plan  # monolithic: empty pins, no packages, none guessed

        plan.dependency_source = SOURCE_DATABASE
        plan.source_pins = {
            str(name): str(version)
            for name, version in (source_record.get("dependencies") or {}).items()
            if version
        }
        plan.target_pins = {
            str(name): str(version)
            for name, version in (target_record.get("dependencies") or {}).items()
            if version
        }

        old_versions = self._version_map(source_record)
        new_versions = self._version_map(target_record)
        pinned = self._pinned_names(source_record, target_record)
        plan.unchanged_packages = sorted(
            f"{name}@{version}"
            for name, version in new_versions.items()
            if version and name not in pinned and old_versions.get(name) == version
        )
        plan.packages = [
            AggregateNotePlanEntry(
                name=name,
                change=change,
                from_version=from_version,
                to_version=to_version,
                pinned=is_pinned,
                reason=self._plan_reason(request, change, from_version, to_version, is_pinned),
            )
            for name, change, from_version, to_version, is_pinned in self._classify(
                pinned, old_versions, new_versions
            )
        ]
        return plan

    @staticmethod
    def _plan_reason(
        request: AggregateReleaseNoteRequest,
        change: str,
        from_version: str,
        to_version: str,
        is_pinned: bool,
    ) -> str | None:
        """Why the plan does not promise a commit comparison for this package."""
        if not is_pinned:
            return "the application does not declare this package (transitive dependency)"
        if change == "removed":
            return f"the package is no longer part of {request.target_ref}"
        if not from_version:
            return f"the package was not part of {request.source_ref}"
        return None

    async def _require_application(
        self, request: AggregateReleaseNoteRequest, db: AsyncSession
    ) -> str:
        """The application's dependency name, refusing anything but an application.

        A combined note is about what an application release carries, and only
        the project registry says what an application is.
        """
        kind = await self.registry.get_registry_kind(
            request.project_key, request.repository_slug, db
        )
        if kind != "application":
            raise ValueError(
                f"{request.project_key}/{request.repository_slug} is not registered as an "
                f"application in the project registry "
                f"(registry_kind='{kind or 'unclassified'}'), so there is nothing to combine: "
                f"combined release notes are for applications only"
            )
        return request.app_name or await self.registry.get_dependency_app_name(
            request.project_key, request.repository_slug, db
        )

    async def build(
        self, request: AggregateReleaseNoteRequest, db: AsyncSession
    ) -> AggregateReleaseNoteResponse:
        """Assemble the note for one application version span.

        Args:
            request: The application coordinates and the two refs of the span
            db: Database session for the registry lookups and the LLM pass

        Returns:
            The application's comparison and rendered body, one entry per
            moved package with its rendered body, and the unchanged summary

        Raises:
            ValueError: If the repository is not registered as an application -
                a combined note is about what an application release carries,
                and only the project registry says what an application is
        """
        app_name = await self._require_application(request, db)

        # the declared relationship: what each ref of the application pins
        source_record, target_record = await self._dependency_records(app_name, request)
        dependency_source = SOURCE_NONE

        entries: list[AggregatePackageEntry] = []
        unchanged: list[str] = []
        if source_record and target_record:
            dependency_source = SOURCE_DATABASE
            entries, unchanged = await self._packages(
                app_name, request, source_record, target_record, db
            )

        compared = [entry for entry in entries if entry.status == "compared"]
        # the comparisons are provider calls with their own caches: they fan out
        if compared:
            await asyncio.gather(*(self._compare_package(request, entry) for entry in compared))

        application = await self._compare_application(request)
        summary, summary_source, summary_notice = await self._summarize(
            request, db, application
        )
        application_body = self._render(
            application.added_commits,
            version=request.target_ref,
            previous_version=request.source_ref,
            summary=summary,
            language=request.language,
            compare_url=self.compare_url(request, request.source_ref, request.target_ref),
        )

        self.metrics.increment_release_diff("aggregate_note", request.git_provider or "default", "built")

        return AggregateReleaseNoteResponse(
            app_name=app_name,
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            git_provider=request.git_provider,
            source_ref=request.source_ref,
            target_ref=request.target_ref,
            dependency_source=dependency_source,
            application=application,
            application_body=application_body,
            summary_source=summary_source,
            summary_notice=summary_notice,
            packages=entries,
            unchanged_packages=unchanged,
            summary=self._counts(entries, application, len(unchanged)),
        )

    # ------------------------------------------------------------------ #
    # The declared relationship
    # ------------------------------------------------------------------ #

    async def _dependency_records(
        self, app_name: str, request: AggregateReleaseNoteRequest
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """What the dependency database holds for each ref of the span.

        An application with no record - or a database that cannot be reached -
        is a monolithic application as far as this note is concerned: the
        fallback answers with nothing rather than with an error, because a
        note about the application's own commits is still worth having.
        """
        try:
            source_record = await self.client.get_app_release_info(app_name, request.source_ref)
            target_record = await self.client.get_app_release_info(app_name, request.target_ref)
        except DependencyApiException as e:
            logger.warning(
                "Dependency database unreachable, degrading to a monolithic note",
                extra={"app_name": app_name, "error": str(e)},
            )
            return None, None
        if not source_record or not target_record:
            logger.info(
                "No dependency record for the span, degrading to a monolithic note",
                extra={"app_name": app_name, "source_ref": request.source_ref, "target_ref": request.target_ref},
            )
            return None, None
        return source_record, target_record

    @staticmethod
    def _version_map(record: dict[str, Any]) -> dict[str, str]:
        """``{package name: version}`` of one record."""
        return {
            str(entry.get("package_name")): str(entry.get("version") or "")
            for entry in record.get("packages") or []
            if isinstance(entry, dict) and entry.get("package_name")
        }

    @staticmethod
    def _pinned_names(source_record: dict[str, Any], target_record: dict[str, Any]) -> set[str]:
        """The packages either version of the application declares (the scope)."""
        pinned: set[str] = set()
        for record in (source_record, target_record):
            pinned.update(str(name) for name in (record.get("dependencies") or {}))
        return pinned

    def _classify(
        self,
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
        for name in sorted(set(old_versions) | set(new_versions)):
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

    async def _packages(
        self,
        app_name: str,
        request: AggregateReleaseNoteRequest,
        source_record: dict[str, Any],
        target_record: dict[str, Any],
        db: AsyncSession,
    ) -> tuple[list[AggregatePackageEntry], list[str]]:
        """One entry per package the span moved, plus the unchanged names.

        Resolution is a database walk: sequential by design, so one session
        serves every lookup.
        """
        old_versions = self._version_map(source_record)
        new_versions = self._version_map(target_record)
        pinned = self._pinned_names(source_record, target_record)

        unchanged = sorted(
            f"{name}@{version}"
            for name, version in new_versions.items()
            if version and name not in pinned and old_versions.get(name) == version
        )

        entries = []
        for name, change, from_version, to_version, is_pinned in self._classify(
            pinned, old_versions, new_versions
        ):
            entries.append(
                await self._resolve_package(
                    request, db, name, change, from_version, to_version, is_pinned
                )
            )
        return entries, unchanged

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

    # ------------------------------------------------------------------ #
    # Comparisons and bodies
    # ------------------------------------------------------------------ #

    async def _compare_package(
        self, request: AggregateReleaseNoteRequest, entry: AggregatePackageEntry
    ) -> None:
        """Fill one package's comparison and body in place; a failure is its status."""
        assert entry.repository is not None  # only compared entries arrive here
        try:
            comparison = await self.diff.compare_releases(
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
            return

        entry.comparison = comparison
        entry.body = self._render(
            comparison.added_commits,
            version=entry.to_version,
            previous_version=entry.from_version,
            summary=None,
            language=request.language,
            compare_url=self.compare_url(
                request,
                entry.from_version,
                entry.to_version,
                project_key=entry.repository.project_key if entry.repository else None,
                repository_slug=entry.repository.repository_slug if entry.repository else None,
            ),
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

    async def _summarize(
        self, request: AggregateReleaseNoteRequest, db: AsyncSession, application: ReleaseCompareResponse
    ) -> tuple[str | None, str | None, str | None]:
        """The one optional LLM pass, over the application's own scope.

        Answers ``(summary, source, notice)``. The commit list stays the source
        of truth - the model's section hints are applied to the commits before
        the body is rendered, and a failed pass degrades to the deterministic
        notes instead of failing the note.
        """
        if not request.summarize:
            return None, None, None

        try:
            llm = ReleaseNoteLlmService(db)
            outcome = await llm.summarize(
                project_key=request.project_key,
                repository_slug=request.repository_slug,
                version=request.target_ref,
                previous_version=request.source_ref,
                commits=application.added_commits or [],
                language=request.language,
            )
        except Exception as e:  # noqa: BLE001 - an optional pass must never fail the note
            logger.warning(f"Aggregate note summarization failed: {e}")
            return None, SUMMARY_DETERMINISTIC, SUMMARY_NOTICE_FAILED

        if outcome.summary is None:
            return None, SUMMARY_DETERMINISTIC, outcome.notice

        for commit in application.added_commits or []:
            section = outcome.summary.sections.get(str(commit.get("id")))
            if section:
                commit["section"] = section
        return outcome.summary.summary or None, SUMMARY_LLM, None

    @staticmethod
    def _render(
        commits: list[dict[str, Any]] | None,
        *,
        version: str,
        previous_version: str | None,
        summary: str | None,
        language: str | None,
        compare_url: str | None = None,
    ) -> str | None:
        """One section's body, in the shape the Release Notes page publishes.

        The same builder the Release Notes generation uses: categorized
        sections, ticket links, authors, the caller's language. A scope with
        nothing to say renders as nothing - an empty section would read as a
        note that promises a change that is not there.
        """
        base_url, project_keys = jira_settings()
        body = build_release_notes_markdown(
            [commit.model_dump() for commit in commits or []],
            version=version,
            previous_version=previous_version,
            jira_base_url=base_url,
            jira_project_keys=project_keys,
            language=language,
            summary=summary,
            compare_url=compare_url,
        )
        return body or None

    # ------------------------------------------------------------------ #
    # Counts
    # ------------------------------------------------------------------ #

    @staticmethod
    def _counts(
        entries: list[AggregatePackageEntry],
        application: ReleaseCompareResponse,
        unchanged_count: int,
    ) -> AggregateReleaseNoteSummary:
        """Counts a reader can trust without scrolling."""
        return AggregateReleaseNoteSummary(
            packages_changed=len(entries),
            packages_compared=sum(1 for entry in entries if entry.status == "compared"),
            packages_skipped=sum(1 for entry in entries if entry.status == "skipped"),
            packages_failed=sum(1 for entry in entries if entry.status == "failed"),
            unchanged_packages=unchanged_count,
            app_commits=len(application.added_commits),
            package_commits=sum(
                len(entry.comparison.added_commits)
                for entry in entries
                if entry.comparison is not None
            ),
        )
