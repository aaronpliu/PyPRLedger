"""Release note endpoints - version releases and their notes.

Mirrors the GitHub Releases workflow for the repositories tracked by PyPRLedger:

* ``GET    /release/notes``             - list the releases of a repository
* ``GET    /release/notes/{id}``        - one release
* ``POST   /release/notes``             - draft or publish a version release
* ``PUT    /release/notes/{id}``        - update a release
* ``DELETE /release/notes/{id}``        - delete a release
* ``POST   /release/notes/preview``     - draft notes from the commits of a version
* ``POST   /release/notes/{id}/push``   - publish the release on the git provider
* ``POST   /release/notes/import``      - import the releases of a repository
* ``GET    /release/notes/confluence``  - whether Confluence sync is available here
* ``POST   /release/notes/{id}/confluence-sync`` - write the release to Confluence

Confluence is an optional addition rather than a dependency. Publishing schedules
a sync when the integration is configured and switched on, and that sync runs
after the response with a session of its own, so a release is published whether
or not Confluence answers - a failure is recorded on the release, where the page
can offer the retry that this module also exposes. An instance that configures
nothing reaches none of that code.

Access control uses the ``release_note`` RBAC resource: every role may read
releases, only review administrators (``review_admin`` / ``system_admin``) may
manage them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.exceptions import GitServiceException
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.models.release_note import ReleaseNote, ReleaseNoteStatus
from src.schemas.release_note import (
    ReleaseNoteConfluenceStatusResponse,
    ReleaseNoteConfluenceSyncResponse,
    ReleaseNoteCreateRequest,
    ReleaseNoteExportRequest,
    ReleaseNoteExportResponse,
    ReleaseNoteImportRequest,
    ReleaseNoteImportResponse,
    ReleaseNoteListResponse,
    ReleaseNotePreviewRequest,
    ReleaseNotePreviewResponse,
    ReleaseNotePushRequest,
    ReleaseNoteResponse,
    ReleaseNoteUpdateRequest,
)
from src.services.confluence.client import has_credentials as has_confluence_credentials
from src.services.confluence.service import (
    ConfluenceSyncService,
    is_auto_sync_enabled,
    sync_release_note_to_confluence,
)
from src.services.git_provider_resolver import (
    registered_provider,
    registered_workspace_slug,
    with_repository_provider,
)
from src.services.rbac_service import RBACService
from src.services.release_note_service import ReleaseNoteService
from src.utils.log import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/release/notes")

RESOURCE_TYPE = "release_note"


def get_release_note_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReleaseNoteService:
    """Dependency provider for ReleaseNoteService."""
    return ReleaseNoteService(db)


def get_rbac_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RBACService:
    """Dependency provider for RBACService (release note permissions)."""
    return RBACService(db)


def get_confluence_sync_service() -> ConfluenceSyncService:
    """Dependency provider for the Confluence sync.

    It is given no session on purpose: it opens one of its own, so a sync never
    writes through the transaction the request is still holding.
    """
    return ConfluenceSyncService()


async def ensure_permission(
    rbac_service: RBACService,
    current_user: AuthUser,
    action: str,
) -> None:
    """Raise 403 unless the user may perform ``action`` on release notes."""
    allowed = await rbac_service.check_permission(
        auth_user_id=current_user.id,
        action=action,
        resource_type=RESOURCE_TYPE,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "FORBIDDEN",
                "message": (
                    f"Insufficient permissions to {action} release notes. "
                    "Review administrator role required."
                ),
            },
        )


def _serialize(
    note: ReleaseNote,
    latest_id: int | None,
    avatars: Mapping[str, str] | None = None,
    tag_url: str | None = None,
) -> ReleaseNoteResponse:
    """Serialize a release and flag it when it is the latest published version."""
    response = ReleaseNoteResponse.model_validate(note)
    response.is_latest = note.id == latest_id
    # Only authors with a local profile picture get one (imported releases keep
    # the provider login, which has no avatar here)
    if avatars and note.author:
        response.author_avatar_url = avatars.get(note.author)
    response.tag_url = tag_url
    return response


async def _tag_urls(
    service: ReleaseNoteService,
    notes: list[ReleaseNote],
) -> dict[int, str]:
    """The repository page of each release's tag, where the platform has one.

    Resolved per repository rather than per release: the provider and workspace
    are a property of the repository, and reading them once keeps a page of
    releases from repeating the same lookup.
    """
    resolved: dict[tuple[str, str], tuple[str | None, str | None]] = {}
    urls: dict[int, str] = {}

    for note in notes:
        pair = (note.project_key, note.repository_slug)
        if pair not in resolved:
            resolved[pair] = (
                await registered_provider(
                    note.project_key, note.repository_slug, service.db
                ),
                await registered_workspace_slug(
                    note.project_key, note.repository_slug, service.db
                ),
            )
        git_provider, workspace_slug = resolved[pair]
        url = service.tag_url(
            project_key=note.project_key,
            repository_slug=note.repository_slug,
            tag_name=note.tag_name,
            git_provider=git_provider,
            workspace_slug=workspace_slug,
        )
        if url and note.id is not None:
            urls[note.id] = url

    return urls


async def serialize_note(
    service: ReleaseNoteService,
    note: ReleaseNote,
    latest_id: int | None,
) -> ReleaseNoteResponse:
    """Serialize one release, resolving its author picture and tag page."""
    avatars = await service.author_avatars([note.author])
    tag_urls = await _tag_urls(service, [note])
    return _serialize(note, latest_id, avatars, tag_urls.get(note.id))


async def serialize_notes(
    service: ReleaseNoteService,
    notes: list[ReleaseNote],
    latest_id: int | None,
) -> list[ReleaseNoteResponse]:
    """Serialize releases, resolving their author pictures and tag pages."""
    avatars = await service.author_avatars([note.author for note in notes])
    tag_urls = await _tag_urls(service, notes)
    return [_serialize(note, latest_id, avatars, tag_urls.get(note.id)) for note in notes]


async def schedule_confluence_sync(
    background_tasks: BackgroundTasks,
    session: AsyncSession,
    note: ReleaseNote,
) -> None:
    """Queue a Confluence sync for a release that has just been published.

    It runs after the response, with a session of its own, so publishing is
    neither delayed by Confluence nor affected by whether it answers. Nothing is
    queued at all unless the integration is configured and switched on, which is
    what keeps it optional.

    A pre-release is never written by itself: it is a version being tried out, and
    what a reader of the space should see is the release. Writing one by hand is
    still offered on the release row.

    The request commits before the task is queued, because the task reads the
    release through a session of its own and background tasks run before the
    dependency that would otherwise commit this request. A release that is still
    only flushed is not there at all for that session, and one that still carries
    its old draft status reads as unpublished: either way the write the reader
    asked for would quietly do nothing.
    """
    if note.status != ReleaseNoteStatus.PUBLISHED:
        return
    if note.is_prerelease:
        return
    if not is_auto_sync_enabled():
        return

    await session.commit()
    background_tasks.add_task(sync_release_note_to_confluence, note.id)


@dataclass(frozen=True)
class _PageState:
    """What a Confluence page said before an update was applied.

    A snapshot of the two fields that reach the page rather than the release
    itself: the update mutates the row it loads, so a release read after it would
    carry the new notes either way and every save would look like a change.
    """

    published: bool
    content: tuple[str, str]


def _page_content(note: ReleaseNote) -> tuple[str, str]:
    """The parts of a release a Confluence page is made of.

    Its notes, and the tag its title is built from. The rest of a release - its
    name, whether it is a pre-release, the version it compares to - is not written
    to the page at all, so a save that touches only those has nothing to write.
    """
    return (note.body or "", note.tag_name)


def _page_state(note: ReleaseNote | None) -> _PageState:
    """Take down what the page said, so an update can be compared against it."""
    if note is None:
        return _PageState(published=False, content=("", ""))

    return _PageState(
        published=note.status == ReleaseNoteStatus.PUBLISHED, content=_page_content(note)
    )


def page_needs_writing(before: _PageState, note: ReleaseNote) -> bool:
    """Whether this update gives Confluence something to write.

    A release that was not published before is a page that does not exist yet,
    which is a change in itself - publishing a draft is how a page is first made.
    After that, a save that leaves the notes and the tag as they were has nothing
    to write, and scheduling one would only add a version to a page that already
    says it.
    """
    if not before.published:
        return True

    return before.content != _page_content(note)


@router.get(
    "/confluence",
    response_model=ReleaseNoteConfluenceStatusResponse,
    summary="Whether Confluence sync is available on this instance",
    description=(
        "Reporting, not changing. The release page asks once so that the sync "
        "controls are only offered where a sync could actually happen."
    ),
)
async def get_confluence_status(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseNoteConfluenceStatusResponse:
    """Report the state of the optional Confluence integration."""
    await ensure_permission(rbac_service, current_user, "read")

    # Credentials, not a space: which space a release goes to is decided per
    # repository, so an instance can be ready to sync while a particular
    # repository still has no target - that is reported by the sync itself.
    return ReleaseNoteConfluenceStatusResponse(
        configured=has_confluence_credentials(),
        auto_sync=is_auto_sync_enabled(),
    )


@router.get(
    "",
    response_model=ReleaseNoteListResponse,
    summary="List the releases of a repository",
    description=(
        "Return the version releases of one repository, newest first (drafts are "
        "included). The newest published, non pre-release version is flagged with "
        "`is_latest`."
    ),
)
async def list_release_notes(
    project_key: Annotated[str, Query(min_length=1, max_length=32)],
    repository_slug: Annotated[str, Query(min_length=1, max_length=128)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="Filter by state: draft or published"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReleaseNoteListResponse:
    """List version releases of a repository."""
    await ensure_permission(rbac_service, current_user, "read")

    if status_filter and status_filter not in ReleaseNoteStatus.VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "VALIDATION_ERROR", "message": "status must be draft or published"},
        )

    notes, total = await service.list_notes(
        project_key=project_key,
        repository_slug=repository_slug,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    latest_id = await service.latest_published_id(
        project_key=project_key, repository_slug=repository_slug
    )

    return ReleaseNoteListResponse(
        total=total,
        items=await serialize_notes(service, notes, latest_id),
    )


@router.post(
    "/preview",
    response_model=ReleaseNotePreviewResponse,
    summary="Draft release notes for a version",
    description=(
        "Generate markdown release notes from the commits of a release scope: every "
        "commit after `previous_version` (or the whole history up to `version` when "
        "no previous version is given), grouped by conventional commit type."
    ),
)
async def preview_release_notes(
    payload: ReleaseNotePreviewRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseNotePreviewResponse:
    """Generate release notes (markdown) without saving them."""
    await ensure_permission(rbac_service, current_user, "read")

    try:
        return await service.generate_preview(payload)
    except GitServiceException as e:
        logger.error(
            "Git provider failed while generating release notes",
            extra={
                "project_key": payload.project_key,
                "repository_slug": payload.repository_slug,
                "version": payload.version,
                "user_id": current_user.id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "git_service_error",
                "message": str(e.detail) if isinstance(e.detail, dict) else str(e),
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_request", "message": str(e)},
        )


@router.post(
    "/export",
    response_model=ReleaseNoteExportResponse,
    summary="Export the notes of one or more releases as markdown",
    description=(
        "Package the stored release notes of the chosen releases into one markdown "
        "document, newest first. Choose the releases by `ids`, or ask for every "
        "release matching `status` with `select_all`. The response carries the "
        "document, a suggested filename, and whatever was skipped or cut."
    ),
)
async def export_release_notes(
    payload: ReleaseNoteExportRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseNoteExportResponse:
    """Export releases as one markdown document (reading, not changing)."""
    await ensure_permission(rbac_service, current_user, "read")

    exported = await service.export_notes(
        project_key=payload.project_key,
        repository_slug=payload.repository_slug,
        ids=payload.ids,
        select_all=payload.select_all,
        status=payload.status,
    )

    logger.info(
        "Release notes exported",
        extra={
            "project_key": payload.project_key,
            "repository_slug": payload.repository_slug,
            "user_id": current_user.id,
            "count": exported.count,
            "skipped": len(exported.skipped_ids),
            "truncated": exported.truncated,
        },
    )

    return ReleaseNoteExportResponse(
        filename=exported.filename,
        content=exported.content,
        count=exported.count,
        skipped_ids=exported.skipped_ids,
        truncated=exported.truncated,
    )


@router.post(
    "/import",
    response_model=ReleaseNoteImportResponse,
    summary="Import the releases of a repository from the git provider",
    description=(
        "Fetch the releases of a repository from the provider release API "
        "(GitHub Enterprise) and store them as version releases. Existing releases "
        "are only refreshed with `overwrite=true`."
    ),
)
async def import_release_notes(
    payload: ReleaseNoteImportRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseNoteImportResponse:
    """Import version releases from the git provider."""
    await ensure_permission(rbac_service, current_user, "manage")
    payload = await with_repository_provider(payload, db)

    try:
        imported, updated, skipped, notes = await service.import_from_provider(payload)
    except GitServiceException as e:
        logger.error(
            "Git provider failed while importing releases",
            extra={
                "project_key": payload.project_key,
                "repository_slug": payload.repository_slug,
                "user_id": current_user.id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "git_service_error",
                "message": str(e.detail) if isinstance(e.detail, dict) else str(e),
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_request", "message": str(e)},
        )

    latest_id = await service.latest_published_id(
        project_key=payload.project_key, repository_slug=payload.repository_slug
    )
    return ReleaseNoteImportResponse(
        imported=imported,
        updated=updated,
        skipped=skipped,
        items=await serialize_notes(service, notes, latest_id),
    )


@router.post(
    "",
    response_model=ReleaseNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Draft or publish a version release",
    description=(
        "Create a release for a git tag. `status=draft` keeps it unpublished, "
        "`status=published` releases it immediately (stamping the publish date and "
        "the author)."
    ),
)
async def create_release_note(
    payload: ReleaseNoteCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseNoteResponse:
    """Create (draft) or publish a version release."""
    await ensure_permission(rbac_service, current_user, "manage")

    try:
        note = await service.create_note(payload, author=current_user.username)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "CONFLICT", "message": str(e)},
        )

    if payload.sync_to_confluence:
        await schedule_confluence_sync(background_tasks, service.db, note)

    latest_id = await service.latest_published_id(
        project_key=note.project_key, repository_slug=note.repository_slug
    )
    return await serialize_note(service, note, latest_id)


@router.get(
    "/{note_id}",
    response_model=ReleaseNoteResponse,
    summary="Get one version release",
    description="Fetch a single release with its notes.",
)
async def get_release_note(
    note_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseNoteResponse:
    """Fetch a single release."""
    await ensure_permission(rbac_service, current_user, "read")

    note = await service.get_note(note_id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": f"Release {note_id} not found"},
        )

    latest_id = await service.latest_published_id(
        project_key=note.project_key, repository_slug=note.repository_slug
    )
    return await serialize_note(service, note, latest_id)


@router.put(
    "/{note_id}",
    response_model=ReleaseNoteResponse,
    summary="Update a version release",
    description="Update the title, notes, previous version, pre-release flag or state.",
)
async def update_release_note(
    note_id: int,
    payload: ReleaseNoteUpdateRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseNoteResponse:
    """Update an existing release."""
    await ensure_permission(rbac_service, current_user, "manage")

    # Taken down before the update rather than after it: the update mutates the row
    # it loads, so what the page said has to be captured first to tell whether this
    # save changes any of it.
    before = _page_state(await service.get_note(note_id))

    note = await service.update_note(note_id, payload, author=current_user.username)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": f"Release {note_id} not found"},
        )

    # A release that had no page gets one; a release that has one is written again
    # only when something the page holds changed.
    if payload.sync_to_confluence and page_needs_writing(before, note):
        await schedule_confluence_sync(background_tasks, service.db, note)

    latest_id = await service.latest_published_id(
        project_key=note.project_key, repository_slug=note.repository_slug
    )
    return await serialize_note(service, note, latest_id)


@router.delete(
    "/{note_id}",
    summary="Delete a version release",
    description="Delete a release and its notes.",
)
async def delete_release_note(
    note_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> dict[str, str]:
    """Delete a release."""
    await ensure_permission(rbac_service, current_user, "manage")

    deleted = await service.delete_note(note_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": f"Release {note_id} not found"},
        )
    return {"message": "Release deleted successfully"}


@router.post(
    "/{note_id}/push",
    response_model=ReleaseNoteResponse,
    summary="Publish a release on the git provider",
    description=(
        "Publish the version release through the provider release API "
        "(GitHub Enterprise) and store the provider release id/url on the release. "
        "Existing provider releases are updated when `update_existing` is set."
    ),
)
async def push_release_note(
    note_id: int,
    payload: ReleaseNotePushRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseNoteResponse:
    """Publish a stored release on the git provider."""
    await ensure_permission(rbac_service, current_user, "manage")
    payload = await with_repository_provider(payload, db)

    try:
        note = await service.push_to_provider(note_id, payload)
    except GitServiceException as e:
        logger.error(
            "Git provider failed while pushing a release",
            extra={
                "note_id": note_id,
                "project_key": payload.project_key,
                "repository_slug": payload.repository_slug,
                "user_id": current_user.id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "git_service_error",
                "message": str(e.detail) if isinstance(e.detail, dict) else str(e),
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_request", "message": str(e)},
        )

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": f"Release {note_id} not found"},
        )

    latest_id = await service.latest_published_id(
        project_key=note.project_key, repository_slug=note.repository_slug
    )
    return await serialize_note(service, note, latest_id)


@router.post(
    "/{note_id}/confluence-sync",
    response_model=ReleaseNoteConfluenceSyncResponse,
    summary="Write one release to Confluence",
    description=(
        "Sync one release by hand, whether or not publishing syncs by itself. The "
        "page is updated where it exists and created where it does not, so asking "
        "twice does not leave two. Failing to reach Confluence is reported in the "
        "response rather than raised: the release is unaffected either way. Only a "
        "published release is written - a draft is refused with 409."
    ),
)
async def sync_release_note_now(
    note_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    confluence: Annotated[ConfluenceSyncService, Depends(get_confluence_sync_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseNoteConfluenceSyncResponse:
    """Sync a release to Confluence on demand."""
    await ensure_permission(rbac_service, current_user, "manage")

    note = await service.get_note(note_id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": f"Release {note_id} not found"},
        )

    # Confluence is somewhere other people read, and publishing is what puts a
    # release in front of them - so a draft is refused here rather than written.
    # The release page only offers the action for a published release either way.
    if note.status != ReleaseNoteStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "CONFLICT",
                "message": (
                    f"Release {note_id} is {note.status}: only a published release is "
                    "written to Confluence"
                ),
            },
        )

    # The sync writes on a session of its own, so what happened is what it returns
    # rather than anything re-read here. It is not the automatic path: a repository
    # left out of the automatic sync - or an instance that switched it off - is
    # still written when someone asks for it here.
    outcome = await confluence.sync_note(note_id, automatic=False)

    logger.info(
        "Confluence sync requested",
        extra={
            "note_id": note_id,
            "tag_name": note.tag_name,
            "synced": outcome.synced,
            "skipped": outcome.skipped,
            "user_id": current_user.id,
        },
    )

    return ReleaseNoteConfluenceSyncResponse(
        synced=outcome.synced,
        page_url=outcome.page_url,
        message=outcome.message,
    )
