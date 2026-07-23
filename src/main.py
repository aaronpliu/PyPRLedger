import asyncio
import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import psutil
from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_offline import FastAPIOffline
from prometheus_fastapi_instrumentator import Instrumentator

from src import __version__
from src.api import api_router
from src.core.config import settings
from src.core.database import close_db, get_db_context, init_db
from src.core.exceptions import AppException
from src.core.middleware import (
    ApiDocsVisibilityMiddleware,
    DatabaseConnectionMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
)
from src.services.project_service import ProjectService
from src.services.rbac_service import RBACService
from src.services.sse_broker import get_sse_broker
from src.services.user_service import UserService
from src.utils.i18n import i18n
from src.utils.log import get_logger, setup_logging
from src.utils.metrics import metrics as metrics_collector
from src.utils.redis import close_redis, init_redis


# Configure logging system
setup_logging()
logger = get_logger(__name__)

# Background task management
background_tasks: list[asyncio.Task] = []


async def delegation_status_cleanup_task():
    """Background task to automatically update delegation statuses in real-time

    This task runs continuously and checks for:
    1. Pending delegations that should become active (starts_at <= now)
    2. Active delegations that should expire (expires_at <= now)

    Runs every 5 minutes by default.
    """
    cleanup_interval = 300  # 5 minutes

    while True:
        try:
            async with get_db_context() as db:
                rbac_service = RBACService(db)

                # Update expired delegations (active -> expired)
                expired_count = await rbac_service.update_expired_delegations()
                if expired_count > 0:
                    logger.info(f"Auto-updated {expired_count} expired delegations")

                # Activate pending delegations (pending -> active)
                activated_count = await rbac_service.activate_pending_delegations()
                if activated_count > 0:
                    logger.info(f"Auto-activated {activated_count} pending delegations")

        except Exception as e:
            # Check if this is a database disconnection error
            from sqlalchemy.exc import DBAPIError

            if isinstance(e, DBAPIError) and getattr(e, "connection_invalidated", False):
                logger.warning(
                    "Database connection invalidated in delegation cleanup task. Pool will replace it.",
                    exc_info=False,
                )
            else:
                # Log other exceptions with full traceback
                logger.error(f"Error in delegation status cleanup task: {e}", exc_info=True)

        # Wait before next check
        await asyncio.sleep(cleanup_interval)


