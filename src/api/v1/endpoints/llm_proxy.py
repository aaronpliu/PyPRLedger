"""LLM Proxy API endpoints - secure backend proxy for PageAgent"""

from __future__ import annotations

import json
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response, StreamingResponse

from src.core.config import settings
from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.models.system_setting import SystemSetting
from src.utils.log import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/llm")


async def _get_llm_config(db: AsyncSession) -> dict:
    """Read LLM proxy configuration from system_settings, falling back to env vars.

    Args:
        db: Database session

    Returns:
        Dict with enabled, model, base_url, api_key keys
    """
    config = {
        "enabled": settings.LLM_PROXY_ENABLED,
        "model": settings.LLM_DEFAULT_MODEL,
        "base_url": settings.LLM_DEFAULT_BASE_URL,
        "api_key": settings.LLM_DEFAULT_API_KEY,
    }

    # Override with system_settings from DB if they exist
    setting_keys = ["llm_enabled", "llm_model", "llm_base_url", "llm_api_key"]
    stmt = select(SystemSetting).where(
        SystemSetting.setting_key.in_(setting_keys),
        SystemSetting.is_active.is_(True),
    )
    result = await db.execute(stmt)
    for setting in result.scalars().all():
        key = setting.setting_key
        value = setting.setting_value
        if key == "llm_enabled":
            config["enabled"] = value.lower() == "true"
        elif key == "llm_model" and value:
            config["model"] = value
        elif key == "llm_base_url" and value:
            config["base_url"] = value
        elif key == "llm_api_key" and value:
            config["api_key"] = value

    return config


@router.get(
    "/config",
    response_model=dict,
    summary="Get LLM proxy configuration",
    description="Returns LLM configuration for the frontend (without the API key). Requires authentication.",
)
async def get_llm_config(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> dict:
    """Return LLM config for frontend initialization (api_key excluded)."""
    config = await _get_llm_config(db)
    return {
        "enabled": config["enabled"],
        "model": config["model"],
        "base_url": config["base_url"],
    }


@router.post(
    "/proxy/{path:path}",
    summary="Proxy LLM API requests",
    description="Proxies requests to the configured LLM provider with server-side API key.",
)
async def llm_proxy(
    path: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
):
    """Proxy any LLM API request path (e.g., chat/completions) to the configured provider."""
    config = await _get_llm_config(db)

    if not config["enabled"] or not config["base_url"] or not config["api_key"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM proxy is not configured or disabled",
        )

    # Read the request body
    body = await request.body()

    # Build the target URL
    target_url = f"{config['base_url'].rstrip('/')}/{path.lstrip('/')}"

    # Forward headers (excluding host and content-length which httpx handles)
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": request.headers.get("Content-Type", "application/json"),
    }

    # Check if the request expects streaming
    is_stream = False
    if body:
        try:
            payload = json.loads(body)
            is_stream = payload.get("stream", False)
        except (json.JSONDecodeError, ValueError):
            pass

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if is_stream:
                # Proxy as SSE streaming response
                req = client.build_request("POST", target_url, headers=headers, content=body)
                response = await client.send(req, stream=True)

                async def _stream_response():
                    async for chunk in response.aiter_bytes():
                        yield chunk

                return StreamingResponse(
                    _stream_response(),
                    media_type=response.headers.get("content-type", "text/event-stream"),
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )
            else:
                # Proxy as regular JSON response
                response = await client.post(target_url, headers=headers, content=body)
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    media_type=response.headers.get("content-type", "application/json"),
                )
    except httpx.RequestError as e:
        logger.error(
            "LLM proxy request failed",
            extra={"path": path, "target_url": target_url, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM proxy request failed: {str(e)}",
        )
