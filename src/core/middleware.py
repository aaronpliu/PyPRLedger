import logging
import time
import uuid
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.background import BackgroundTask

from src.core.config import settings
from src.core.exceptions import RateLimitException
from src.utils.redis import get_redis_client


logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成唯一请求ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # 记录请求开始时间
        start_time = time.time()

        # 记录请求信息
        client_ip = request.client.host if request.client else "unknown"
        request_headers = dict(request.headers)

        # 过滤敏感头部信息
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

        # 处理请求
        try:
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 添加请求ID到响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}"

            # 记录响应信息
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
            # 计算处理时间
            process_time = time.time() - start_time

            # 记录异常
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
    """请求限流中间件"""

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
        # 如果未启用限流，直接处理请求
        if not self.enabled:
            return await call_next(request)

        # 获取客户端标识符 (使用IP地址)
        client_ip = request.client.host if request.client else "unknown"

        # 获取Redis客户端 (如果未提供，则创建新的连接)
        redis = self.redis_client
        if redis is None:
            redis = get_redis_client()

        try:
            # 构建限流key
            rate_limit_key = f"rate_limit:{client_ip}"

            # 获取当前计数
            current_count = await redis.incr(rate_limit_key)

            # 如果是第一次请求，设置过期时间
            if current_count == 1:
                await redis.expire(rate_limit_key, self.period_seconds)

            # 检查是否超过限制
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
                    message=f"Rate limit exceeded. Maximum {self.max_requests} requests per {self.period_seconds} seconds",
                    detail={
                        "limit": self.max_requests,
                        "period": self.period_seconds,
                        "retry_after": await redis.ttl(rate_limit_key),
                    },
                )

            # 添加限流信息到请求状态
            request.state.rate_limit = {
                "current": current_count,
                "limit": self.max_requests,
                "remaining": self.max_requests - current_count,
                "reset": await redis.ttl(rate_limit_key),
            }

            # 处理请求
            response = await call_next(request)

            # 添加限流信息到响应头
            rate_limit = request.state.rate_limit
            response.headers["X-RateLimit-Limit"] = str(rate_limit["limit"])
            response.headers["X-RateLimit-Remaining"] = str(rate_limit["remaining"])
            response.headers["X-RateLimit-Reset"] = str(rate_limit["reset"])

            return response

        except RateLimitException:
            raise
        except Exception as exc:
            logger.error(f"Rate limiting error: {str(exc)}", exc_info=True)
            # 发生错误时不阻止请求
            return await call_next(request)


class CacheControlMiddleware(BaseHTTPMiddleware):
    """缓存控制中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 处理请求
        response = await call_next(request)

        # 根据请求方法和路径设置缓存策略
        if request.method == "GET":
            # 对GET请求设置适当的缓存策略
            if request.url.path.startswith("/api/v1/reviews"):
                # 审查列表可以短时间缓存
                response.headers["Cache-Control"] = "private, max-age=60"
            elif request.url.path.startswith("/api/v1/projects"):
                # 项目信息可以较长时间缓存
                response.headers["Cache-Control"] = "private, max-age=300"
            else:
                # 其他GET请求默认不缓存
                response.headers["Cache-Control"] = "no-store"
        else:
            # 非GET请求禁止缓存
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全头中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 处理请求
        response = await call_next(request)

        # 添加安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """请求计时中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 记录开始时间
        start_time = time.time()

        # 处理请求
        response = await call_next(request)

        # 计算处理时间
        process_time = time.time() - start_time

        # 添加处理时间到响应头
        response.headers["X-Response-Time"] = f"{process_time:.4f}s"

        return response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """请求ID中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 尝试从请求头获取请求ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # 添加到请求状态
        request.state.request_id = request_id

        # 处理请求
        response = await call_next(request)

        # 添加请求ID到响应头
        response.headers["X-Request-ID"] = request_id

        return response
