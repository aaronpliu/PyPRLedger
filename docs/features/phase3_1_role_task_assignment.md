# Phase 3.1: Role-Based Access Control & Task Assignment

## 📋 Overview

This phase implements role-based review visibility and task assignment functionality:

1. **Review Visibility Control**: Users can only view reviews assigned to them, except review admins who can view all
2. **Auto-Role Assignment**: New registered users automatically receive the "reviewer" role
3. **Task Assignment**: Review admins can assign review tasks to other reviewers
4. **Role Management**: System admins can manage user roles through the admin interface

**Implementation Period**: Estimated 1.5 working days  
**Status**: 📝 Planning

---

## ✅ Current System Analysis

### Existing Infrastructure

#### Database Models
- ✅ `Role` table with predefined roles (viewer, reviewer, review_admin, system_admin)
- ✅ `UserRoleAssignment` table for RBAC mappings
- ✅ `AuthUser` table for authentication
- ✅ `User` table with `is_reviewer` field

#### RBAC System
- ✅ Permission checking mechanism (`check_permission`, `require_permission`)
- ✅ JWT authentication with token validation
- ✅ RBAC API endpoints for role management
- ✅ Pre-defined permissions in role JSON configuration

#### Current Roles (from migration 006)

| Role ID | Name | Description | Key Permissions |
|---------|------|-------------|----------------|
| 1 | viewer | Read-only access | reviews: read, scores: read |
| 2 | reviewer | Can submit reviews | reviews: read/create, scores: read/create/update |
| 3 | review_admin | Manage review data | reviews: CRUD, scores: CRUD, projects/repositories: manage |
| 4 | system_admin | Full system control | All permissions including user/role management |

### Identified Gaps

1. ❌ **Missing "assign" permission** - review_admin needs explicit "assign" permission for task assignment
2. ❌ **No auto-role assignment** - Registration doesn't assign default "reviewer" role
3. ❌ **No review filtering by role** - All users can currently see all reviews
4. ❌ **No task assignment API** - Missing endpoint to assign reviews to specific reviewers
5. ❌ **Incomplete role management UI** - UserManagementView has placeholder but no implementation

---

## 🎯 Implementation Plan

### Phase 1: Backend Implementation

#### 1.1 Update review_admin Role Permissions

**File**: `alembic/versions/007_add_assign_permission.py`

**Purpose**: Add "assign" permission to review_admin role for task assignment authorization

**Changes**:
```python
def upgrade():
    """Add 'assign' permission to review_admin role"""
    op.execute("""
        UPDATE role 
        SET permissions = '{
            "reviews": ["read", "create", "update", "delete", "assign"],
            "scores": ["read", "create", "update", "delete"],
            "projects": ["read", "manage"],
            "repositories": ["read", "manage"],
            "users": ["read"]
        }',
        updated_at = NOW()
        WHERE name = 'review_admin'
    """)
```

**Testing**:
- Verify review_admin role has "assign" permission in database
- Test permission check returns True for review_admin users

---

#### 1.2 Auto-Assign Reviewer Role on Registration

**File**: `src/services/auth_service.py`

**Purpose**: Automatically assign "reviewer" role to newly registered users

**Changes**:

1. Modify `register()` method:
```python
async def register(self, register_data: RegisterRequest) -> TokenResponse:
    # ... existing validation and user creation code ...
    
    self.db.add(new_auth_user)
    await self.db.commit()
    await self.db.refresh(new_auth_user)
    
    # ✨ NEW: Auto-assign reviewer role
    await self._assign_default_role(new_auth_user.id)
    
    # Create JWT token and return
    access_token = create_access_token(...)
    return TokenResponse(...)
```

