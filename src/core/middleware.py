import logging
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.core.config import settings
from src.core.exceptions import RateLimitException
from src.utils.redis import get_redis_client


logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Request logging middleware"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Record request start time
        start_time = time.time()

        # Record request information
        client_ip = request.client.host if request.client else "unknown"
        request_headers = dict(request.headers)

        # Filter sensitive headers
        sensitive_headers = ["authorization", "x-api-key", "cookie"]
        for header in sensitive_headers:
            if header.lower() in request_headers:
                request_headers[header.lower()] = "*****"

        logger.info(
            f"Incoming request: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_ip": client_ip,
                "headers": request_headers,
                "user_agent": request.headers.get("user-agent", "unknown"),
            },
        )

        # Process request
        try:
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}"

            # Record response information
            logger.info(
                f"Request completed: {request.method} {request.url.path} - Status: {response.status_code}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time": process_time,
                    "client_ip": client_ip,
                },
            )

            return response

        except Exception as exc:
            # Calculate processing time
            process_time = time.time() - start_time

            # Record exception
            logger.error(
                f"Request failed: {request.method} {request.url.path} - Error: {str(exc)}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "process_time": process_time,
                    "client_ip": client_ip,
                },
                exc_info=True,
            )
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = None,
        period_seconds: int = None,
        redis_client=None,
        enabled: bool = None,
    ):
        super().__init__(app)
        self.max_requests = max_requests or settings.RATE_LIMIT_MAX_REQUESTS
        self.period_seconds = period_seconds or settings.RATE_LIMIT_PERIOD_SECONDS
        self.enabled = enabled if enabled is not None else settings.RATE_LIMIT_ENABLED
        self.redis_client = redis_client

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # If rate limiting is disabled, process request directly
        if not self.enabled:
            return await call_next(request)

        # Get client identifier (use IP address)
        client_ip = request.client.host if request.client else "unknown"

        # Get Redis client (if not provided, create new connection)
        redis = self.redis_client
        if redis is None:
            redis = get_redis_client()

        try:
            # Build rate limit key
            rate_limit_key = f"rate_limit:{client_ip}"

            # Get current count
            current_count = await redis.incr(rate_limit_key)

            # If first request, set expiration time
            if current_count == 1:
                await redis.expire(rate_limit_key, self.period_seconds)

            # Check if limit exceeded
            if current_count > self.max_requests:
                logger.warning(
                    f"Rate limit exceeded for client {client_ip}: {current_count}/{self.max_requests} requests",
                    extra={
                        "client_ip": client_ip,
                        "current_count": current_count,
                        "max_requests": self.max_requests,
                        "period_seconds": self.period_seconds,
                    },
                )
                raise RateLimitException(
                    message=f"Rate limit exceeded. Maximum {self.max_requests} requests per {self.period_seconds} seconds"
                )

            # Add rate limit information to request state
            request.state.rate_limit = {
                "current": current_count,
                "limit": self.max_requests,
                "remaining": self.max_requests - current_count,
                "reset": await redis.ttl(rate_limit_key),
            }

            # Process request
            response = await call_next(request)

            # Add rate limit information to response headers
            rate_limit = request.state.rate_limit
            response.headers["X-RateLimit-Limit"] = str(rate_limit["limit"])
            response.headers["X-RateLimit-Remaining"] = str(rate_limit["remaining"])
            response.headers["X-RateLimit-Reset"] = str(rate_limit["reset"])

            return response

        except RateLimitException:
            raise
        except Exception as exc:
            logger.warning(f"Rate limiting error (Redis): {str(exc)}")
            # Don't block request when error occurs
            return await call_next(request)


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Cache control middleware"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Process request
        response = await call_next(request)

        # Set cache strategy based on request method and path
        if request.method == "GET":
            # Set appropriate cache strategy for GET requests
            if request.url.path.startswith("/api/v1/reviews"):
                # Review list can be cached for short time
                response.headers["Cache-Control"] = "private, max-age=60"
            elif request.url.path.startswith("/api/v1/projects"):
                # Project information can be cached for longer time
                response.headers["Cache-Control"] = "private, max-age=300"
            else:
                # Other GET requests default to no cache
                response.headers["Cache-Control"] = "no-store"
        else:
            # Non-GET requests disable caching
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Security headers middleware"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Process request
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Request timing middleware"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Record start time
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Add processing time to response headers
        response.headers["X-Response-Time"] = f"{process_time:.4f}s"

        return response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Request ID middleware"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Try to get request ID from headers
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Add to request state
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class DatabaseConnectionMiddleware(BaseHTTPMiddleware):
    """Database connection health check middleware

    This middleware ensures that database connections are valid before processing requests.
    It handles the case where database connections become stale after periods of inactivity,
    particularly important for background tasks like delegation_status_cleanup_task.

    Instead of pinging the database on every request, it catches disconnection errors
    and triggers reconnection when needed.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            # Process the request normally
            response = await call_next(request)
            return response

        except Exception as exc:
            # Check if this is a database disconnection error
            from sqlalchemy.exc import DBAPIError

            if isinstance(exc, DBAPIError) and getattr(exc, "connection_invalidated", False):
                logger.warning(
                    "Database connection invalidated detected, attempting to recover...",
                    extra={
                        "request_id": getattr(request.state, "request_id", "unknown"),
                        "method": request.method,
                        "path": request.url.path,
                    },
                )

                # Dispose the old engine to force recreation of connections
                from src.core.database import get_engine

                try:
                    engine = get_engine()
                    await engine.dispose()
                    logger.info("Database engine disposed successfully")
                except Exception as dispose_error:
                    logger.error(
                        f"Failed to dispose database engine: {dispose_error}", exc_info=True
                    )

                # Re-raise the exception to be handled by exception handlers
                # The next attempt will create fresh connections
                raise

            # For non-database errors, re-raise as-is
            raise


class ApiDocsVisibilityMiddleware(BaseHTTPMiddleware):
    """Middleware to hide API documentation endpoints in production

    When ENABLE_API_DOCS is False, blocks access to:
    - /api/docs (Swagger UI)
    - /api/redoc (ReDoc)
    - /api/openapi.json (OpenAPI schema)
    - /api/static-offline-docs/* (Offline documentation assets)
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # Paths to block when docs are disabled
        self.blocked_paths = [
            "/api/docs",
            "/api/docs/",
            "/api/redoc",
            "/api/redoc/",
            "/api/openapi.json",
            "/api/static-offline-docs",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process incoming requests"""
        path = request.url.path

        # Check if API docs should be hidden:
        # - Production: Always hidden (security by default)
        # - Development: Hidden only when ENABLE_API_DOCS=False
        env_lower = settings.ENV.lower() if settings.ENV else ""
        is_production = env_lower == "production"
        should_hide_docs = is_production or not settings.ENABLE_API_DOCS

        if should_hide_docs and self._is_blocked_path(path):
            logger.warning(
                f"Blocked access to API documentation endpoint: {path} "
                f"(ENV={settings.ENV}, ENABLE_API_DOCS={settings.ENABLE_API_DOCS})"
            )

            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": "not_found",
                    "message": "The requested resource does not exist",
                },
            )

        # Process request normally
        return await call_next(request)

    def _is_blocked_path(self, path: str) -> bool:
        """Check if the path should be blocked"""
        # Exact match for main endpoints
        if path in self.blocked_paths:
            return True

        # Prefix match for static offline docs
        return path.startswith("/api/static-offline-docs/")
