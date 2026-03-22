from fastapi import APIRouter
from src.api.v1.endpoints import reviews, users, projects

api_router = APIRouter()

# 包含各个子路由
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])

api_router.include_router(users.router, prefix="/users", tags=["users"])

api_router.include_router(projects.router, prefix="/projects", tags=["projects"])


# API信息端点
@api_router.get("/info")
async def api_info():
    """获取API信息"""
    return {
        "name": "Pull Request Code Review System API",
        "version": "1.0.0",
        "description": "FastAPI-based Pull Request Code Review System",
        "endpoints": {
            "reviews": "/api/v1/reviews",
            "users": "/api/v1/users",
            "projects": "/api/v1/projects",
        },
    }
