"""RBAC management API endpoints"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.models.role import Role
from src.schemas.rbac import (
    RoleAssignmentRequest,
    RoleAssignmentResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)
from src.services.rbac_service import RBACService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rbac")


def get_rbac_service(db: Annotated[AsyncSession, Depends(get_db_session)]) -> RBACService:
    """Dependency to get RBAC service instance"""
    return RBACService(db)


# Role Management Endpoints
@router.get(
    "/roles",
    response_model=list[RoleResponse],
    summary="Get all roles",
    description="List all available roles in the system",
)
async def list_roles(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> list[RoleResponse]:
    """List all roles (requires manage roles or manage settings permission)"""
    # Check if user has permission to manage roles OR settings
    has_permission = await rbac_service.check_permission(current_user.id, "manage", "roles")
    if not has_permission:
        has_permission = await rbac_service.check_permission(current_user.id, "manage", "settings")

    if not has_permission:
        from src.core.exceptions import ForbiddenException

        raise ForbiddenException(message="You do not have permission to view roles")

    roles = await rbac_service.get_all_roles()
    return [
        RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=role.permissions,
            created_at=role.created_at.isoformat(),
        )
        for role in roles
    ]


@router.get(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Get role by ID",
    description="Get details of a specific role",
)
async def get_role(
    role_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> RoleResponse:
    """Get role details (requires manage roles or manage settings permission)"""
    # Check if user has permission to manage roles OR settings
    has_permission = await rbac_service.check_permission(current_user.id, "manage", "roles")
    if not has_permission:
        has_permission = await rbac_service.check_permission(current_user.id, "manage", "settings")

    if not has_permission:
        from src.core.exceptions import ForbiddenException

        raise ForbiddenException(message="You do not have permission to view role details")

    role = await rbac_service.get_role_by_id(role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        created_at=role.created_at.isoformat(),
    )


@router.post(
    "/roles",
    response_model=RoleResponse,
    summary="Create new role",
    description="Create a new role with custom permissions",
    status_code=status.HTTP_201_CREATED,
)
async def create_role(
    role_data: RoleCreate,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> RoleResponse:
    """Create new role (requires system admin)"""
    await rbac_service.require_permission(current_user.id, "manage", "settings")

    # Check if role name already exists
    stmt = select(Role).where(Role.name == role_data.name)
    result = await rbac_service.db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{role_data.name}' already exists",
        )

    # Create new role
    new_role = Role(
        name=role_data.name,
        description=role_data.description,
        permissions=role_data.permissions,
    )

    rbac_service.db.add(new_role)
    await rbac_service.db.commit()
    await rbac_service.db.refresh(new_role)

    return RoleResponse(
        id=new_role.id,
        name=new_role.name,
        description=new_role.description,
        permissions=new_role.permissions,
        created_at=new_role.created_at.isoformat(),
    )


@router.put(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Update role",
    description="Update role permissions and description",
)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> RoleResponse:
    """Update role (requires system admin)"""
    await rbac_service.require_permission(current_user.id, "manage", "settings")

    role = await rbac_service.get_role_by_id(role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    # Update fields
    if role_data.description is not None:
        role.description = role_data.description
    if role_data.permissions is not None:
        role.permissions = role_data.permissions

    await rbac_service.db.commit()
    await rbac_service.db.refresh(role)

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        created_at=role.created_at.isoformat(),
    )


# Role Assignment Endpoints
@router.get(
    "/users/{auth_user_id}/roles",
    response_model=list[RoleAssignmentResponse],
    summary="Get user roles",
    description="Get all roles assigned to a specific user",
)
async def get_user_roles(
    auth_user_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> list[RoleAssignmentResponse]:
    """Get user's role assignments"""
    # Users can view their own roles, admins can view any user's roles
    if current_user.id != auth_user_id:
        await rbac_service.require_permission(current_user.id, "read", "users")

    assignments = await rbac_service.get_user_roles(auth_user_id)
    return [
        RoleAssignmentResponse(
            id=a["id"],
            auth_user_id=a["auth_user_id"],
            role_id=a["role_id"],
            role_name=a.get("role_name"),
            resource_type=a["resource_type"],
            resource_id=a["resource_id"],
            granted_by=a["granted_by"],
            expires_at=a["expires_at"],
            created_at=a["created_at"],
        )
        for a in assignments
    ]


