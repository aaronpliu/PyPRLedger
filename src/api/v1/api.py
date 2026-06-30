from fastapi import APIRouter

from src import __version__
from src.api.v1.endpoints import (
    audit,
    auth,
    auto_task_assignment,  # Auto-assignment rule management
    delegation,
    llm_proxy,
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

# SSE streaming endpoint — mounted at /api/v1/sse/stream
# Uses separate prefix to avoid route conflicts with reviews router
api_router.include_router(sse.router, prefix="/sse", tags=["sse"])

# Task assignment endpoints (for review_admin to manage reviews)
api_router.include_router(task_assignment.router, tags=["task-assignment"])

# Auto-assignment rule management (for review_admin)
api_router.include_router(auto_task_assignment.router, tags=["auto-task-assignment"])

api_router.include_router(users.git_router, prefix="/users/git", tags=["git-users"])
api_router.include_router(users.auth_router, prefix="/users/auth", tags=["auth-users"])

api_router.include_router(projects.router, prefix="/projects", tags=["projects"])

api_router.include_router(project_registry.router, tags=["project-registry"])

# Notification management endpoints
api_router.include_router(notifications.router, tags=["notifications"])

# Personal Access Token management endpoints
api_router.include_router(personal_access_tokens.router, tags=["personal-access-tokens"])

# Global search endpoint
api_router.include_router(search.router, prefix="/search", tags=["search"])

# LLM Proxy endpoint (for PageAgent AI assistant)
api_router.include_router(llm_proxy.router, tags=["llm-proxy"])


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
