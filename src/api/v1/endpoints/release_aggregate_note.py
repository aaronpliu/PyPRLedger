"""Aggregate release note endpoints.

One note for an application version span and the packages it moved:

* ``POST /release/aggregate-note/build`` - the dependency database is asked
  what each ref of the application declares (its exact pins), and every moved
  package is classified as upgraded, added, removed or unchanged, then
  compared between its two pinned versions with the same release diff the
  release pages use. Each compared section is rendered by the same markdown
  builder the Release Notes page generates with - categorized sections,
  ticket links, authors - and the application's own comparison rides along
  as the note's first section, with one optional AI summary over its scope.

An application the database holds no record for is monolithic: the note
degrades to the application's own comparison (``dependency_source = "none"``)
and no packages are guessed. A package that cannot be compared stays legible:
it is ``skipped`` with the reason (not pinned, not registered, added or
removed in the span) or ``failed`` with the provider error - never silently
missing, never guessed at.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import CurrentRepositoryAccess, get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.aggregate_release_note import (
    AggregateNotePlanResponse,
    AggregateReleaseNoteRequest,
    AggregateReleaseNoteResponse,
)
from src.services.aggregate_release_note_service import AggregateReleaseNoteService
from src.services.git_provider_resolver import with_repository_provider
from src.utils.log import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/release/aggregate-note")


def get_aggregate_release_note_service() -> AggregateReleaseNoteService:
    """Dependency provider for AggregateReleaseNoteService."""
    return AggregateReleaseNoteService()


@router.post(
    "/build",
    response_model=AggregateReleaseNoteResponse,
    summary="Build the combined release note for an application and its packages",
    description=(
        "The note one release actually deserves when the application pins packages:\n\n"
        "* `application` - the app's own comparison between `source_ref` and `target_ref`, "
        "with a rendered release note body and one optional AI summary.\n"
        "* `packages` - one entry per package the dependency database says the span moved, "
        "compared between its two pinned versions and rendered like a release note. "
        "Packages that cannot be compared are `skipped` with the reason; a provider "
        "failure is `failed` and never takes the note down.\n"
        "* `unchanged_packages` - every package both versions hold at the same version.\n\n"
        "An application with no dependency record degrades to a monolithic note "
        "(`dependency_source = 'none'`): the application's own comparison only."
    ),
)
async def build_aggregate_note(
    payload: AggregateReleaseNoteRequest,
    access: CurrentRepositoryAccess,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[AggregateReleaseNoteService, Depends(get_aggregate_release_note_service)],
) -> AggregateReleaseNoteResponse:
    payload = await with_repository_provider(payload, db)
    logger.info(
        "Building aggregate release note",
        extra={
            "app_name": payload.app_name,
            "project_key": payload.project_key,
            "repository_slug": payload.repository_slug,
            "source_ref": payload.source_ref,
            "target_ref": payload.target_ref,
        },
    )
    try:
        return await service.build(payload, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_request", "message": str(e)},
        )


@router.post(
    "/plan",
    response_model=AggregateNotePlanResponse,
    summary="Preview the dependency versions an application version span carries",
    description=(
        "What the dependency database says each ref of the application declares, "
        "before any note is built: the declared pins of the source and target "
        "versions, one entry per package the span moved (with the version it "
        "moves from and to), and the packages held unchanged. Two dependency "
        "lookups and a classification - no repository resolution, no commit "
        "comparison, no AI - so it answers while the release is still being "
        "typed. Only applications get a plan; anything else is refused."
    ),
)
async def plan_aggregate_note(
    payload: AggregateReleaseNoteRequest,
    access: CurrentRepositoryAccess,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[AggregateReleaseNoteService, Depends(get_aggregate_release_note_service)],
) -> AggregateNotePlanResponse:
    payload = await with_repository_provider(payload, db)
    try:
        return await service.plan(payload, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_request", "message": str(e)},
        )