2. Add helper method:
```python
async def _assign_default_role(self, auth_user_id: int):
    """Assign default 'reviewer' role to newly registered user
    
    Args:
        auth_user_id: The newly created auth user ID
    """
    from src.services.rbac_service import RBACService
    from sqlalchemy import select
    from src.models.role import Role
    
    rbac_service = RBACService(self.db)
    
    # Get reviewer role by name
    stmt = select(Role).where(Role.name == "reviewer")
    result = await self.db.execute(stmt)
    reviewer_role = result.scalar_one_or_none()
    
    if not reviewer_role:
        logger.warning("Reviewer role not found, skipping auto-assignment")
        return
    
    try:
        await rbac_service.assign_role(
            auth_user_id=auth_user_id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
            granted_by=None,  # System assigned
        )
        logger.info(f"Auto-assigned reviewer role to user {auth_user_id}")
    except Exception as e:
        logger.error(f"Failed to assign default role to user {auth_user_id}: {e}")
        # Don't fail registration if role assignment fails
```

**Edge Cases**:
- If reviewer role doesn't exist, log warning but don't fail registration
- If role assignment fails, log error but continue (user can be manually assigned later)

**Testing**:
- Register a new user and verify they have reviewer role in `user_role_assignment` table
- Check role is assigned with resource_type='global' and resource_id=NULL

---

#### 1.3 Review List API - Role-Based Filtering

**File**: `src/api/v1/endpoints/reviews.py`

**Purpose**: Filter reviews based on user role - regular users see only their assigned reviews, review admins see all

**Changes**:

1. Add current_user dependency to `list_reviews()`:
```python
@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],  # ✨ NEW
    pull_request_id: str | None = Query(None),
    project_key: str | None = Query(None),
    # ... other parameters unchanged ...
) -> ReviewListResponse:
    """
    List pull request reviews with filtering and pagination
    
    Access Control:
    - review_admin: Can view ALL reviews
    - reviewer: Can only view reviews where reviewer field matches their username
    """
    try:
        from src.services.rbac_service import RBACService
        
        rbac_service = RBACService(db)
        
        # Check if user has review_admin role (by checking 'assign' permission)
        is_review_admin = await rbac_service.check_permission(
            auth_user_id=current_user.id,
            action="assign",
            resource_type="reviews",
        )
        
        filters = ReviewFilter(
            pull_request_id=pull_request_id,
            project_key=project_key,
            # ... other filters ...
        )
        
        # ✨ NEW: Apply role-based filtering
        if not is_review_admin:
            # Regular user - filter by their git username
            git_username = await _get_git_username(current_user.id, db)
            
            if git_username:
                filters.reviewer = git_username
                logger.info(
                    f"Regular user {current_user.username} filtered by reviewer={git_username}"
                )
            else:
                # No linked git user - return empty list
                logger.warning(
                    f"User {current_user.username} has no linked Git account"
                )
                return ReviewListResponse(items=[], total=0, page=page, page_size=page_size)
        else:
            logger.info(f"Review admin {current_user.username} accessing all reviews")
        
        # Continue with existing logic
        enriched_reviews, total = await review_service.list_reviews_with_entities(
            filters, db, page, page_size, app_names=app_names_list
        )
        
        review_responses = [ReviewResponse(**review) for review in enriched_reviews]
        
        return ReviewListResponse(
            items=review_responses,
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        logger.error(f"Failed to list reviews: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to list reviews"},
        )
```

2. Add helper function at module level:
```python
async def _get_git_username(auth_user_id: int, db: AsyncSession) -> str | None:
    """Get git username linked to auth user
    
    Args:
        auth_user_id: Auth user ID
        db: Database session
    
    Returns:
        Git username or None if not linked
    """
    from src.models.auth_user import AuthUser
    from src.models.user import User
    from sqlalchemy import select
    
    # Get auth user
    stmt = select(AuthUser).where(AuthUser.id == auth_user_id)
    result = await db.execute(stmt)
    auth_user = result.scalar_one_or_none()
    
    if not auth_user or not auth_user.user_id:
        return None
    
    # Get linked git user
    stmt = select(User).where(User.id == auth_user.user_id)
    result = await db.execute(stmt)
    git_user = result.scalar_one_or_none()
    
    return git_user.username if git_user else None
```

