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

Access control uses the ``release_note`` RBAC resource: every role may read
releases, only review administrators (``review_admin`` / ``system_admin``) may
manage them.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.exceptions import GitServiceException
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.models.release_note import ReleaseNote, ReleaseNoteStatus
from src.schemas.release_note import (
    ReleaseNoteCreateRequest,
    ReleaseNoteImportRequest,
    ReleaseNoteImportResponse,
    ReleaseNoteListResponse,
    ReleaseNotePreviewRequest,
    ReleaseNotePreviewResponse,
    ReleaseNotePushRequest,
    ReleaseNoteResponse,
    ReleaseNoteUpdateRequest,
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


def _serialize(note: ReleaseNote, latest_id: int | None) -> ReleaseNoteResponse:
    """Serialize a release and flag it when it is the latest published version."""
    response = ReleaseNoteResponse.model_validate(note)
    response.is_latest = note.id == latest_id
    return response


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
        items=[_serialize(note, latest_id) for note in notes],
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
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseNoteImportResponse:
    """Import version releases from the git provider."""
    await ensure_permission(rbac_service, current_user, "manage")

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
        items=[_serialize(note, latest_id) for note in notes],
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

    latest_id = await service.latest_published_id(
        project_key=note.project_key, repository_slug=note.repository_slug
    )
    return _serialize(note, latest_id)


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
    return _serialize(note, latest_id)


@router.put(
    "/{note_id}",
    response_model=ReleaseNoteResponse,
    summary="Update a version release",
    description="Update the title, notes, previous version, pre-release flag or state.",
)
async def update_release_note(
    note_id: int,
    payload: ReleaseNoteUpdateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseNoteResponse:
    """Update an existing release."""
    await ensure_permission(rbac_service, current_user, "manage")

    note = await service.update_note(note_id, payload, author=current_user.username)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": f"Release {note_id} not found"},
        )

    latest_id = await service.latest_published_id(
        project_key=note.project_key, repository_slug=note.repository_slug
    )
    return _serialize(note, latest_id)


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
    service: Annotated[ReleaseNoteService, Depends(get_release_note_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> ReleaseNoteResponse:
    """Publish a stored release on the git provider."""
    await ensure_permission(rbac_service, current_user, "manage")

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
    return _serialize(note, latest_id)
