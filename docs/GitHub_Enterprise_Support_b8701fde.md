# GitHub Enterprise Support

## Architecture Overview

The current system is already largely provider-agnostic at the review ingestion layer. The `ReviewCreate` schema uses generic fields (`project_key`, `repository_slug`, `pull_request_id`, `git_code_diff`, etc.) that work for any Git provider. The provider-specific code is isolated to:

1. `BitbucketService` (`src/services/bitbucket_service.py`) -- fetches project/repo/user metadata from Bitbucket REST API
2. `EntitySyncService` (`src/services/entity_sync_service.py`) -- orchestrates entity sync, calls `BitbucketService`
3. `usePrUrl.ts` -- constructs Bitbucket-specific PR URLs
4. Global config (`BITBUCKET_*` in `src/core/config.py`) -- single-provider assumption

**Audit of direct `BitbucketService` usage**: Only `EntitySyncService` imports and uses `get_bitbucket_service()`. No other service calls Bitbucket API directly. This is clean isolation.

**Audit of `EntitySyncService` callers** (3 sites):
- `review_service.py` line 490 (`create_review`) -- `EntitySyncService(db)`
- `review_service.py` line 641 (`upsert_review`) -- `EntitySyncService(db)`
- `review_score_service.py` line 66 (`submit_score`) -- `EntitySyncService(db)`

All three create it without provider info. The provider must be determined internally with zero breaking changes to these callers.

The plan introduces a **provider abstraction** and **per-project provider tracking** so both Bitbucket Server and GitHub Enterprise coexist.

---

## Task 1: Database Migration -- Add `git_provider` to `project_registry`

**File**: `alembic/versions/029_add_git_provider_to_project_registry.py`

Add a `git_provider` column (String(32), default `"bitbucket_server"`) to `project_registry` table.

```python
git_provider: Mapped[str] = mapped_column(
    String(32), nullable=False, default="bitbucket_server", server_default="bitbucket_server"
)
```

Valid values: `bitbucket_server`, `bitbucket_cloud`, `github_enterprise`.

---

## Task 2: Provider Abstraction -- Create `src/services/git_providers/`

Create a provider package with an abstract base and concrete implementations:

**`src/services/git_providers/__init__.py`** -- Provider registry/factory:
```python
def get_git_provider(provider_name: str) -> BaseGitProvider:
    """Factory to get the appropriate git provider instance"""
```

**`src/services/git_providers/base.py`** -- Abstract base class:
```python
class BaseGitProvider(ABC):
    @abstractmethod
    async def get_project_info(self, project_key: str) -> dict | None: ...
    
    @abstractmethod
    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict | None: ...
    
    @abstractmethod
    async def get_user_info(self, username: str) -> dict | None: ...
```

**`src/services/git_providers/bitbucket_server.py`** -- Extract from existing `BitbucketService`:
- Wrap the existing `BitbucketService` methods to conform to `BaseGitProvider` interface.
- No behavior change, just adapter pattern.

**`src/services/git_providers/github_enterprise.py`** -- New GitHub Enterprise provider:
- `get_project_info()` -- GitHub doesn't have a "project" concept like Bitbucket. Map org/repo owner to project. Use `GET /api/v3/orgs/{org}` or `GET /api/v3/users/{owner}`.
- `get_repository_info()` -- `GET /api/v3/repos/{owner}/{repo}` with GitHub API response mapping.
- `get_user_info()` -- `GET /api/v3/users/{username}` with GitHub API response mapping.
- Auth: `Authorization: Bearer <token>` or `Authorization: token <token>` header.
- Base URL: Configurable `https://github.example.com/api/v3`.

---

## Task 3: Config -- Add GitHub Enterprise Settings

**File**: `src/core/config.py`

Add new config fields alongside existing Bitbucket config:

```python
# GitHub Enterprise API configuration
GITHUB_ENTERPRISE_URL: str | None = Field(
    default=None, description="GitHub Enterprise base URL (e.g., https://github.example.com)"
)
GITHUB_ENTERPRISE_TOKEN: str | None = Field(
    default=None, description="GitHub Enterprise personal access token or app token"
)
```

**File**: `.env`, `.env.example` -- Add corresponding env vars:
```
GITHUB_ENTERPRISE_URL=https://github.example.com
GITHUB_ENTERPRISE_TOKEN=ghp_xxxx
```

---

## Task 4: Update `EntitySyncService` for Provider Routing (Backward Compatible)

**File**: `src/services/entity_sync_service.py`

**Goal**: Route to the correct provider per project WITHOUT changing any of the 3 caller sites.

### Provider Resolution Strategy (Lazy + Memoized)

```python
class EntitySyncService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._provider: BaseGitProvider | None = None  # lazy resolved

    async def _resolve_provider(self) -> BaseGitProvider:
        """Lazy-resolve provider on first use, then memoize for the session."""
        if self._provider is not None:
            return self._provider
        # Default to bitbucket_server -- preserves existing behavior exactly
        self._provider = get_git_provider("bitbucket_server")
        return self._provider

    async def _try_resolve_provider_from_registry(
        self, project_key: str, repository_slug: str
    ) -> None:
        """Try to determine provider from project_registry (best effort)."""
        try:
            result = await self.db.execute(
                select(ProjectRegistry).where(
                    and_(
                        ProjectRegistry.project_key == project_key,
                        ProjectRegistry.repository_slug == repository_slug,
                    )
                )
            )
            entry = result.scalar_one_or_none()
            if entry:
                self._provider = get_git_provider(entry.git_provider)
        except Exception:
            pass  # Fall back to default
```

### Updated Method Flow