async def system_metrics_collection_task():
    """Background task to collect system metrics (CPU, memory, disk) every 60s."""
    logger = get_logger(__name__)
    interval = 60

    while True:
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics_collector.set_cpu_usage(cpu_percent)

            # Memory
            mem = psutil.virtual_memory()
            metrics_collector.set_memory_usage(mem.used)
            metrics_collector.set_memory_available(mem.available)

            # Disk
            disk = psutil.disk_usage("/")
            metrics_collector.set_disk_usage("/", disk.used)
            metrics_collector.set_disk_available("/", disk.free)

            logger.debug(
                "System metrics collected",
                extra={
                    "cpu_percent": cpu_percent,
                    "memory_used": mem.used,
                    "memory_available": mem.available,
                    "disk_used": disk.used,
                    "disk_free": disk.free,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to collect system metrics: {e}", exc_info=True)

        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPIOffline) -> AsyncGenerator:
    """Application lifecycle management"""
    # Startup operations
    logger.info("Starting application...")
    await init_db()
    await init_redis()
    metrics_collector.startup()

    # Initialize metrics with real values from database
    try:
        async with get_db_context() as db:
            user_service = UserService()
            project_service = ProjectService()
            await user_service.get_user_statistics(db, use_cache=False)
            await project_service.get_project_statistics(db, use_cache=False)
        logger.info("Initial metrics loaded from database")
    except Exception as e:
        logger.warning(f"Failed to initialize metrics from database: {e}")

    # Start background tasks
    logger.info("Starting background tasks...")
    delegation_cleanup = asyncio.create_task(delegation_status_cleanup_task())
    background_tasks.append(delegation_cleanup)
    logger.info("Background delegation cleanup task started (interval: 5 minutes)")
    system_metrics = asyncio.create_task(system_metrics_collection_task())
    background_tasks.append(system_metrics)
    logger.info("System metrics collection task started (interval: 60 seconds)")

    logger.info("Application started successfully")

    yield

    # Shutdown operations
    logger.info("Shutting down application...")

    # Cancel background tasks
    logger.info("Cancelling background tasks...")
    for task in background_tasks:
        task.cancel()

    # Wait for tasks to finish
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)
        logger.info("All background tasks cancelled")

    await close_db()
    await close_redis()
    await get_sse_broker().stop()  # Stop SSE broker (shared pubsub subscription)

    metrics_collector.shutdown()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPIOffline(
    title=settings.PROJECT_NAME,
    description="Pull Request Code Review Result Storage System API",
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    static_url="/api/static-offline-docs",  # Offline docs, outer nginx proxy with same-origin
    swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect",  # Offline docs
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(ApiDocsVisibilityMiddleware)
app.add_middleware(DatabaseConnectionMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=settings.RATE_LIMIT_MAX_REQUESTS)

# Integrate Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint=settings.PROMETHEUS_METRICS_PATH)

# Register API routes
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount static files for avatar uploads
avatar_upload_dir = Path(settings.AVATAR_UPLOAD_DIR)
avatar_upload_dir.mkdir(parents=True, exist_ok=True)
app.mount(settings.AVATAR_BASE_URL, StaticFiles(directory=str(avatar_upload_dir)), name="avatars")


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Custom application exception handler with i18n support"""
    # Detect language from request
    lang = i18n.get_language_from_request(request)

    # Get translated message
    message = exc.get_message(lang)

    # Log detailed error information
    severity = "🔴 ERROR" if exc.status_code >= 500 else "🟠 CLIENT ERROR"

    detail = exc.detail if isinstance(exc.detail, dict) else {}
    error_code = detail.get("error", "unknown_error")

    log_message = (
        f"\n{'=' * 80}\n"
        f"{severity} - Application Exception\n"
        f"{'=' * 80}\n"
        f"  Request:     {request.method} {request.url.path}\n"
        f"  Client IP:   {request.client.host if request.client else 'unknown'}\n"
        f"  Language:    {lang}\n"
        f"  Status Code: {exc.status_code}\n"
        f"  Error Code:  {error_code}\n"
        f"  Message:     {message}"
    )

    if detail and len(detail) > 1:
        detail_items = [f"{k}={v}" for k, v in detail.items() if k != "message"]
        if detail_items:
            log_message += f"\n  Details:     {', '.join(detail_items)}"

    log_message += f"\n  Exception:   {type(exc).__name__}\n{'=' * 80}"

    logger.error(log_message, extra={"request": str(request)})

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": error_code,
            "message": message,
            "detail": detail if detail != {"error": error_code, "message": message} else None,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI built-in HTTP exceptions (4xx errors)"""
    # Log detailed error information
    logger.error(
        f"\n{'=' * 80}\n"
        f"🟠 CLIENT ERROR - HTTP Exception\n"
        f"{'=' * 80}\n"
        f"  Request:     {request.method} {request.url.path}\n"
        f"  Client IP:   {request.client.host if request.client else 'unknown'}\n"
        f"  Status Code: {exc.status_code}\n"
        f"  Error Code:  HTTP_{exc.status_code}\n"
        f"  Message:     {str(exc.detail) if hasattr(exc, 'detail') and exc.detail else f'HTTP {exc.status_code} Error'}\n"
        f"  Details:     {exc.detail if hasattr(exc, 'detail') else None}\n"
        f"  Exception:   HTTPException\n"
        f"{'=' * 80}",
        extra={"request": str(request)},
    )

    # Return standard FastAPI error response format
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail if hasattr(exc, "detail") else None,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Request validation exception handler"""
    # Convert validation errors to detailed format
    error_list = []
    try:
        for error in exc.errors():
            error_info = {
                "field": ".".join(str(x) for x in error.get("loc", [])),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            }
            error_list.append(error_info)
    except Exception as e:
        logger.error(f"Failed to parse validation errors: {str(e)}")
        error_list = [{"field": "unknown", "message": str(exc), "type": "parse_error"}]

    # Log detailed error information
    logger.error(
        f"\n{'=' * 80}\n"
        f"🟠 CLIENT ERROR - Validation Error\n"
        f"{'=' * 80}\n"
        f"  Request:     {request.method} {request.url.path}\n"
        f"  Client IP:   {request.client.host if request.client else 'unknown'}\n"
        f"  Status Code: 422\n"
        f"  Error Code:  validation_error\n"
        f"  Message:     Request validation failed\n"
        f"  Validation Errors:\n"
        + "".join([f"    - Field '{err['field']}': {err['message']}\n" for err in error_list])
        + f"  Exception:   RequestValidationError\n"
        f"{'=' * 80}",
        extra={"request": str(request)},
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "detail": {"errors": error_list},
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """General exception handler"""
    error_traceback = traceback.format_exc()

    # Log detailed error information with full stack trace
    logger.error(
        f"\n{'=' * 80}\n"
        f"🔴 ERROR - Unexpected Exception\n"
        f"{'=' * 80}\n"
        f"  Request:     {request.method} {request.url.path}\n"
        f"  Client IP:   {request.client.host if request.client else 'unknown'}\n"
        f"  Status Code: 500\n"
        f"  Error Code:  internal_server_error\n"
        f"  Message:     {str(exc)}\n"
        f"  Exception:   {type(exc).__name__}\n"
        f"\n  Stack Trace:\n"
        f"  {'-' * 76}\n"
        f"  {error_traceback}\n"
        f"  {'-' * 76}\n"
        f"{'=' * 80}",
        extra={"request": str(request)},
    )

    # Safely convert exception to string for JSON serialization
    detail = None
    if settings.DEBUG:
        try:
            detail = str(exc)
        except Exception:
            detail = f"Error converting exception to string: {type(exc).__name__}"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "detail": detail,
        },
    )


@app.get("/api/health")
async def health_check() -> dict:
    """Health check endpoint"""
    return {"status": "healthy", "version": __version__}
