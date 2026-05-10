# Phase 5.1: Personal Access Token (PAT) Management

## Overview

Implement a secure Personal Access Token system allowing authenticated users to generate API tokens for programmatic access, with full lifecycle management in the Profile page. This feature enables developers and integrations to authenticate with the API without using username/password credentials.

---

## Requirements

### Functional Requirements

1. **Token Generation**
   - Users can create personal access tokens from their Profile page
   - Each token has a user-defined name for identification
   - Tokens are shown only once at creation time
   - Maximum 10 active tokens per user

2. **Token Configuration**
   - Optional expiration date (7 days, 30 days, 90 days, 365 days, or never)
   - If no expiration specified, default to 90 days
   - Token format: `pat_<base64_string>` (e.g., `pat_aB3dEf7hIjKlMnOpQrStUvWxYz0123456789`)

3. **Token Management**
   - View list of active tokens
   - View expired tokens (retained for 3 months after expiration)
   - Revoke any token at any time
   - Track last usage timestamp

4. **Security**
   - Tokens are hashed before storage (SHA-256)
   - Only prefix (first 8 chars) stored in plain text for identification
   - Full token never recoverable after creation
   - Rate limiting on token creation (5 per hour per user)

5. **Authentication**
   - PATs can be used in Authorization header: `Authorization: Bearer pat_xxx`
   - Same permissions as the user who created the token
   - Automatic tracking of last used timestamp

---

## Implementation Plan

### Phase 1: Database Schema & Migration

**File**: `alembic/versions/021_create_personal_access_tokens.py`

#### Table Structure: `personal_access_token`

```sql
CREATE TABLE personal_access_token (
    id INT AUTO_INCREMENT PRIMARY KEY,
    auth_user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    prefix VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NULL,
    last_used_at DATETIME NULL,
    is_active BOOLEAN DEFAULT TRUE,
    ip_address VARCHAR(45) NULL,
    user_agent TEXT NULL,
    
    INDEX idx_auth_user (auth_user_id),
    INDEX idx_prefix (prefix),
    INDEX idx_expires_at (expires_at),
    INDEX idx_is_active (is_active),
    
    FOREIGN KEY (auth_user_id) REFERENCES auth_user(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

#### Migration Actions

1. Create table with above schema
2. Add indexes for performance optimization
3. Set up cascade delete when user is removed
4. Add comment explaining purpose of each column

---

### Phase 2: Backend Models & Schemas

#### 2.1 Model (`src/models/personal_access_token.py`)

```python
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.auth_user import AuthUser


