from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_offline import FastAPIOffline
from prometheus_fastapi_instrumentator import Instrumentator

from src import __version__
from src.api.v1.api import api_router
from src.core.config import settings
from src.core.database import close_db, init_db
from src.core.exceptions import AppException, ErrorCode
from src.core.middleware import LoggingMiddleware, RateLimitMiddleware
from src.utils.log import get_logger, setup_logging
from src.utils.metrics import MetricsCollector
from src.utils.redis import close_redis, init_redis


# Configure logging system
setup_logging()
logger = get_logger(__name__)


# Initialize metrics collector
metrics_collector = MetricsCollector()


@asynccontextmanager
async def lifespan(app: FastAPIOffline) -> AsyncGenerator:
    """Application lifecycle management"""
    # Startup operations
    logger.info("Starting application...")
    await init_db()
    await init_redis()
    metrics_collector.startup()
    logger.info("Application started successfully")

    yield

    # Shutdown operations
    logger.info("Shutting down application...")
    await close_db()
    await close_redis()
    metrics_collector.shutdown()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPIOffline(
    title=settings.PROJECT_NAME,
    description="Pull Request Code Review Result Storage System API",
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
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
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=settings.RATE_LIMIT_MAX_REQUESTS)

# Integrate Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Register API routes
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Custom application exception handler"""
    # Log detailed error information
    severity = "🔴 ERROR" if exc.status_code >= 500 else "🟠 CLIENT ERROR"

    log_message = (
        f"\n{'=' * 80}\n"
        f"{severity} - Application Exception\n"
        f"{'=' * 80}\n"
        f"  Request:     {request.method} {request.url.path}\n"
        f"  Client IP:   {request.client.host if request.client else 'unknown'}\n"
        f"  Status Code: {exc.status_code}\n"
        f"  Error Code:  {exc.code}\n"
        f"  Message:     {exc.message}"
    )

    if exc.detail:
        if isinstance(exc.detail, dict):
            detail_items = [f"{k}={v}" for k, v in exc.detail.items()]
            log_message += f"\n  Details:     {', '.join(detail_items)}"
        else:
            log_message += f"\n  Detail:      {exc.detail}"

    log_message += f"\n  Exception:   {type(exc).__name__}\n{'=' * 80}"

    logger.error(log_message, extra={"request": str(request)})

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message, "detail": exc.detail},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI built-in HTTP exceptions (4xx errors)"""
    message = (
        str(exc.detail)
        if hasattr(exc, "detail") and exc.detail
        else f"HTTP {exc.status_code} Error"
    )

    # Log detailed error information
    logger.error(
        f"\n{'=' * 80}\n"
        f"🟠 CLIENT ERROR - HTTP Exception\n"
        f"{'=' * 80}\n"
        f"  Request:     {request.method} {request.url.path}\n"
        f"  Client IP:   {request.client.host if request.client else 'unknown'}\n"
        f"  Status Code: {exc.status_code}\n"
        f"  Error Code:  HTTP_{exc.status_code}\n"
        f"  Message:     {message}\n"
        f"  Details:     {exc.detail if hasattr(exc, 'detail') else None}\n"
        f"  Exception:   HTTPException\n"
        f"{'=' * 80}",
        extra={"request": str(request)},
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": f"HTTP_{exc.status_code}",
            "message": message,
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
        f"  Error Code:  VALIDATION_ERROR\n"
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
            "error": ErrorCode.VALIDATION_ERROR,
            "message": "Request validation failed",
            "detail": {"errors": error_list},
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """General exception handler"""
    import traceback

    error_traceback = traceback.format_exc()

    # Log detailed error information with full stack trace
    logger.error(
        f"\n{'=' * 80}\n"
        f"🔴 ERROR - Unexpected Exception\n"
        f"{'=' * 80}\n"
        f"  Request:     {request.method} {request.url.path}\n"
        f"  Client IP:   {request.client.host if request.client else 'unknown'}\n"
        f"  Status Code: 500\n"
        f"  Error Code:  INTERNAL_SERVER_ERROR\n"
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
            "error": ErrorCode.INTERNAL_SERVER_ERROR,
            "message": "An unexpected error occurred",
            "detail": detail,
        },
    )


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint"""
    return {"status": "healthy", "version": __version__}


@app.get("/")
async def root() -> dict:
    """Root path"""
    return {
        "message": "Pull Request Code Review Result Storage System API",
        "version": __version__,
        "docs": "/api/docs",
    }