@router.post(
    "/users/{auth_user_id}/roles",
    response_model=RoleAssignmentResponse,
    summary="Assign role to user",
    description="Assign a role to a user with specific resource scope",
    status_code=status.HTTP_201_CREATED,
)
async def assign_role_to_user(
    auth_user_id: int,
    assignment_data: RoleAssignmentRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> RoleAssignmentResponse:
    """Assign role to user (requires system admin or user management permission)"""
    await rbac_service.require_permission(current_user.id, "manage", "users")

    try:
        assignment = await rbac_service.assign_role(
            auth_user_id=auth_user_id,
            role_id=assignment_data.role_id,
            resource_type=assignment_data.resource_type,
            resource_id=assignment_data.resource_id,
            granted_by=current_user.id,
            expires_at=assignment_data.expires_at,
        )

        return RoleAssignmentResponse(
            id=assignment.id,
            auth_user_id=assignment.auth_user_id,
            role_id=assignment.role_id,
            resource_type=assignment.resource_type,
            resource_id=assignment.resource_id,
            granted_by=assignment.granted_by,
            expires_at=(assignment.expires_at.isoformat() if assignment.expires_at else None),
            created_at=assignment.created_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete(
    "/users/{auth_user_id}/roles/{role_id}",
    summary="Revoke role from user",
    description="Remove a role assignment from a user",
)
async def revoke_role_from_user(
    auth_user_id: int,
    role_id: int,
    resource_type: str,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
    resource_id: str | None = Query(default=None),
) -> dict[str, str]:
    """Revoke role from user (requires system admin or user management permission)"""
    await rbac_service.require_permission(current_user.id, "manage", "users")

    # Normalize resource_id: treat empty string as None
    normalized_resource_id = resource_id if resource_id else None

    success = await rbac_service.revoke_role(
        auth_user_id=auth_user_id,
        role_id=role_id,
        resource_type=resource_type,
        resource_id=normalized_resource_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found",
        )

    return {"message": "Role revoked successfully"}


# ============================================================================
# System Settings Endpoints
# ============================================================================


@router.get(
    "/settings/registration-enabled",
    response_model=dict,
    summary="Check if user registration is enabled",
    description="Returns whether new user registration is currently allowed (public endpoint)",
)
async def get_registration_enabled(
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> dict:
    """Check if registration is enabled (public endpoint, no auth required)"""
    try:
        value = await rbac_service.get_setting("registration_enabled", default_value="true")
        is_enabled = value.lower() == "true"
        return {"registration_enabled": is_enabled}
    except Exception as e:
        logger.error(f"Failed to get registration setting: {e}")
        # Default to enabled on error for availability
        return {"registration_enabled": True}


@router.put(
    "/settings/registration-enabled",
    response_model=dict,
    summary="Update registration enabled setting",
    description="Enable or disable new user registration (requires system admin)",
)
async def update_registration_enabled(
    setting_data: dict,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> dict:
    """Update registration enabled setting (requires manage settings permission)"""
    # Check if user has permission to manage settings
    await rbac_service.require_permission(current_user.id, "manage", "settings")

    enabled = setting_data.get("registration_enabled", True)
    value_str = str(enabled).lower()

    try:
        await rbac_service.update_setting(
            setting_key="registration_enabled",
            setting_value=value_str,
            updated_by=current_user.id,
            description="Controls whether new user registration is allowed",
        )
        return {
            "message": "Registration setting updated successfully",
            "registration_enabled": enabled,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to update registration setting: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update registration setting: {str(e)}",
        ) from e


# ============================================================================
# JIRA Settings Endpoints
# ============================================================================


@router.get(
    "/settings/jira",
    response_model=dict,
    summary="Get JIRA ticket link settings",
    description=(
        "Base URL and project keys used to turn the JIRA ticket keys of commit "
        "messages and release notes into links. Empty when JIRA is not configured."
    ),
)
async def get_jira_settings(
    _current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> dict:
    """JIRA link configuration (JIRA_BASE_URL / JIRA_PROJECT_KEYS of the backend)."""
    base_url = (settings.JIRA_BASE_URL or "").rstrip("/")
    project_keys = [
        key.strip().upper() for key in (settings.JIRA_PROJECT_KEYS or "").split(",") if key.strip()
    ]
    return {"base_url": base_url, "project_keys": project_keys}


# ============================================================================
# Banner Settings Endpoints
# ============================================================================


# ----------------------------------------------------------------------------
# Reviews page banners
#
# The banners are one JSON array under a single setting, because they are a
# collection: several can be scheduled at once and several can be within their
# window together. They used to be four scalar settings describing exactly one
# banner (enabled / content / start_date / end_date); those keys are still read
# when the array has never been written, so an installation that has not been
# re-saved keeps showing the banner it already had.
# ----------------------------------------------------------------------------

BANNER_SETTING_KEY = "banner_items"
LEGACY_BANNER_KEYS = (
    "banner_enabled",
    "banner_content",
    "banner_start_date",
    "banner_end_date",
)
BANNER_LEVELS = ("info", "warning", "success")
MAX_BANNERS = 20
MAX_BANNER_CONTENT_LENGTH = 500
MAX_BANNER_LINK_LENGTH = 500


def _stable_id(*parts: str) -> str:
    """A short id that is the same every time it is derived from the same parts."""
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return f"banner-{digest[:12]}"


def _validated_date(value: object) -> str:
    """Keep an ISO 8601 window bound, or empty for "no bound"."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        # Element Plus writes a trailing Z, which fromisoformat takes from 3.11.
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"'{text}' is not a valid date") from exc
    return text


def _validated_link(value: object) -> str:
    """Keep an http(s) or site-relative link.

    The value ends up in an anchor's href, so a scheme like ``javascript:`` would
    be a scripting vector for whoever can edit settings.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) > MAX_BANNER_LINK_LENGTH:
        raise ValueError(f"a banner link is longer than {MAX_BANNER_LINK_LENGTH} characters")
    if text.startswith(("/", "https://", "http://")):
        return text
    raise ValueError("a banner link must be http(s) or start with /")


def _coerced_flag(value: object) -> bool:
    """Read a boolean that may arrive as the string the settings table stores."""
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def _normalize_banner(raw: object) -> dict:
    """Validate one banner and bound every field of it."""
    if not isinstance(raw, dict):
        raise ValueError("each banner must be an object")

    content = str(raw.get("content") or "").strip()
    if not content:
        raise ValueError("a banner needs content")
    if len(content) > MAX_BANNER_CONTENT_LENGTH:
        raise ValueError(f"banner content is longer than {MAX_BANNER_CONTENT_LENGTH} characters")

    level = str(raw.get("level") or "info").strip().lower()
    if level not in BANNER_LEVELS:
        level = "info"

    start_date = _validated_date(raw.get("start_date"))
    end_date = _validated_date(raw.get("end_date"))

    try:
        priority = int(raw.get("priority") or 0)
    except (TypeError, ValueError):
        priority = 0

    # A banner saved without an id gets one derived from what it says, so that
    # dismissing it survives until its wording changes.
    banner_id = str(raw.get("id") or "").strip()
    if not banner_id:
        banner_id = _stable_id(content, start_date, end_date)

    return {
        "id": banner_id,
        "enabled": _coerced_flag(raw.get("enabled", False)),
        "content": content,
        "start_date": start_date,
        "end_date": end_date,
        "level": level,
        "link_url": _validated_link(raw.get("link_url")),
        "link_label": str(raw.get("link_label") or "").strip()[:MAX_BANNER_LINK_LENGTH],
        "priority": priority,
    }


def _parse_stored_banners(value: str) -> list[dict] | None:
    """Read the stored array, or None when it has never been written.

    Anything unreadable is reported and treated as absent: the banners are display
    data, and a hand-edited row should not take the settings page down.
    """
    if not value or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("Banner settings are not valid JSON; falling back to the legacy keys")
        return None
    if not isinstance(parsed, list):
        logger.warning("Banner settings are not a list; falling back to the legacy keys")
        return None

    banners: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        try:
            banners.append(_normalize_banner(item))
        except ValueError as exc:
            logger.warning("Skipping an unusable stored banner: %s", exc)
    return banners


async def _banners_from_legacy_settings(rbac_service: RBACService) -> list[dict]:
    """Fold the four scalar settings into the list they preceded."""
    enabled = await rbac_service.get_setting(LEGACY_BANNER_KEYS[0], default_value="false")
    content = await rbac_service.get_setting(LEGACY_BANNER_KEYS[1], default_value="")
    start_date = await rbac_service.get_setting(LEGACY_BANNER_KEYS[2], default_value="")
    end_date = await rbac_service.get_setting(LEGACY_BANNER_KEYS[3], default_value="")
    if not content.strip():
        return []
    return [
        _normalize_banner(
            {
                "id": _stable_id(content, start_date, end_date),
                "enabled": enabled,
                "content": content,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
    ]


@router.get(
    "/settings/banner",
    response_model=dict,
    summary="Get reviews page banner config",
    description="Returns the announcement banners of the reviews page, each with its own window",
)
async def get_banner_settings(
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> dict:
    """Get reviews page banner configuration"""
    try:
        stored = await rbac_service.get_setting(BANNER_SETTING_KEY, default_value="")
        banners = _parse_stored_banners(stored)
        if banners is None:
            banners = await _banners_from_legacy_settings(rbac_service)
        return {"banners": banners}
    except Exception as e:
        logger.error(f"Failed to get banner settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get banner settings",
        ) from e


@router.put(
    "/settings/banner",
    response_model=dict,
    summary="Update reviews page banner config",
    description="Replace the announcement banners of the reviews page. Requires manage settings permission.",
)
async def update_banner_settings(
    setting_data: dict,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> dict:
    """Replace the reviews page banners"""
    await rbac_service.require_permission(current_user.id, "manage", "settings")

    try:
        raw_banners = setting_data.get("banners")
        if raw_banners is None:
            # A page that predates the list shape sends one banner's fields. Only a
            # complete one is accepted, so a partial write cannot wipe the list.
            if "content" not in setting_data:
                raise ValueError("banners is required")
            raw_banners = [setting_data]

        if not isinstance(raw_banners, list):
            raise ValueError("banners must be a list")
        if len(raw_banners) > MAX_BANNERS:
            raise ValueError(f"at most {MAX_BANNERS} banners are supported")

        banners = [_normalize_banner(item) for item in raw_banners]

        # The settings store only updates a row it already has, and reading one is
        # how it comes into existence (`RBACService.get_setting` creates it on a
        # miss). Without this, the first save on a fresh installation would fail.
        await rbac_service.get_setting(BANNER_SETTING_KEY, default_value="")

        await rbac_service.update_setting(
            setting_key=BANNER_SETTING_KEY,
            setting_value=json.dumps(banners, ensure_ascii=False),
            updated_by=current_user.id,
            description="Announcement banners of the reviews page, as a JSON array",
        )
        return {"message": "Banner settings updated successfully", "banners": banners}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to update banner settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update banner settings: {str(e)}",
        ) from e


# ============================================================================
# LLM Proxy Settings Endpoints
# ============================================================================


@router.get(
    "/settings/llm",
    response_model=dict,
    summary="Get LLM proxy settings",
    description="Returns LLM proxy configuration (without API key). Requires manage settings permission.",
)
async def get_llm_settings(
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> dict:
    """Get LLM proxy settings (api_key excluded from response)"""
    await rbac_service.require_permission(current_user.id, "manage", "settings")

    try:
        enabled = await rbac_service.get_setting("llm_enabled", default_value="false")
        model = await rbac_service.get_setting("llm_model", default_value="")
        base_url = await rbac_service.get_setting("llm_base_url", default_value="")
        api_key = await rbac_service.get_setting("llm_api_key", default_value="")
        return {
            "enabled": enabled.lower() == "true",
            "model": model,
            "base_url": base_url,
            "has_api_key": bool(api_key),
        }
    except Exception as e:
        logger.error(f"Failed to get LLM settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get LLM settings: {str(e)}",
        ) from e


@router.put(
    "/settings/llm",
    response_model=dict,
    summary="Update LLM proxy settings",
    description="Update LLM proxy configuration (model, base_url, api_key). Requires manage settings permission.",
)
async def update_llm_settings(
    setting_data: dict,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> dict:
    """Update LLM proxy settings"""
    await rbac_service.require_permission(current_user.id, "manage", "settings")

    try:
        # Update each setting individually
        if "enabled" in setting_data:
            value_str = str(setting_data["enabled"]).lower()
            await rbac_service.update_setting(
                setting_key="llm_enabled",
                setting_value=value_str,
                updated_by=current_user.id,
                description="Enable or disable LLM proxy for PageAgent",
            )

        if "model" in setting_data:
            await rbac_service.update_setting(
                setting_key="llm_model",
                setting_value=setting_data["model"],
                updated_by=current_user.id,
                description="Default LLM model for PageAgent",
            )

        if "base_url" in setting_data:
            await rbac_service.update_setting(
                setting_key="llm_base_url",
                setting_value=setting_data["base_url"],
                updated_by=current_user.id,
                description="Base URL for LLM provider API",
            )

        if "api_key" in setting_data and setting_data["api_key"]:
            await rbac_service.update_setting(
                setting_key="llm_api_key",
                setting_value=setting_data["api_key"],
                updated_by=current_user.id,
                description="API key for LLM provider (server-side only)",
            )

        return {"message": "LLM settings updated successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to update LLM settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update LLM settings: {str(e)}",
        ) from e
