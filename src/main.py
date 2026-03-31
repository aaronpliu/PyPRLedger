from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
async def lifespan(app: FastAPI) -> AsyncGenerator:
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
app = FastAPI(
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
    """Request validation exception handler"""
    logger.error("Validation error", extra={"request": str(request)})

    # Convert validation errors to simple strings to ensure JSON serialization
    detail = "Validation failed"
    try:
        error_list = exc.errors()
        # Just convert the entire error list to string representation
        detail = str(error_list)
    except Exception as e:
        detail = f"Error: {str(e)}"

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": ErrorCode.VALIDATION_ERROR,
            "message": "Request validation failed",
            "detail": detail,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """General exception handler"""
    import traceback

    error_traceback = traceback.format_exc()
    logger.error(
        f"Unexpected error: {str(exc)}\n{error_traceback}", extra={"request": str(request)}
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