**Important Notes**:
- This filtering applies to the main review list endpoint only
- Direct PR lookup (`GET /reviews/{project}/{repo}/{pr_id}`) remains accessible to all authenticated users
- Other filtered endpoints (by project, reviewer, status) also need similar updates

**Testing**:
- Login as regular user and verify only their reviews are shown
- Login as review_admin and verify all reviews are visible
- Test with user who has no linked Git account (should return empty list)

---

#### 1.4 Task Assignment API Endpoint

**File**: `src/api/v1/endpoints/reviews.py`

**Purpose**: Allow review admins to assign review tasks to specific reviewers

**New Schema** - `src/schemas/pull_request.py`:
```python
class ReviewAssignmentRequest(BaseModel):
    """Schema for assigning review task to a reviewer"""
    
    pull_request_id: str = Field(..., description="Pull request ID")
    project_key: str = Field(..., min_length=1, max_length=32, description="Project key")
    repository_slug: str = Field(..., min_length=1, max_length=128, description="Repository slug")
    assignee_username: str = Field(
        ..., 
        min_length=1, 
        max_length=64, 
        description="Reviewer username to assign"
    )
    pull_request_user: str = Field(..., min_length=1, max_length=64, description="PR author username")
    source_branch: str = Field(..., min_length=1, description="Source branch")
    target_branch: str = Field(..., min_length=1, description="Target branch")
    pull_request_commit_id: str | None = Field(None, description="Commit ID (optional)")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "pull_request_id": "123",
                "project_key": "PROJ",
                "repository_slug": "my-repo",
                "assignee_username": "john_doe",
                "pull_request_user": "jane_smith",
                "source_branch": "feature/new-feature",
                "target_branch": "main",
            }
        }
    }
```

**New Endpoint**:
```python
@router.post("/assign", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def assign_review_task(
    assignment_data: ReviewAssignmentRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewResponse:
    """
    Assign a review task to a reviewer (requires review_admin role)
    
    Creates a new review record with the specified reviewer.
    Only users with 'assign' permission on 'reviews' can use this endpoint.
    
    Args:
        assignment_data: Assignment details
        db: Database session
        current_user: Authenticated user (must be review_admin)
        review_service: Review service instance
    
    Returns:
        ReviewResponse: The created review
    
    Raises:
        ForbiddenException: If user lacks assign permission
        NotFoundException: If assignee not found
        HTTPException: 400 if assignee is not a reviewer
    """
    from src.services.rbac_service import RBACService
    from src.models.user import User
    from src.schemas.pull_request import ReviewCreate
    from sqlalchemy import select
    
    # Check permission - must have 'assign' permission (review_admin)
    rbac_service = RBACService(db)
    await rbac_service.require_permission(
        auth_user_id=current_user.id,
        action="assign",
        resource_type="reviews",
    )
    
    # Verify assignee exists
    stmt = select(User).where(User.username == assignment_data.assignee_username)
    result = await db.execute(stmt)
    assignee = result.scalar_one_or_none()
    
    if not assignee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reviewer '{assignment_data.assignee_username}' not found",
        )
    
    # Verify assignee is a reviewer
    if not assignee.is_reviewer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User '{assignment_data.assignee_username}' is not marked as a reviewer",
        )
    
    # Create review with assigned reviewer
    review_data = ReviewCreate(
        pull_request_id=assignment_data.pull_request_id,
        project_key=assignment_data.project_key,
        repository_slug=assignment_data.repository_slug,
        reviewer=assignment_data.assignee_username,
        pull_request_user=assignment_data.pull_request_user,
        source_branch=assignment_data.source_branch,
        target_branch=assignment_data.target_branch,
        pull_request_status="open",
        pull_request_commit_id=assignment_data.pull_request_commit_id,
    )
    
    review, is_created = await review_service.upsert_review(review_data, db)
    
    # Log audit trail
    try:
        from src.services.audit_service import AuditService
        audit_service = AuditService(db)
        await audit_service.log_action(
            auth_user_id=current_user.id,
            action="assign_review",
            resource_type="reviews",
            resource_id=f"{assignment_data.project_key}/{assignment_data.repository_slug}/{assignment_data.pull_request_id}",
            new_values={
                "assigned_to": assignment_data.assignee_username,
                "assigned_by": current_user.username,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to log audit for task assignment: {e}")
    
    logger.info(
        f"Review task assigned: PR {assignment_data.pull_request_id} "
        f"to {assignment_data.assignee_username} by {current_user.username}"
    )
    
    return ReviewResponse(**review.to_dict())
```

