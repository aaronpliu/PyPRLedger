"""Aggregate release note endpoints.

One note for an application version span and the packages it moved:

* ``POST /release/aggregate-note/build`` - the packages the application
  carries come from the project registry (the registrations grouped under its
  name that are marked as packages), and each package's ``from`` and ``to``
  versions are read off its own tag timeline: the newest tag it had released
  by each end of the span. A package the span moved is compared between those
  two versions with the same release diff the release pages use, and the
  application's own comparison rides along as the note's first section. No
  dependency database is involved.

A package that cannot be compared stays legible: it is ``skipped`` with the
reason (not registered, nothing released in the span, an undated span ref) or
``failed`` with the provider error - never silently missing, never guessed at.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import CurrentRepositoryAccess, get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.aggregate_release_note import (
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
        "The note one release actually deserves when the application carries packages:\n\n"
        "* `application` - the app's own comparison between `source_ref` and `target_ref`.\n"
        "* `packages` - one entry per package the span moved, compared between the two "
        "versions its own tag timeline places at each end of the span. Packages the "
        "registry cannot settle on are `skipped` with the reason; a provider failure is "
        "`failed` and never takes the note down.\n"
        "* `unchanged_packages` - every package that held the same version across the span.\n\n"
        "The package list comes from the project registry; no dependency database is asked."
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
    return await service.build(payload, db)
