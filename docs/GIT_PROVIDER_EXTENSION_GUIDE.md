# Git Provider Extension Guide

This document describes how to extend the system with new Git providers (e.g., GitLab, Azure DevOps, Gitea).

## Architecture Overview

The Git provider system follows the **Strategy Pattern** with a factory for provider resolution:

```
src/core/git_provider.py          ← Enum definition (single source of truth)
src/services/git_providers/
├── base.py                       ← Abstract interface (BaseGitProvider)
├── bitbucket_server.py           ← Bitbucket Server implementation
├── github_enterprise.py          ← GitHub Enterprise implementation
└── __init__.py                   ← Factory (get_git_provider)
frontend/src/constants/gitProvider.ts ← Frontend constants (mirrors backend enum)
```

Provider-specific logic is isolated behind the `BaseGitProvider` interface. All other services interact with Git providers exclusively through this abstraction.

---

## Step-by-Step: Adding a New Provider

Using **GitLab** as an example.

### 1. Backend — Register the Enum Value

**File**: `src/core/git_provider.py`

```python
class GitProvider(StrEnum):
    BITBUCKET_SERVER = "bitbucket_server"
    BITBUCKET_CLOUD = "bitbucket_cloud"
    GITHUB_ENTERPRISE = "github_enterprise"
    GITLAB = "gitlab"                  # ← Add new member
```

The enum is the single source of truth. All defaults, validations, and descriptions across the codebase derive from it automatically.

### 2. Backend — Add Environment Variables

**File**: `src/core/config.py`

Add configuration fields following the existing naming convention (`<PROVIDER>_<SETTING>`):

```python
# GitLab API configuration
GITLAB_URL: str | None = Field(
    default=None,
    description="GitLab instance base URL (e.g., https://gitlab.example.com)",
)
GITLAB_TOKEN: str | None = Field(
    default=None,
    description="GitLab personal access token or project token",
)
```

**File**: `.env.example`

```bash
# GitLab
GITLAB_URL=
GITLAB_TOKEN=
```

### 3. Backend — Implement the Provider

**File**: `src/services/git_providers/gitlab.py`

```python
from __future__ import annotations

import logging
from typing import Any

import httpx

from src.core.config import settings
from src.core.git_provider import GitProvider
from src.services.git_providers.base import BaseGitProvider

logger = logging.getLogger(__name__)


class GitLabProvider(BaseGitProvider):
    """Adapter for GitLab REST API."""

    def __init__(self) -> None:
        self._base_url = getattr(settings, "GITLAB_URL", None)
        if not self._base_url:
            logger.warning("GITLAB_URL is not configured")

        self.headers: dict[str, str] = {"Content-Type": "application/json"}
        token = getattr(settings, "GITLAB_TOKEN", None)
        if token:
            self.headers["PRIVATE-TOKEN"] = token

    @property
    def name(self) -> str:
        return GitProvider.GITLAB.value

    async def get_project_info(self, project_key: str) -> dict[str, Any] | None:
        # Implement GitLab project API call
        ...

    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any] | None:
        # Implement GitLab repository API call
        ...

    async def get_user_info(self, username: str) -> dict[str, Any] | None:
        # Implement GitLab user API call
        ...
```

The provider must implement all abstract methods defined in `BaseGitProvider`.

### 4. Backend — Register in Factory

**File**: `src/services/git_providers/__init__.py`

```python
elif provider_str == GitProvider.GITLAB:
    from src.services.git_providers.gitlab import GitLabProvider
    provider = GitLabProvider()
```

### 5. Frontend — Register the Constant

**File**: `frontend/src/constants/gitProvider.ts`

```typescript
export const GitProvider = {
  BITBUCKET_SERVER: 'bitbucket_server',
  BITBUCKET_CLOUD: 'bitbucket_cloud',
  GITHUB_ENTERPRISE: 'github_enterprise',
  GITLAB: 'gitlab',                    // ← Add new member
} as const
```

Update `GIT_PROVIDER_OPTIONS` if the provider should appear in UI dropdowns:

```typescript
export const GIT_PROVIDER_OPTIONS = [
  { value: GitProvider.BITBUCKET_SERVER, label: 'Bitbucket Server' },
  { value: GitProvider.GITHUB_ENTERPRISE, label: 'GitHub Enterprise' },
  { value: GitProvider.GITLAB, label: 'GitLab' },
] as const
```

Update `getGitProviderTagType` if a custom tag color is desired:

```typescript
case GitProvider.GITLAB: return 'warning'
```

### 6. Frontend — Update PR URL Generation

**File**: `frontend/src/composables/usePrUrl.ts`

```typescript
if (gitProvider === GitProvider.GITLAB) {
  // GitLab: <project_url>/<repo>/-/merge_requests/<id>
  return `${baseUrl}/${review.repository_slug}/-/merge_requests/${review.pull_request_id}`
}
```

Also update `getPRUrl` in `frontend/src/views/scores/ScoreListView.vue` with the same logic.

---

## Checklist

| # | Location | What to Update |
|---|----------|---------------|
| 1 | `src/core/git_provider.py` | Add enum member |
| 2 | `src/core/config.py` | Add `FIELD_*` env variables |
| 3 | `.env.example` | Document new env variables |
| 4 | `src/services/git_providers/<provider>.py` | Create provider class |
| 5 | `src/services/git_providers/__init__.py` | Register in factory |
| 6 | `frontend/src/constants/gitProvider.ts` | Add constant + UI options |
| 7 | `frontend/src/composables/usePrUrl.ts` | Add PR URL pattern |
| 8 | `frontend/src/views/scores/ScoreListView.vue` | Add PR URL pattern |

---

## Key Design Principles

- **Single source of truth**: The `GitProvider` enum drives all defaults, validations, and API descriptions.
- **Open/Closed**: New providers are added by extension (new enum member + new class), never by modifying existing provider code.
- **Provider isolation**: All Git API calls go through `BaseGitProvider`. No service outside `git_providers/` makes provider-specific API calls.
- **Backward compatibility**: Existing providers are unaffected when new ones are added. The `get_git_provider()` factory falls back to `BITBUCKET_SERVER` for unknown values.