**Testing**:
- Test as review_admin - should successfully create review
- Test as regular reviewer - should get 403 Forbidden
- Test with non-existent assignee - should get 404
- Test with user who is not a reviewer - should get 400
- Verify audit log entry is created

---

### Phase 2: Frontend Implementation

#### 2.1 Enhance UserManagementView - Role Management

**File**: `frontend/src/views/admin/UserManagementView.vue`

**Purpose**: Allow system admins to view and manage user roles

**Key Features**:
- View current user roles
- Assign new roles with scope (global/project/repository)
- Revoke existing roles
- Confirmation dialogs for destructive actions

**Implementation Details**: See full code in implementation section

**Testing**:
- Login as system_admin
- Navigate to User Management
- Click "Manage Roles" on a user
- Verify current roles are displayed
- Assign a new role and verify it appears in the list
- Revoke a role and verify it's removed

---

#### 2.2 ReviewListView - Add Task Assignment Feature

**File**: `frontend/src/views/reviews/ReviewListView.vue`

**Purpose**: Allow review admins to assign review tasks from the Code Reviews page

**Key Features**:
- "Assign Review Task" button (visible only to review_admin)
- Dialog form with all required fields
- Reviewer selection dropdown
- Form validation
- Success/error feedback
- Auto-refresh after assignment

**Implementation Details**: See full code in implementation section

**Testing**:
- Login as review_admin
- Navigate to Code Reviews page
- Verify "Assign Review Task" button is visible
- Click button and fill form
- Submit and verify review is created
- Verify assigned reviewer can see the review in their list
- Login as regular reviewer and verify button is NOT visible

---

#### 2.3 Add Review Assignment API Method

**File**: `frontend/src/api/reviews.ts`

**Purpose**: Add API method for task assignment

**Changes**:
```typescript
export interface ReviewAssignmentRequest {
  pull_request_id: string
  project_key: string
  repository_slug: string
  assignee_username: string
  pull_request_user: string
  source_branch: string
  target_branch: string
  pull_request_commit_id?: string | null
}

export const reviewsApi = {
  // ... existing methods ...
  
  /**
   * Assign a review task to a reviewer (requires review_admin role)
   */
  assignTask(data: ReviewAssignmentRequest): Promise<Review> {
    return request.post('/reviews/assign', data)
  },
}
```

---

### Phase 3: Testing & Validation

#### 3.1 Backend Tests

**Test Scenarios**:

1. **Registration Auto-Assignment**:
   ```bash
   # Register new user
   curl -X POST http://localhost:8000/api/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{"username": "test_user", "email": "test@example.com", "password": "SecurePass123!"}'
   
   # Verify role assignment in database
   mysql> SELECT * FROM user_role_assignment WHERE auth_user_id = <new_user_id>;
   # Should show reviewer role
   ```

