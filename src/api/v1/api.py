from fastapi import APIRouter

from src import __version__
from src.api.v1.endpoints import audit, auth, project_registry, projects, rbac, reviews, users


api_router = APIRouter()

# Include routers for different endpoints
api_router.include_router(auth.router, tags=["authentication"])

api_router.include_router(audit.router, tags=["audit-logs"])

api_router.include_router(rbac.router, tags=["rbac-management"])

api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])

api_router.include_router(users.router, prefix="/users", tags=["users"])

api_router.include_router(projects.router, prefix="/projects", tags=["projects"])

api_router.include_router(project_registry.router, tags=["project-registry"])


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
