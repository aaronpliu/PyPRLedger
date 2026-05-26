from fastapi import APIRouter

from src import __version__
from src.api.v1.endpoints import (
    audit,
    auth,
    delegation,
    notifications,  # Notification management endpoints
    personal_access_tokens,
    project_registry,
    projects,
    rbac,
    reviews,
    search,  # Global search endpoint
    sse,  # SSE streaming endpoint for real-time review notifications
    task_assignment,  # Task assignment endpoints for review_admin
    users,
)


api_router = APIRouter()

# Include routers for different endpoints
api_router.include_router(auth.router, tags=["authentication"])

api_router.include_router(audit.router, tags=["audit-logs"])

api_router.include_router(rbac.router, tags=["rbac-management"])

api_router.include_router(delegation.router, prefix="/rbac/delegations", tags=["role-delegations"])

api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])

# SSE streaming endpoint — mounted at /api/v1/reviews/stream
api_router.include_router(sse.router, prefix="/reviews", tags=["sse"])

# Task assignment endpoints (for review_admin to manage reviews)
api_router.include_router(task_assignment.router, tags=["task-assignment"])

api_router.include_router(users.router, prefix="/users", tags=["users"])

api_router.include_router(projects.router, prefix="/projects", tags=["projects"])

api_router.include_router(project_registry.router, tags=["project-registry"])

# Notification management endpoints
api_router.include_router(notifications.router, tags=["notifications"])

# Personal Access Token management endpoints
api_router.include_router(personal_access_tokens.router, tags=["personal-access-tokens"])

# Global search endpoint
api_router.include_router(search.router, prefix="/search", tags=["search"])


# API information endpoint
@api_router.get("/info")
async def api_info():
    """Get API information including version"""
    return {
        "name": "Pull Request Code Review Result Storage System API",
        "version": __version__,
        "description": "FastAPI-based Pull Request Code Review Result Storage System",
        "docs": "/api/docs",
    }