2. **Review List Filtering**:
   ```bash
   # Login as regular user
   TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "regular_user", "password": "password"}' | jq -r '.access_token')
   
   # Get reviews - should only show user's own reviews
   curl -X GET http://localhost:8000/api/v1/reviews \
     -H "Authorization: Bearer $TOKEN"
   
   # Login as review_admin
   ADMIN_TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "admin_user", "password": "password"}' | jq -r '.access_token')
   
   # Get reviews - should show ALL reviews
   curl -X GET http://localhost:8000/api/v1/reviews \
     -H "Authorization: Bearer $ADMIN_TOKEN"
   ```

3. **Task Assignment**:
   ```bash
   # As review_admin, assign task
   curl -X POST http://localhost:8000/api/v1/reviews/assign \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "pull_request_id": "999",
       "project_key": "TEST",
       "repository_slug": "test-repo",
       "assignee_username": "regular_user",
       "pull_request_user": "author_user",
       "source_branch": "feature/test",
       "target_branch": "main"
     }'
   
   # Verify assigned reviewer can see it
   curl -X GET http://localhost:8000/api/v1/reviews?reviewer=regular_user \
     -H "Authorization: Bearer $USER_TOKEN"
   ```

#### 3.2 Frontend Tests

**Manual Testing Checklist**:

- [ ] New user registration automatically gets reviewer role
- [ ] Regular user sees only their assigned reviews
- [ ] Review admin sees all reviews
- [ ] "Assign Review Task" button visible only to review admin
- [ ] Task assignment creates review successfully
- [ ] Assigned reviewer can see the new review
- [ ] Role management dialog works correctly
- [ ] Can assign/revoke roles in User Management
- [ ] Permission checks work correctly in UI

---

## 📊 Implementation Timeline

| Task | Estimated Time | Priority |
|------|---------------|----------|
| **Backend** | | |
| 1.1 Update review_admin permissions (migration) | 0.5h | P0 |
| 1.2 Auto-assign reviewer role on registration | 1h | P0 |
| 1.3 Review list API role-based filtering | 2h | P0 |
| 1.4 Task assignment API endpoint | 2h | P1 |
| **Frontend** | | |
| 2.1 UserManagementView role management | 3h | P1 |
| 2.2 ReviewListView task assignment UI | 3h | P1 |
| 2.3 API methods | 0.5h | P1 |
| **Testing** | | |
| Backend testing | 1h | P0 |
| Frontend testing | 1h | P0 |
| **Total** | **~14 hours** | |

---

## 🔧 Technical Considerations

### Security
- All endpoints require authentication
- Permission checks enforced at API level
- Audit logging for task assignments
- No sensitive data exposed in responses

### Performance
- Permission checks cached in Redis (future enhancement)
- Review filtering done at database level (efficient)
- No N+1 queries introduced

### Backward Compatibility
- Existing reviews unaffected
- Existing users need manual role assignment or re-registration
- API contracts maintained (only added new endpoint)

### Edge Cases
- User without linked Git account → empty review list
- Reviewer role missing from database → graceful degradation
- Role assignment failure → logged but registration continues

---

## 📝 Next Steps

After completing Phase 3.1:

1. **Phase 3.2** (Optional Enhancements):
   - Apply role-based filtering to other review endpoints
   - Implement proper role caching in frontend
   - Add batch task assignment
   - Enhanced permission composable with real-time role data

2. **Documentation Updates**:
   - Update API documentation with new endpoint
   - Update user guide with role management instructions
   - Add troubleshooting guide for common issues

3. **Deployment**:
   - Run database migration
   - Deploy backend changes
   - Deploy frontend changes
   - Verify in production environment

---

## ✅ Acceptance Criteria

- [ ] New users automatically receive reviewer role on registration
- [ ] Regular users can only view their assigned reviews
- [ ] Review admins can view all reviews
- [ ] Review admins can assign tasks to other reviewers
- [ ] System admins can manage user roles via UI
- [ ] All permission checks enforced at API level
- [ ] Audit logs created for task assignments
- [ ] UI shows/hides features based on user role
- [ ] All tests pass
- [ ] No breaking changes to existing functionality
