from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from src import __version__
from src.core.config import settings
from src.core.exceptions import AppException, ErrorCode
from src.core.middleware import LoggingMiddleware, RateLimitMiddleware
from src.api.v1.api import api_router
from src.core.database import init_db, close_db
from src.utils.redis import init_redis, close_redis
from src.utils.metrics import MetricsCollector
from src.utils.log import setup_logging, get_logger

# 配置日志系统
setup_logging()
logger = get_logger(__name__)


# 初始化指标收集器
metrics_collector = MetricsCollector()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """应用程序生命周期管理"""
    # 启动时执行
    logger.info("Starting application...")
    await init_db()
    await init_redis()
    metrics_collector.startup()
    logger.info("Application started successfully")

    yield

    # 关闭时执行
    logger.info("Shutting down application...")
    await close_db()
    await close_redis()
    metrics_collector.shutdown()
    logger.info("Application shutdown complete")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Pull Request Code Review System API",
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加自定义中间件
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=settings.RATE_LIMIT_MAX_REQUESTS)

# 集成Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# 注册API路由
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """自定义应用异常处理"""
    logger.error(
        f"Application error occurred: {exc.code} - {exc.message}", extra={"request": str(request)}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message, "detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """请求验证异常处理"""
    logger.error(f"Validation error: {exc.errors()}", extra={"request": str(request)})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": ErrorCode.VALIDATION_ERROR,
            "message": "Request validation failed",
            "detail": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理"""
    logger.error(f"Unexpected error: {str(exc)}", extra={"request": str(request)})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": ErrorCode.INTERNAL_SERVER_ERROR,
            "message": "An unexpected error occurred",
            "detail": str(exc) if settings.DEBUG else None,
        },
    )


@app.get("/health")
async def health_check() -> dict:
    """健康检查端点"""
    return {"status": "healthy", "version": __version__}


@app.get("/")
async def root() -> dict:
    """根路径"""
    return {
        "message": "Pull Request Code Review Result Storage System API",
        "version": __version__,
        "docs": "/api/docs",
    }