1. `sync_project(project_key)`:
   - Check if project exists in `project` table (existing behavior, unchanged)
   - If exists, return it (no provider needed -- entity already synced)
   - If not, use `_resolve_provider()` (defaults to `bitbucket_server`) to fetch from API
   - This is the **backward compatible path**: existing projects work identically

2. `sync_repository(repository_slug, project)`:
   - Check if repository exists (existing behavior)
   - If not, call `_try_resolve_provider_from_registry(project.project_key, repository_slug)` to refine provider
   - Then use resolved provider for API call

3. `sync_user(username, is_reviewer)`:
   - Check if user exists (existing behavior)
   - If not, use current provider for API call

### Why This Is Safe

- **Existing Bitbucket projects**: `project` already exists in DB -> `sync_project()` returns immediately, no provider resolution needed. All subsequent calls use Bitbucket as before.
- **New Bitbucket projects (first review)**: Provider defaults to `bitbucket_server` -> identical to current behavior.
- **New GitHub projects**: Admin pre-registers in project_registry with `git_provider=github_enterprise` -> `_try_resolve_provider_from_registry()` picks up GitHub provider for API calls.
- **Caller sites unchanged**: All 3 callers still do `EntitySyncService(db)` with no new parameters.

---

## Task 5: Update `ProjectRegistry` Model and Schema

**File**: `src/models/project_registry.py`
- Add `git_provider` column with default `"bitbucket_server"`.

**File**: `src/schemas/` (new or existing)
- Add `git_provider` to project registry response schemas.

**File**: `src/api/v1/endpoints/project_registry.py`
- Add `git_provider` parameter to `register_project_to_app()` endpoint.
- Include `git_provider` in all list/get responses.

---

## Task 6: Frontend -- Project Registry Management

**File**: `frontend/src/api/projectRegistry.ts`
- Add `git_provider` to `ProjectRegistry` interface.
- Add `git_provider` param to `registerProject()`.

**File**: `frontend/src/views/admin/ProjectRegistryManagementView.vue`
- Add provider dropdown (Bitbucket Server / Bitbucket Cloud / GitHub Enterprise) in the registration dialog.
- Show provider column in the project table.

---

## Task 7: Frontend -- PR URL Generation

**File**: `frontend/src/composables/usePrUrl.ts`

Update to generate provider-appropriate URLs:

```typescript
// Bitbucket Server: <project_url>/repos/<slug>/pull-requests/<id>/diff
// GitHub Enterprise: <project_url>/<slug>/pull/<id>  (or <org_url>/<repo>/pull/<id>)
```

The `project_url` stored in the `project` table already reflects the provider-specific base URL, so the URL construction just needs to use the right path format. Consider storing `git_provider` in the review response or deriving it from `project_url` patterns.

---

## Task 8: Frontend -- i18n and Label Updates

**Files**: `frontend/src/locales/en.json`, `zh-CN.json`, `zh-TW.json`
- Update "Bitbucket" references to "Git Provider" or "Bitbucket/GitHub" where user-facing.
- Add provider-related labels.

**Files**: Various Vue components that say "Bitbucket" in user-facing text:
- `DelegationForm.vue` -- "Bitbucket Status" labels
- `GitUserManagementView.vue` -- Page title/description
- `SystemUserManagementView.vue` -- Deletion warning text

---

## Task 9: Backward Compatibility Verification

### What Must NOT Break

| Existing Behavior | Protection |
|---|---|
| `EntitySyncService(db)` constructor signature | No new required params; provider is resolved lazily |
| `BitbucketService` singleton | Kept as-is; wrapped by `bitbucket_server.py` adapter |
| `BITBUCKET_*` config vars | Still used by `BitbucketService`; unchanged |
| `project.project_id` (Integer) | GitHub Enterprise IDs fit in 32-bit for self-hosted; no migration needed |
| `user.user_id` (Integer) | Same as above |
| `repository.repository_id` (Integer) | Same as above |
| First-review-without-registration flow | Defaults to `bitbucket_server` provider, same as today |
| All 3 `EntitySyncService` caller sites | Zero changes to `review_service.py` or `review_score_service.py` |
| Existing `project_registry` entries | `server_default="bitbucket_server"` ensures all existing rows get correct default |

### Verification Steps

- `ruff format && ruff check --fix` on all Python changes
- `uv run python -c "from src.services.git_providers import get_git_provider; ..."` -- import check
- `alembic revision --autogenerate -m "add git_provider to project_registry"` -- generate migration
- `vue-tsc --noEmit && vite build` -- frontend build check
- Deploy to staging with existing Bitbucket projects -> verify reviews still ingest correctly
- Register a new project with `git_provider=github_enterprise` -> verify GitHub API calls work
- Verify `EntitySyncService` callers (review_service, review_score_service) need zero changes

---

## Summary of Changes

| Area | Files | Impact |
|---|---|---|
| DB Migration | `alembic/versions/029_*.py` | New `git_provider` column on `project_registry` |
| Provider Abstraction | `src/services/git_providers/` (new package) | Abstract base + Bitbucket adapter + GitHub Enterprise impl |
| Config | `src/core/config.py`, `.env`, `.env.example` | New `GITHUB_ENTERPRISE_*` settings |
| Entity Sync | `src/services/entity_sync_service.py` | Lazy provider resolution; no caller changes |
| Project Registry | Model, schema, endpoint | Add `git_provider` field |
| Frontend | `projectRegistry.ts`, `ProjectRegistryManagementView.vue`, `usePrUrl.ts`, i18n | Provider selection in UI, correct PR URLs |

**Zero breaking changes**: All existing Bitbucket projects default to `git_provider = "bitbucket_server"`. The `EntitySyncService` constructor, `BitbucketService`, and all 3 caller sites remain unchanged.