class PersonalAccessToken(Base):
    """Personal Access Token model for API authentication"""

    __tablename__ = "personal_access_token"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Foreign key to auth_user
    auth_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("auth_user.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Token metadata
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Creation context
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    auth_user: Mapped["AuthUser"] = relationship("AuthUser", back_populates="personal_access_tokens")

    # Table arguments
    __table_args__ = (
        Index("idx_auth_user_created", "auth_user_id", "created_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary (excludes sensitive data)"""
        return {
            "id": self.id,
            "name": self.name,
            "prefix": self.prefix,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "is_active": self.is_active,
        }
```

#### 2.2 Update AuthUser Model (`src/models/auth_user.py`)

Add relationship:
```python
# In AuthUser class
personal_access_tokens: Mapped[list["PersonalAccessToken"]] = relationship(
    "PersonalAccessToken", 
    back_populates="auth_user",
    lazy="selectin"
)
```

#### 2.3 Schemas (`src/schemas/personal_access_token.py`)

```python
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class PATCreateRequest(BaseModel):
    """Request schema for creating a new personal access token"""
    
    name: str = Field(..., min_length=1, max_length=100, description="Token name for identification")
    expires_in_days: int | None = Field(
        None, 
        ge=1, 
        le=365, 
        description="Days until token expires (1-365). None means use default (90 days)"
    )


class PATResponse(BaseModel):
    """Response schema for token metadata (no token value)"""
    
    id: int
    name: str
    prefix: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    is_active: bool
    
    class Config:
        from_attributes = True


class PATCreationResponse(PATResponse):
    """Special response for token creation (includes token once)"""
    
    token: str = Field(..., description="Full token value (shown only once)")


class PATListResponse(BaseModel):
    """Paginated list response"""
    
    total: int
    items: list[PATResponse]
```

---

### Phase 3: Service Layer

**File**: `src/services/pat_service.py`

```python
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import AppException, ErrorCode
from src.models.personal_access_token import PersonalAccessToken
from src.utils.redis import get_redis_client

logger = logging.getLogger(__name__)

# Constants
TOKEN_PREFIX = "pat_"
TOKEN_LENGTH = 64  # bytes
MAX_TOKENS_PER_USER = 10
DEFAULT_EXPIRY_DAYS = 90
RATE_LIMIT_WINDOW = 3600  # 1 hour
RATE_LIMIT_MAX = 5  # 5 creations per hour


class PATService:
    """Service for managing Personal Access Tokens"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis_client = get_redis_client()

    async def create_token(
        self,
        auth_user_id: int,
        name: str,
        expires_in_days: int | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, PersonalAccessToken]:
        """
        Create a new personal access token
        
        Returns:
            Tuple of (full_token_string, token_record)
        """
        # Check rate limit
        await self._check_rate_limit(auth_user_id)
        
        # Check token count limit
        await self._check_token_limit(auth_user_id)
        
        # Generate token
        raw_token = TOKEN_PREFIX + secrets.token_urlsafe(TOKEN_LENGTH)
        token_hash = self._hash_token(raw_token)
        prefix = raw_token[:12]  # Store first 12 chars for identification
        
        # Calculate expiry
        if expires_in_days is None:
            expires_in_days = DEFAULT_EXPIRY_DAYS
        
        expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
        
        # Create record
        token_record = PersonalAccessToken(
            auth_user_id=auth_user_id,
            name=name,
            token_hash=token_hash,
            prefix=prefix,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        self.db.add(token_record)
        await self.db.commit()
        await self.db.refresh(token_record)
        
        logger.info(
            "PAT created",
            extra={
                "token_id": token_record.id,
                "user_id": auth_user_id,
                "token_name": name,
            }
        )
        
        return raw_token, token_record

    async def validate_token(self, token_string: str) -> PersonalAccessToken | None:
        """
        Validate a personal access token
        
        Returns:
            PersonalAccessToken record if valid, None otherwise
        """
        if not token_string.startswith(TOKEN_PREFIX):
            return None
        
        # Extract prefix
        prefix = token_string[:12]
        
        # Find by prefix
        result = await self.db.execute(
            select(PersonalAccessToken)
            .where(PersonalAccessToken.prefix == prefix)
            .where(PersonalAccessToken.is_active == True)
        )
        token_record = result.scalar_one_or_none()
        
        if not token_record:
            return None
        
        # Verify hash
        token_hash = self._hash_token(token_string)
        if not self._constant_time_compare(token_record.token_hash, token_hash):
            return None
        
        # Check expiration
        if token_record.expires_at and token_record.expires_at < datetime.now(UTC):
            # Mark as inactive
            token_record.is_active = False
            await self.db.commit()
            logger.warning("PAT expired", extra={"token_id": token_record.id})
            return None
        
        # Update last used
        token_record.last_used_at = datetime.now(UTC)
        await self.db.commit()
        
        return token_record

    async def list_tokens(
        self,
        auth_user_id: int,
        include_expired: bool = False,
    ) -> list[PersonalAccessToken]:
        """List tokens for a user"""
        query = select(PersonalAccessToken).where(
            PersonalAccessToken.auth_user_id == auth_user_id
        )
        
        if not include_expired:
            query = query.where(PersonalAccessToken.is_active == True)
        else:
            # Include expired tokens from last 3 months
            three_months_ago = datetime.now(UTC) - timedelta(days=90)
            query = query.where(
                (PersonalAccessToken.is_active == True) |
                (PersonalAccessToken.expires_at >= three_months_ago)
            )
        
        query = query.order_by(PersonalAccessToken.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def revoke_token(self, auth_user_id: int, token_id: int) -> bool:
        """Revoke a token (verify ownership)"""
        result = await self.db.execute(
            select(PersonalAccessToken)
            .where(PersonalAccessToken.id == token_id)
            .where(PersonalAccessToken.auth_user_id == auth_user_id)
        )
        token_record = result.scalar_one_or_none()
        
        if not token_record:
            return False
        
        token_record.is_active = False
        await self.db.commit()
        
        logger.info(
            "PAT revoked",
            extra={
                "token_id": token_id,
                "user_id": auth_user_id,
            }
        )
        
        return True

    async def cleanup_expired_tokens(self) -> int:
        """
        Delete tokens that expired more than 3 months ago
        
        Returns:
            Number of deleted tokens
        """
        three_months_ago = datetime.now(UTC) - timedelta(days=90)
        
        result = await self.db.execute(
            select(PersonalAccessToken)
            .where(PersonalAccessToken.expires_at < three_months_ago)
            .where(PersonalAccessToken.is_active == False)
        )
        expired_tokens = result.scalars().all()
        
        count = len(expired_tokens)
        for token in expired_tokens:
            await self.db.delete(token)
        
        await self.db.commit()
        
        if count > 0:
            logger.info("Cleaned up expired PATs", extra={"count": count})
        
        return count

    async def get_token_count(self, auth_user_id: int) -> int:
        """Count active tokens for a user"""
        result = await self.db.execute(
            select(PersonalAccessToken)
            .where(PersonalAccessToken.auth_user_id == auth_user_id)
            .where(PersonalAccessToken.is_active == True)
        )
        return len(result.scalars().all())

    # Private methods
    
    def _hash_token(self, token: str) -> str:
        """Hash token using SHA-256"""
        return hashlib.sha256(token.encode()).hexdigest()

    def _constant_time_compare(self, a: str, b: str) -> bool:
        """Constant-time comparison to prevent timing attacks"""
        return hmac.compare_digest(a.encode(), b.encode())

    async def _check_rate_limit(self, auth_user_id: int):
        """Check if user has exceeded token creation rate limit"""
        key = f"pat_rate_limit:{auth_user_id}"
        current = await self.redis_client.get(key)
        
        if current and int(current) >= RATE_LIMIT_MAX:
            raise AppException(
                error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
                message=f"Token creation rate limit exceeded. Max {RATE_LIMIT_MAX} tokens per hour.",
            )
        
        # Increment counter
        pipe = self.redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, RATE_LIMIT_WINDOW)
        await pipe.execute()

    async def _check_token_limit(self, auth_user_id: int):
        """Check if user has reached maximum token limit"""
        count = await self.get_token_count(auth_user_id)
        
        if count >= MAX_TOKENS_PER_USER:
            raise AppException(
                error_code=ErrorCode.VALIDATION_ERROR,
                message=f"Maximum {MAX_TOKENS_PER_USER} active tokens allowed per user.",
            )
```

---

### Phase 4: API Endpoints

**File**: `src/api/v1/endpoints/personal_access_tokens.py`

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies import get_current_user_with_token, get_db_session
from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.personal_access_token import (
    PATCreateRequest,
    PATCreationResponse,
    PATListResponse,
    PATResponse,
)
from src.services.pat_service import PATService

router = APIRouter(prefix="/personal-access-tokens", tags=["Personal Access Tokens"])


def get_pat_service(db: Annotated[AsyncSession, Depends(get_db_session)]) -> PATService:
    """Dependency to get PAT service"""
    return PATService(db)


@router.get(
    "/",
    response_model=PATListResponse,
    summary="List personal access tokens",
    description="List all personal access tokens for the current user",
)
async def list_tokens(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    pat_service: Annotated[PATService, Depends(get_pat_service)],
    include_expired: bool = False,
) -> PATListResponse:
    """List all personal access tokens for current user"""
    tokens = await pat_service.list_tokens(
        auth_user_id=current_user.id,
        include_expired=include_expired,
    )
    
    return PATListResponse(
        total=len(tokens),
        items=[PATResponse.model_validate(t) for t in tokens],
    )


@router.post(
    "/",
    response_model=PATCreationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create personal access token",
    description="Generate a new personal access token (token shown only once)",
)
async def create_token(
    request_data: PATCreateRequest,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    pat_service: Annotated[PATService, Depends(get_pat_service)],
) -> PATCreationResponse:
    """Generate a new personal access token"""
    # Get request context
    forwarded_for = request.headers.get("X-Forwarded-For")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else None
    if not ip_address and request.client:
        ip_address = request.client.host
    user_agent = request.headers.get("User-Agent")
    
    # Create token
    full_token, token_record = await pat_service.create_token(
        auth_user_id=current_user.id,
        name=request_data.name,
        expires_in_days=request_data.expires_in_days,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    return PATCreationResponse(
        id=token_record.id,
        name=token_record.name,
        prefix=token_record.prefix,
        created_at=token_record.created_at,
        expires_at=token_record.expires_at,
        last_used_at=token_record.last_used_at,
        is_active=token_record.is_active,
        token=full_token,
    )


@router.get(
    "/{token_id}",
    response_model=PATResponse,
    summary="Get token details",
    description="Get details of a specific personal access token",
)
async def get_token(
    token_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PATResponse:
    """Get details of a specific token"""
    from sqlalchemy import select
    from src.models.personal_access_token import PersonalAccessToken
    
    result = await db.execute(
        select(PersonalAccessToken)
        .where(PersonalAccessToken.id == token_id)
        .where(PersonalAccessToken.auth_user_id == current_user.id)
    )
    token_record = result.scalar_one_or_none()
    
    if not token_record:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
    
    return PATResponse.model_validate(token_record)


@router.delete(
    "/{token_id}",
    summary="Revoke personal access token",
    description="Revoke a personal access token immediately",
)
async def revoke_token(
    token_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    pat_service: Annotated[PATService, Depends(get_pat_service)],
) -> dict[str, str]:
    """Revoke a personal access token"""
    success = await pat_service.revoke_token(
        auth_user_id=current_user.id,
        token_id=token_id,
    )
    
    if not success:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found or already revoked",
        )
    
    return {"message": "Token revoked successfully"}
```

**Register Router** in `src/api/v1/router.py`:
```python
from src.api.v1.endpoints import personal_access_tokens

api_router.include_router(
    personal_access_tokens.router,
    prefix="/v1",
)
```

---

### Phase 5: Authentication Middleware Update

**File**: `src/core/permissions.py`

Update `get_current_user_with_token()` to support PAT authentication:

```python
async def get_current_user_with_token(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthUser:
    """Dependency to get current authenticated user from JWT token or PAT"""
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]
    
    # Check if token is PAT or JWT
    if token.startswith("pat_"):
        # Validate as Personal Access Token
        from src.services.pat_service import PATService
        pat_service = PATService(db)
        token_record = await pat_service.validate_token(token)
        
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired personal access token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get auth user
        from sqlalchemy import select
        from src.models.auth_user import AuthUser
        result = await db.execute(
            select(AuthUser).where(AuthUser.id == token_record.auth_user_id)
        )
        auth_user = result.scalar_one_or_none()
        
        if not auth_user or not auth_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return auth_user
    else:
        # Validate as JWT (existing logic)
        auth_service = AuthService(db)
        forwarded_for = request.headers.get("X-Forwarded-For")
        ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else None
        if not ip_address and request.client:
            ip_address = request.client.host
        user_agent = request.headers.get("User-Agent")

        try:
            auth_user = await auth_service.get_current_user(token)
            await auth_service.sync_session_client_context(
                token,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return auth_user
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
```

---

### Phase 6: Frontend Implementation

#### 6.1 API Client (`frontend/src/api/pat.ts`)

```typescript
import request from '@/utils/request'
import type { PATResponse, PATCreationResponse, PATListResponse } from '@/types'

export interface PATCreateRequest {
  name: string
  expires_in_days?: number
}

export const patApi = {
  // List tokens
  listTokens(includeExpired = false): Promise<PATListResponse> {
    return request.get('/personal-access-tokens/', {
      params: { include_expired: includeExpired },
    })
  },

  // Create token
  createToken(data: PATCreateRequest): Promise<PATCreationResponse> {
    return request.post('/personal-access-tokens/', data)
  },

  // Revoke token
  revokeToken(tokenId: number): Promise<{ message: string }> {
    return request.delete(`/personal-access-tokens/${tokenId}`)
  },

  // Get token details
  getTokenDetails(tokenId: number): Promise<PATResponse> {
    return request.get(`/personal-access-tokens/${tokenId}`)
  },
}
```

#### 6.2 Type Definitions (`frontend/src/types/index.ts`)

Add to existing types:
```typescript
// Personal Access Token types
export interface PATResponse {
  id: number
  name: string
  prefix: string
  created_at: string
  expires_at: string | null
  last_used_at: string | null
  is_active: boolean
}

export interface PATCreationResponse extends PATResponse {
  token: string
}

export interface PATListResponse {
  total: number
  items: PATResponse[]
}
```

#### 6.3 Profile Tab Component (`frontend/src/components/profile/PATManagement.vue`)

```vue
<template>
  <div class="pat-management">
    <!-- Header -->
    <div class="pat-header">
      <div>
        <h3>{{ t('profile.manage_tokens') }}</h3>
        <p class="subtitle">{{ t('profile.tokens_description') }}</p>
      </div>
      <el-button 
        type="primary" 
        @click="showCreateDialog = true"
        :disabled="activeTokenCount >= 10"
      >
        <el-icon><Plus /></el-icon>
        {{ t('profile.create_token') }}
      </el-button>
    </div>

    <!-- Warning Banner -->
    <el-alert
      v-if="activeTokenCount >= 8"
      :title="t('profile.token_limit_warning')"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    />

    <!-- Filter Tabs -->
    <el-tabs v-model="activeFilter" @tab-change="loadTokens">
      <el-tab-pane :label="t('profile.active_tokens')" name="active" />
      <el-tab-pane :label="t('profile.expired_tokens')" name="expired" />
    </el-tabs>

    <!-- Token List -->
    <el-table 
      :data="tokens" 
      v-loading="loading"
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column prop="name" :label="t('profile.token_name')" min-width="150" />
      <el-table-column prop="prefix" label="Token" width="120">
        <template #default="{ row }">
          <code>{{ row.prefix }}••••</code>
        </template>
      </el-table-column>
      <el-table-column :label="t('profile.created_at')" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column :label="t('profile.expires_at')" width="180">
        <template #default="{ row }">
          {{ row.expires_at ? formatDate(row.expires_at) : t('profile.never_expires') }}
        </template>
      </el-table-column>
      <el-table-column :label="t('profile.last_used')" width="180">
        <template #default="{ row }">
          {{ row.last_used_at ? formatDate(row.last_used_at) : t('profile.never_used') }}
        </template>
      </el-table-column>
      <el-table-column :label="t('common.status')" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? t('common.active') : t('common.expired') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('common.actions')" width="120" fixed="right">
        <template #default="{ row }">
          <el-popconfirm
            :title="t('profile.confirm_revoke')"
            @confirm="handleRevoke(row.id)"
          >
            <template #reference>
              <el-button 
                type="danger" 
                size="small" 
                :disabled="!row.is_active"
              >
                {{ t('profile.revoke_token') }}
              </el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- Empty State -->
    <el-empty 
      v-if="!loading && tokens.length === 0"
      :description="t('profile.no_tokens')"
    />

    <!-- Create Token Dialog -->
    <el-dialog
      v-model="showCreateDialog"
      :title="t('profile.create_token')"
      width="500px"
      @close="resetForm"
    >
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="120px">
        <el-form-item :label="t('profile.token_name')" prop="name">
          <el-input 
            v-model="createForm.name" 
            :placeholder="t('profile.token_name_placeholder')"
            maxlength="100"
            show-word-limit
          />
        </el-form-item>
        
        <el-form-item :label="t('profile.expiration')">
          <el-select v-model="createForm.expires_in_days" style="width: 100%">
            <el-option :label="t('profile.expiry_7_days')" :value="7" />
            <el-option :label="t('profile.expiry_30_days')" :value="30" />
            <el-option :label="t('profile.expiry_90_days')" :value="90" />
            <el-option :label="t('profile.expiry_365_days')" :value="365" />
            <el-option :label="t('profile.never_expires')" :value="null" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleCreateToken" :loading="creating">
          {{ t('common.create') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Token Created Dialog (Show Once) -->
    <el-dialog
      v-model="showTokenDialog"
      :title="t('profile.token_created')"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-alert
        :title="t('profile.token_copy_warning')"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      
      <div class="token-display">
        <el-input
          v-model="newTokenValue"
          readonly
          type="textarea"
          :rows="3"
        />
        <el-button 
          type="primary" 
          @click="copyToken"
          style="margin-top: 12px"
        >
          <el-icon><CopyDocument /></el-icon>
          {{ copied ? t('profile.copied') : t('profile.copy_token') }}
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Plus, CopyDocument } from '@element-plus/icons-vue'
import { patApi } from '@/api/pat'
import type { PATResponse, PATCreateRequest } from '@/types'
import dayjs from 'dayjs'

const { t } = useI18n()

// State
const loading = ref(false)
const creating = ref(false)
const tokens = ref<PATResponse[]>([])
const activeFilter = ref('active')
const showCreateDialog = ref(false)
const showTokenDialog = ref(false)
const newTokenValue = ref('')
const copied = ref(false)
const activeTokenCount = computed(() => tokens.value.filter(t => t.is_active).length)

// Form
const createForm = reactive<PATCreateRequest>({
  name: '',
  expires_in_days: 90, // Default to 90 days
})

const createRules = {
  name: [
    { required: true, message: t('profile.token_name_required'), trigger: 'blur' },
    { min: 1, max: 100, message: t('profile.token_name_length'), trigger: 'blur' },
  ],
}

// Load tokens
const loadTokens = async () => {
  loading.value = true
  try {
    const response = await patApi.listTokens(activeFilter.value === 'expired')
    tokens.value = response.items
  } catch (error) {
    console.error('Failed to load tokens:', error)
    ElMessage.error(t('profile.load_tokens_failed'))
  } finally {
    loading.value = false
  }
}

// Create token
const handleCreateToken = async () => {
  creating.value = true
  try {
    const response = await patApi.createToken(createForm)
    newTokenValue.value = response.token
    showCreateDialog.value = false
    showTokenDialog.value = true
    await loadTokens()
    ElMessage.success(t('profile.token_created_success'))
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || t('profile.create_token_failed'))
  } finally {
    creating.value = false
  }
}

// Revoke token
const handleRevoke = async (tokenId: number) => {
  try {
    await patApi.revokeToken(tokenId)
    ElMessage.success(t('profile.token_revoked_success'))
    await loadTokens()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || t('profile.revoke_token_failed'))
  }
}

// Copy token
const copyToken = async () => {
  try {
    await navigator.clipboard.writeText(newTokenValue.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (error) {
    ElMessage.error(t('profile.copy_failed'))
  }
}

// Reset form
const resetForm = () => {
  createForm.name = ''
  createForm.expires_in_days = 90
}

// Format date
const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
}

// Initialize
onMounted(() => {
  loadTokens()
})
</script>

<style scoped>
.pat-management {
  padding: 20px 0;
}

.pat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.pat-header h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
}

.subtitle {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.token-display {
  margin-top: 16px;
}

code {
  background: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
}
</style>
```

#### 6.4 Integration into ProfileView

Add new tab in `frontend/src/views/auth/ProfileView.vue`:

```vue
<!-- After existing tabs -->
<el-tab-pane :label="t('profile.api_tokens')" name="tokens">
  <PATManagement />
</el-tab-pane>
```

Import component:
```typescript
import PATManagement from '@/components/profile/PATManagement.vue'
```

---

### Phase 7: i18n Translations

Add to all three locale files:

#### `frontend/src/locales/en.json`
```json
{
  "profile": {
    "api_tokens": "API Tokens",
    "manage_tokens": "Manage Personal Access Tokens",
    "tokens_description": "Create and manage tokens for API authentication",
    "create_token": "Create New Token",
    "token_name": "Token Name",
    "token_name_placeholder": "e.g., GitHub Integration, CI/CD Pipeline",
    "token_name_required": "Please enter a token name",
    "token_name_length": "Token name must be between 1 and 100 characters",
    "expiration": "Expiration",
    "expiry_7_days": "7 days",
    "expiry_30_days": "30 days",
    "expiry_90_days": "90 days",
    "expiry_365_days": "365 days",
    "never_expires": "Never Expires",
    "token_created_success": "Token created successfully",
    "token_created": "Token Created",
    "token_copy_warning": "Copy this token now. It will not be shown again!",
    "copy_token": "Copy Token",
    "copied": "Copied!",
    "copy_failed": "Failed to copy token",
    "revoke_token": "Revoke",
    "confirm_revoke": "Are you sure you want to revoke this token? This action cannot be undone.",
    "token_revoked_success": "Token revoked successfully",
    "active_tokens": "Active Tokens",
    "expired_tokens": "Expired Tokens",
    "token_limit_warning": "You can have at most 10 active tokens",
    "last_used": "Last Used",
    "never_used": "Never Used",
    "created_at": "Created At",
    "expires_at": "Expires At",
    "load_tokens_failed": "Failed to load tokens",
    "create_token_failed": "Failed to create token",
    "revoke_token_failed": "Failed to revoke token",
    "no_tokens": "No tokens found"
  }
}
```

#### `frontend/src/locales/zh-CN.json`
```json
{
  "profile": {
    "api_tokens": "API令牌",
    "manage_tokens": "管理个人访问令牌",
    "tokens_description": "创建和管理用于API身份验证的令牌",
    "create_token": "创建新令牌",
    "token_name": "令牌名称",
    "token_name_placeholder": "例如：GitHub集成、CI/CD流水线",
    "token_name_required": "请输入令牌名称",
    "token_name_length": "令牌名称必须在1到100个字符之间",
    "expiration": "过期时间",
    "expiry_7_days": "7天",
    "expiry_30_days": "30天",
    "expiry_90_days": "90天",
    "expiry_365_days": "365天",
    "never_expires": "永不过期",
    "token_created_success": "令牌创建成功",
    "token_created": "令牌已创建",
    "token_copy_warning": "请立即复制此令牌。它将不再显示！",
    "copy_token": "复制令牌",
    "copied": "已复制！",
    "copy_failed": "复制令牌失败",
    "revoke_token": "撤销",
    "confirm_revoke": "确定要撤销此令牌吗？此操作无法撤销。",
    "token_revoked_success": "令牌撤销成功",
    "active_tokens": "活跃令牌",
    "expired_tokens": "已过期令牌",
    "token_limit_warning": "您最多可以有10个活跃令牌",
    "last_used": "最后使用",
    "never_used": "从未使用",
    "created_at": "创建时间",
    "expires_at": "过期时间",
    "load_tokens_failed": "加载令牌失败",
    "create_token_failed": "创建令牌失败",
    "revoke_token_failed": "撤销令牌失败",
    "no_tokens": "未找到令牌"
  }
}
```

#### `frontend/src/locales/zh-TW.json`
```json
{
  "profile": {
    "api_tokens": "API權杖",
    "manage_tokens": "管理個人存取權杖",
    "tokens_description": "建立和管理用於API身份驗證的權杖",
    "create_token": "建立新權杖",
    "token_name": "權杖名稱",
    "token_name_placeholder": "例如：GitHub整合、CI/CD流水線",
    "token_name_required": "請輸入權杖名稱",
    "token_name_length": "權杖名稱必須在1到100個字元之間",
    "expiration": "過期時間",
    "expiry_7_days": "7天",
    "expiry_30_days": "30天",
    "expiry_90_days": "90天",
    "expiry_365_days": "365天",
    "never_expires": "永不過期",
    "token_created_success": "權杖建立成功",
    "token_created": "權杖已建立",
    "token_copy_warning": "請立即複製此權杖。它將不再顯示！",
    "copy_token": "複製權杖",
    "copied": "已複製！",
    "copy_failed": "複製權杖失敗",
    "revoke_token": "撤銷",
    "confirm_revoke": "確定要撤銷此權杖嗎？此操作無法復原。",
    "token_revoked_success": "權杖撤銷成功",
    "active_tokens": "活躍權杖",
    "expired_tokens": "已過期權杖",
    "token_limit_warning": "您最多可以有10個活躍權杖",
    "last_used": "最後使用",
    "never_used": "從未使用",
    "created_at": "建立時間",
    "expires_at": "過期時間",
    "load_tokens_failed": "載入權杖失敗",
    "create_token_failed": "建立權杖失敗",
    "revoke_token_failed": "撤銷權杖失敗",
    "no_tokens": "未找到權杖"
  }
}
```

---

### Phase 8: Background Task for Cleanup

**File**: `src/tasks/cleanup_tasks.py`

```python
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.pat_service import PATService

logger = logging.getLogger(__name__)


async def cleanup_expired_pats(db: AsyncSession) -> int:
    """
    Cleanup expired PATs older than 3 months
    
    Should be scheduled to run daily or weekly
    """
    pat_service = PATService(db)
    deleted_count = await pat_service.cleanup_expired_tokens()
    
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} expired PATs")
    
    return deleted_count
```

**Schedule with Celery or APScheduler** (if project uses task scheduler).

---

### Phase 9: Testing

#### 9.1 Unit Tests (`tests/test_pat_service.py`)

```python
import pytest
from datetime import UTC, datetime, timedelta

from src.services.pat_service import PATService


@pytest.mark.asyncio
async def test_create_token(db_session):
    """Test token creation"""
    service = PATService(db_session)
    
    token, record = await service.create_token(
        auth_user_id=1,
        name="Test Token",
        expires_in_days=30,
    )
    
    assert token.startswith("pat_")
    assert record.name == "Test Token"
    assert record.is_active == True


@pytest.mark.asyncio
async def test_validate_token(db_session):
    """Test token validation"""
    service = PATService(db_session)
    
    token, record = await service.create_token(
        auth_user_id=1,
        name="Test Token",
        expires_in_days=30,
    )
    
    validated = await service.validate_token(token)
    assert validated is not None
    assert validated.id == record.id


@pytest.mark.asyncio
async def test_token_expiration(db_session):
    """Test expired token validation"""
    service = PATService(db_session)
    
    token, record = await service.create_token(
        auth_user_id=1,
        name="Test Token",
        expires_in_days=1,
    )
    
    # Manually expire
    record.expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()
    
    validated = await service.validate_token(token)
    assert validated is None


@pytest.mark.asyncio
async def test_token_limit(db_session):
    """Test maximum token limit"""
    service = PATService(db_session)
    
    # Create 10 tokens
    for i in range(10):
        await service.create_token(
            auth_user_id=1,
            name=f"Token {i}",
            expires_in_days=30,
        )
    
    # 11th should fail
    with pytest.raises(Exception):
        await service.create_token(
            auth_user_id=1,
            name="Token 11",
            expires_in_days=30,
        )
```

#### 9.2 API Tests (`tests/test_pat_api.py`)

```python
@pytest.mark.asyncio
async def test_list_tokens(async_client, auth_headers):
    """Test listing tokens"""
    response = await async_client.get(
        "/api/v1/personal-access-tokens/",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "items" in response.json()


@pytest.mark.asyncio
async def test_create_token(async_client, auth_headers):
    """Test creating token"""
    response = await async_client.post(
        "/api/v1/personal-access-tokens/",
        headers=auth_headers,
        json={
            "name": "Test Token",
            "expires_in_days": 30,
        },
    )
    assert response.status_code == 201
    assert "token" in response.json()


@pytest.mark.asyncio
async def test_revoke_token(async_client, auth_headers):
    """Test revoking token"""
    # Create token first
    create_response = await async_client.post(
        "/api/v1/personal-access-tokens/",
        headers=auth_headers,
        json={"name": "Test Token"},
    )
    token_id = create_response.json()["id"]
    
    # Revoke
    response = await async_client.delete(
        f"/api/v1/personal-access-tokens/{token_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
```

#### 9.3 E2E Tests (`frontend/e2e/pat-management.spec.ts`)

```typescript
import { expect, test } from '@playwright/test'

test.describe('PAT Management', () => {
  test('create and revoke token', async ({ page }) => {
    // Login
    await page.goto('/login')
    await page.getByPlaceholder('Username').fill('testuser')
    await page.getByPlaceholder('Password').fill('password123')
    await page.getByRole('button', { name: 'Login' }).click()
    
    // Navigate to profile
    await page.goto('/profile')
    await page.getByRole('tab', { name: 'API Tokens' }).click()
    
    // Create token
    await page.getByRole('button', { name: 'Create New Token' }).click()
    await page.getByPlaceholder('Token Name').fill('E2E Test Token')
    await page.getByRole('button', { name: 'Create' }).click()
    
    // Verify token shown
    await expect(page.getByText('Token Created')).toBeVisible()
    const tokenValue = await page.locator('.token-display textarea').inputValue()
    expect(tokenValue).toMatch(/^pat_/)
    
    // Copy token
    await page.getByRole('button', { name: 'Copy Token' }).click()
    await expect(page.getByText('Copied!')).toBeVisible()
    
    // Close dialog
    await page.keyboard.press('Escape')
    
    // Verify token in list
    await expect(page.getByText('E2E Test Token')).toBeVisible()
    
    // Revoke token
    await page.getByRole('button', { name: 'Revoke' }).first().click()
    await page.getByRole('button', { name: 'Confirm' }).click()
    
    await expect(page.getByText('Token revoked successfully')).toBeVisible()
  })
})
```

---

## Security Considerations

1. **Token Storage**: Never store plain text tokens, only hashes
2. **Rate Limiting**: Prevent abuse with creation limits
3. **Constant-Time Comparison**: Prevent timing attacks on hash verification
4. **Audit Logging**: Log all token operations for security monitoring
5. **HTTPS Only**: Tokens should only be transmitted over HTTPS
6. **Token Rotation**: Encourage users to rotate tokens periodically
7. **Minimal Permissions**: PATs inherit user permissions, no elevation

---

## Deployment Checklist

- [ ] Run database migration: `alembic upgrade head`
- [ ] Verify indexes created: `SHOW INDEX FROM personal_access_token;`
- [ ] Test token creation via API
- [ ] Test PAT authentication
- [ ] Verify frontend UI displays correctly
- [ ] Test token revocation
- [ ] Verify expired token cleanup job
- [ ] Monitor logs for errors
- [ ] Update API documentation
- [ ] Notify users about new feature

---

## Future Enhancements

1. **Token Scopes**: Allow users to restrict token permissions (read-only, write, admin)
2. **IP Whitelisting**: Restrict token usage to specific IP addresses
3. **Usage Analytics**: Show detailed API usage statistics per token
4. **Webhook Notifications**: Notify on token creation/revocation
5. **Bulk Operations**: Revoke multiple tokens at once
6. **Token Templates**: Pre-configured token settings for common use cases

---

## References

- [GitHub Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [GitLab Personal Access Tokens](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html)
- [OAuth 2.0 Bearer Token Usage](https://tools.ietf.org/html/rfc6750)
