import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.services.project_registry_service import ProjectRegistryService


logger = logging.getLogger(__name__)

router = APIRouter()


def get_registry_service() -> ProjectRegistryService:
    """Get project registry service instance"""
    return ProjectRegistryService()


# ==================== Public Endpoints ====================


@router.get("/apps", response_model=list[dict])
async def list_all_apps(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    registry_service: Annotated[ProjectRegistryService, Depends(get_registry_service)],
):
    """
    List all registered applications with their project counts

    Returns:
        List of apps with app_name and project_count
    """
    try:
        apps = await registry_service.list_all_apps(db)
        return apps
    except Exception as e:
        logger.error(f"Failed to list apps: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to list applications"},
        )


@router.get("/apps/{app_name}/projects", response_model=list[dict])
async def list_projects_by_app(
    app_name: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    registry_service: Annotated[ProjectRegistryService, Depends(get_registry_service)],
):
    """
    List all projects registered to a specific application

    Args:
        app_name: The application name
    """
    try:
        projects = await registry_service.list_projects_by_app(app_name, db)
        return [
            {
                "id": p.id,
                "app_name": p.app_name,
                "project_key": p.project_key,
                "repository_slug": p.repository_slug,
                "description": p.description,
                "created_date": p.created_date.isoformat(),
                "updated_date": p.updated_date.isoformat(),
            }
            for p in projects
        ]
    except Exception as e:
        logger.error(f"Failed to list projects for app {app_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to list projects"},
        )


@router.get("/projects/{project_key}/{repository_slug}/app-name", response_model=dict)
async def get_project_app_name(
    project_key: str,
    repository_slug: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    registry_service: Annotated[ProjectRegistryService, Depends(get_registry_service)],
):
    """
    Get the application name for a specific project-repository pair

    Args:
        project_key: The project key
        repository_slug: The repository slug

    Returns:
        Dict with app_name field
    """
    try:
        app_name = await registry_service.get_app_name(project_key, repository_slug, db)
        return {"app_name": app_name}
    except Exception as e:
        logger.error(f"Failed to get app name for {project_key}/{repository_slug}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to resolve app name"},
        )


# ==================== Admin Endpoints ====================
# TODO: Add authentication and authorization middleware


@router.post("/admin/registry/register", response_model=dict)
async def register_project_to_app(
    app_name: Annotated[str, Query(min_length=1, max_length=64, description="Application name")],
    project_key: Annotated[str, Query(min_length=1, max_length=32, description="Project key")],
    repository_slug: Annotated[
        str, Query(min_length=1, max_length=128, description="Repository slug")
    ],
    description: Annotated[
        str | None, Query(max_length=255, description="Optional description")
    ] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
    registry_service: Annotated[ProjectRegistryService, Depends(get_registry_service)] = None,
):
    """
    Register a project-repository pair to an application (Admin only)

    Args:
        app_name: Application name
        project_key: Project key
        repository_slug: Repository slug
        description: Optional description

    Returns:
        Dict with registration details

    Raises:
        HTTPException: If already registered to different app
    """
    # TODO: Add admin authentication check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")

    try:
        registry = await registry_service.register_project(
            app_name, project_key, repository_slug, description, db
        )
        return {
            "message": "Successfully registered",
            "app_name": registry.app_name,
            "project_key": registry.project_key,
            "repository_slug": registry.repository_slug,
            "description": registry.description,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "CONFLICT", "message": str(e)},
        )
    except Exception as e:
        logger.error(f"Failed to register project: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to register project"},
        )


@router.put("/admin/registry/update", response_model=dict)
async def update_project_app(
    project_key: Annotated[str, Query(min_length=1, max_length=32, description="Project key")],
    repository_slug: Annotated[
        str, Query(min_length=1, max_length=128, description="Repository slug")
    ],
    new_app_name: Annotated[
        str, Query(min_length=1, max_length=64, description="New application name")
    ],
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
    registry_service: Annotated[ProjectRegistryService, Depends(get_registry_service)] = None,
):
    """
    Move a project-repository pair to a different application (Admin only)

    Args:
        project_key: Project key
        repository_slug: Repository slug
        new_app_name: New application name

    Returns:
        Dict with update details
    """
    # TODO: Add admin authentication check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")

    try:
        registry = await registry_service.update_project_app(
            project_key, repository_slug, new_app_name, db
        )
        return {
            "message": "Successfully updated",
            "project_key": registry.project_key,
            "repository_slug": registry.repository_slug,
            "old_app_name": "Unknown",  # Would need to track this
            "new_app_name": registry.app_name,
        }
    except Exception as e:
        logger.error(f"Failed to update project app: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to update assignment"},
        )


@router.delete("/admin/registry/unregister", response_model=dict)
async def unregister_project(
    project_key: Annotated[str, Query(min_length=1, max_length=32, description="Project key")],
    repository_slug: Annotated[
        str, Query(min_length=1, max_length=128, description="Repository slug")
    ],
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
    registry_service: Annotated[ProjectRegistryService, Depends(get_registry_service)] = None,
):
    """
    Remove a project-repository pair from registry (Admin only)

    Args:
        project_key: Project key
        repository_slug: Repository slug

    Returns:
        Dict with unregistration details
    """
    # TODO: Add admin authentication check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")

    try:
        success = await registry_service.unregister_project(project_key, repository_slug, db)
        if success:
            return {
                "message": "Successfully unregistered",
                "project_key": project_key,
                "repository_slug": repository_slug,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Project {project_key}/{repository_slug} not found in registry",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unregister project: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to unregister project"},
        )
