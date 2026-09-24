"""Release diff endpoints.

Exposes two read-only operations over the git provider compare API:

* ``POST /release/diff/compare`` - compare two release refs and report whether
  every commit of the old release is contained in the new release.
* ``POST /release/diff/check``   - check whether one or more commits belong to
  a target release.

Both endpoints are backed by the Bitbucket Server ``compare/commits`` REST API
(or the GitHub Enterprise equivalent) through the provider abstraction.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.core.exceptions import GitServiceException
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.release_diff import (
    ReleaseCommitCheckRequest,
    ReleaseCommitCheckResponse,
    ReleaseCompareRequest,
    ReleaseCompareResponse,
)
from src.services.release_diff_service import ReleaseDiffService
from src.utils.log import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/release/diff")


def get_release_diff_service() -> ReleaseDiffService:
    """Dependency provider for ReleaseDiffService."""
    return ReleaseDiffService()


@router.post(
    "/compare",
    response_model=ReleaseCompareResponse,
    summary="Compare two release versions",
    description=(
        "Compare an old release ref against a new release ref and report whether every "
        "old release commit is reachable from the new release. Uses the Bitbucket Server "
        "`/rest/api/latest/projects/{projectKey}/repos/{repositorySlug}/compare/commits` "
        "endpoint under the hood.\n\n"
        "`old_release_ref` / `new_release_ref` answer the containment question "
        "(is the old release fully included in the new one).\n\n"
        "`old_release_base_ref` / `new_release_base_ref` are optional and only narrow the "
        "commit set that counts as *belonging to* each release: with a base ref the release "
        "scope is `base_ref..release_ref`, without it every commit reachable from the "
        "release ref is used (capped by `max_commits`). Example - consecutive releases "
        "v1.1.0 -> v1.2.0 -> v1.3.0:\n"
        "```json\n"
        "{\n"
        '  "old_release_ref": "v1.2.0", "old_release_base_ref": "v1.1.0",\n'
        '  "new_release_ref": "v1.3.0", "new_release_base_ref": "v1.2.0"\n'
        "}\n"
        "```"
    ),
)
async def compare_releases(
    payload: ReleaseCompareRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[ReleaseDiffService, Depends(get_release_diff_service)],
) -> ReleaseCompareResponse:
    """Compare two releases and return missing / added commits."""
    try:
        return await service.compare_releases(payload)
    except GitServiceException as e:
        logger.error(
            "Git provider failed while comparing releases",
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


@router.post(
    "/check",
    response_model=ReleaseCommitCheckResponse,
    summary="Check commits against a target release",
    description=(
        "Verify whether one or more commits (full or short SHA) are part of a target "
        "release. Optionally scope the release to the commits between "
        "`target_release_base_ref` and `target_release_ref`."
    ),
)
async def check_release_commits(
    payload: ReleaseCommitCheckRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[ReleaseDiffService, Depends(get_release_diff_service)],
) -> ReleaseCommitCheckResponse:
    """Check whether the requested commits belong to the target release."""
    try:
        return await service.check_commits(payload)
    except GitServiceException as e:
        logger.error(
            "Git provider failed while checking release commits",
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
