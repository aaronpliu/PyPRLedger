# Phase 3.2: User Role Delegation Implementation

## Overview

This document outlines the implementation plan and details for the User Role Delegation feature, which allows users with higher-level roles to delegate specific permissions to other users for a defined time period.

**Status**: ✅ Completed  
**Implementation Date**: April 12, 2026  
**Version**: Backend 1.6.0+

---

## Business Requirements

### Core Features

1. **Multi-Role Support** ✅
   - Users can have multiple roles simultaneously
   - Roles can be assigned at different resource scopes (global/project/repository)
   - Permissions are merged from all active roles

2. **Role Delegation** ✅
   - Senior users can delegate their role permissions to junior users
   - Delegation is temporary with configurable time range
   - Delegated permissions must be a subset of delegator's permissions

3. **Time-Bound Access** ✅
   - `starts_at`: When delegation becomes effective
   - `expires_at`: When delegation expires
   - Automatic status management (pending → active → expired)

4. **Audit Trail** ✅
   - Complete history of delegations (never deleted)
   - Track who delegated, to whom, when, and why
   - Record revocation details

### Business Rules

| Rule | Implementation | Status |
|------|----------------|--------|
| No cross-resource delegation | Validated in service layer | ✅ |
| No delegation chains (A→B→C) | Single-level only | ✅ |
| Preserve delegation history | Status-based lifecycle | ✅ |
| Permission subset validation | Strict subset check | ✅ |
| Time range validation | starts_at < expires_at | ✅ |
| Delegator must have role | Pre-validation check | ✅ |

---

## Technical Implementation

### Database Schema Changes

#### Migration: `009_add_delegation_support.py`

**New Fields in `user_role_assignment` table:**

```sql
-- Time range
starts_at DATETIME NULL COMMENT 'Start time for role validity'

-- Delegation flag
is_delegated BOOLEAN NOT NULL DEFAULT 0 COMMENT 'Whether this is delegated'

-- Delegation metadata
delegator_id INT NULL COMMENT 'User who delegated this role'
delegation_status ENUM('active','expired','revoked','pending') NULL
delegation_scope JSON NULL COMMENT 'Specific permissions delegated'
delegation_reason TEXT NULL COMMENT 'Reason for delegation'

-- Revocation tracking
revoked_by INT NULL COMMENT 'User who revoked'
revoked_at DATETIME NULL COMMENT 'When revoked'

-- Indexes
INDEX ix_user_role_delegator_id (delegator_id)
INDEX ix_user_role_starts_at (starts_at)
INDEX ix_user_role_delegation_status (delegation_status)
INDEX ix_user_role_is_delegated (is_delegated)
```

**Enum Type:**
```python
delegation_status_enum = ('active', 'expired', 'revoked', 'pending')
```

---

### Model Changes

**File**: `src/models/rbac.py`

```python
class UserRoleAssignment(Base):
    # ... existing fields ...
    
    # Time range
    starts_at: Mapped[datetime | None]
    expires_at: Mapped[datetime | None]  # already existed
    
    # Delegation fields
    is_delegated: Mapped[bool] = mapped_column(default=False)
    delegator_id: Mapped[int | None] = ForeignKey("auth_user.id")
    delegation_status: Mapped[str | None] = Enum(...)
    delegation_scope: Mapped[dict | None] = Column(JSON)
    delegation_reason: Mapped[str | None] = Column(Text)
    revoked_by: Mapped[int | None] = ForeignKey("auth_user.id")
    revoked_at: Mapped[datetime | None]
    
    # Relationships
    delegator: Mapped[AuthUser | None] = relationship(...)
    revoker: Mapped[AuthUser | None] = relationship(...)
```

---

### Service Layer

**File**: `src/services/rbac_service.py`

#### Key Methods

1. **`delegate_role()`** - Create delegation
   ```python
   async def delegate_role(
       delegator_id: int,
       delegatee_id: int,
       role_id: int,
       resource_type: str,
       resource_id: str | None,
       delegation_scope: dict,
       starts_at: datetime,
       expires_at: datetime,
       reason: str | None = None,
   ) -> UserRoleAssignment
   ```
   
   **Validations**:
   - Delegator has the role with same resource scope
   - delegation_scope ⊆ delegator's permissions
   - starts_at < expires_at
   - No duplicate active delegation

2. **`revoke_delegation()`** - Revoke delegation
   ```python
   async def revoke_delegation(
       assignment_id: int,
       revoked_by: int,
       reason: str | None = None,
   ) -> bool
   ```
   
   **Permissions**: Only delegator or admin can revoke

3. **`get_delegations()`** - Query delegations
   ```python
   async def get_delegations(
       delegator_id: int | None = None,
       delegatee_id: int | None = None,
       status: str | None = None,
       include_expired: bool = False,
   ) -> list[dict]
   ```

4. **`update_expired_delegations()`** - Batch update expired
   ```python
   async def update_expired_delegations() -> int
   ```
   
   **Usage**: Cron job or manual trigger

5. **Enhanced `check_permission()`** - Include delegated roles
   - Filters by time range (starts_at, expires_at)
   - Validates delegation status
   - Checks delegation_scope for specific actions

---

### API Endpoints

**File**: `src/api/v1/endpoints/delegation.py`

**Base Path**: `/api/v1/rbac/delegations`

#### 1. POST `/` - Create Delegation

**Request**:
```json
{
  "delegatee_id": 123,
  "role_id": 2,
  "resource_type": "global",
  "resource_id": null,
  "delegation_scope": {
    "reviews": ["read", "create"],
    "scores": ["read"]
  },
  "starts_at": "2026-04-12T00:00:00Z",
  "expires_at": "2026-05-12T23:59:59Z",
  "reason": "Temporary coverage during vacation"
}
```

**Permission**: `manage roles`

**Response**: `201 Created` with delegation details

---

#### 2. GET `/` - List Delegations

**Query Parameters**:
- `delegator_id`: Filter by delegator
- `delegatee_id`: Filter by delegatee
- `status`: active/expired/revoked/pending
- `include_expired`: true/false (default: false)

**Permission**: 
- Users can view their own delegations
- Admins can view all

**Response**: Array of delegation objects

---

#### 3. DELETE `/{assignment_id}` - Revoke Delegation

**Request Body** (optional):
```json
{
  "reason": "Project completed"
}
```

**Permission**: Delegator or admin

**Response**: Success message

---

#### 4. GET `/users/{user_id}` - User's Delegations

**Query Parameters**:
- `direction`: sent/received (default: received)
- `include_expired`: true/false

**Permission**: Own delegations or admin

**Response**: Array of delegations

---

#### 5. POST `/cleanup-expired` - Manual Cleanup

**Permission**: System admin only

**Response**:
```json
{
  "message": "Updated 5 expired delegations",
  "updated_count": 5
}
```

---

### Request/Response Schemas

**File**: `src/schemas/delegation.py`

```python
class DelegationCreate(BaseModel):
    delegatee_id: int
    role_id: int
    resource_type: str  # global/project/repository
    resource_id: str | None
    delegation_scope: dict
    starts_at: datetime
    expires_at: datetime
    reason: str | None

class DelegationResponse(BaseModel):
    id: int
    auth_user_id: int  # delegatee
    role_id: int
    role_name: str | None
    resource_type: str
    resource_id: str | None
    granted_by: int | None
    delegator_id: int | None
    is_delegated: bool
    delegation_status: str | None
    delegation_scope: dict | None
    delegation_reason: str | None
    starts_at: str | None
    expires_at: str | None
    revoked_by: int | None
    revoked_at: str | None
    created_at: str

class DelegationRevoke(BaseModel):
    reason: str | None

class DelegationListQuery(BaseModel):
    delegator_id: int | None
    delegatee_id: int | None
    status: str | None
    include_expired: bool = False
```

---

## Testing

### Unit Tests

**File**: `tests/test_delegation.py`

**Test Cases** (9 total):

1. ✅ `test_create_delegation_success` - Basic delegation flow
2. ✅ `test_delegation_permission_subset_validation` - Subset check
3. ✅ `test_delegation_time_range_validation` - Time validation
4. ✅ `test_delegation_requires_delegator_has_role` - Role ownership
5. ✅ `test_revoke_delegation` - Revocation flow
6. ✅ `test_get_delegations_filter` - Query filtering
7. ✅ `test_update_expired_delegations` - Expiration handling
8. ✅ `test_delegation_pending_status` - Future start time
9. ✅ `test_prevent_duplicate_active_delegation` - Duplicate prevention

**Run Tests**:
```bash
pytest tests/test_delegation.py -v
```

---

## Deployment

### Prerequisites

1. Database backup (recommended)
2. Stop application service
3. Ensure Alembic is configured

### Migration Steps

```bash
# 1. Navigate to project root
cd /path/to/PyPRLedger

# 2. Run migration
alembic upgrade head

# 3. Verify migration
alembic current
# Should show: 009 (head)

# 4. Restart application
uv run uvicorn src.main:app --reload
```

### Rollback Plan

```bash
# Rollback to previous version
alembic downgrade 008
```

---

## Usage Examples

### Example 1: Admin Delegates Reviewer Role

```bash
# Admin (user_id=1) delegates reviewer permissions to junior (user_id=5)
curl -X POST http://localhost:8000/api/v1/rbac/delegations \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "delegatee_id": 5,
    "role_id": 2,
    "resource_type": "global",
    "resource_id": null,
    "delegation_scope": {
      "reviews": ["read", "create"],
      "scores": ["read", "create"]
    },
    "starts_at": "2026-04-12T00:00:00Z",
    "expires_at": "2026-05-12T23:59:59Z",
    "reason": "Covering while team member on leave"
  }'
```

### Example 2: View My Received Delegations

```bash
curl http://localhost:8000/api/v1/rbac/users/5/delegations?direction=received \
  -H "Authorization: Bearer USER_5_TOKEN"
```

### Example 3: Revoke Delegation

```bash
curl -X DELETE http://localhost:8000/api/v1/rbac/delegations/123 \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Team member returned from leave"}'
```

---

## Security Considerations

### Permission Validation

1. **Delegator Authorization**
   - Must have `manage roles` permission
   - Must own the role being delegated
   - Can only delegate their own permissions

2. **Permission Subset**
   - Strict validation: requested ⊆ available
   - Prevents privilege escalation
   - Checked at creation time

3. **Revocation Rights**
   - Only delegator or admin can revoke
   - Audit trail maintained

### Data Protection

1. **No Cascading Deletion**
   - Delegations preserved for audit
   - Status-based lifecycle management

2. **Foreign Key Constraints**
   - `ON DELETE SET NULL` for delegator/revoker
   - Prevents orphaned records

3. **Index Optimization**
   - Queries optimized for common filters
   - Prevents performance degradation

---

## Future Enhancements

### TODO Items

1. **Email Notifications** 📧
   - Notify delegatee when delegation created
   - Notify when delegation revoked
   - Reminder before expiration (e.g., 3 days prior)
   - Integration with third-party email service (SendGrid/AWS SES)

2. **In-Site Messages** 💬
   - Build message/notification module
   - Real-time notifications via WebSocket
   - Message inbox in user profile

3. **Frontend UI** 🖥️
   - Delegation management page
   - Create delegation form with date picker
   - Delegation list with filters
   - Revoke confirmation dialog
   - Estimated effort: 2-3 days

4. **Scheduled Tasks** ⏰
   - Automated cleanup of expired delegations
   - Celery beat or cron job
   - Daily execution recommended

5. **Analytics & Reporting** 📊
   - Delegation statistics dashboard
   - Active delegations count
   - Most common delegation patterns
   - Compliance reporting

6. **Advanced Features**
   - Delegation templates (pre-defined scopes)
   - Bulk delegation operations
   - Delegation approval workflow
   - Delegation conflict detection

---

## Troubleshooting

### Common Issues

#### Issue 1: Migration Fails with "Duplicate Column"

**Cause**: Partial migration left columns in database

**Solution**:
```python
# Run cleanup script
python cleanup_migration.py
# Then retry migration
alembic upgrade head
```

#### Issue 2: "Invalid Default Value for Boolean"

**Cause**: MySQL uses 0/1, not true/false

**Solution**: Use `server_default="0"` instead of `"false"`

#### Issue 3: "Cannot Import get_current_user"

**Cause**: Wrong import path

**Solution**: Use `from src.core.permissions import get_current_user_with_token`

---

## Monitoring & Maintenance

### Health Checks

1. **Active Delegations Count**
   ```sql
   SELECT COUNT(*) FROM user_role_assignment 
   WHERE is_delegated = 1 AND delegation_status = 'active';
   ```

2. **Expiring Soon** (next 7 days)
   ```sql
   SELECT * FROM user_role_assignment 
   WHERE delegation_status = 'active' 
   AND expires_at BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 7 DAY);
   ```

3. **Expired But Not Updated**
   ```sql
   SELECT COUNT(*) FROM user_role_assignment 
   WHERE delegation_status = 'active' 
   AND expires_at < NOW();
   ```

### Regular Maintenance

- **Weekly**: Review active delegations
- **Monthly**: Clean up old expired delegations (archive if needed)
- **Quarterly**: Audit delegation patterns and usage

---

## References

- **RBAC Documentation**: See `docs/features/phase1_auth_rbac_audit.md`
- **API Documentation**: `http://localhost:8000/api/docs`
- **Database Schema**: `src/models/rbac.py`
- **Migration Script**: `alembic/versions/009_add_delegation_support.py`

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-12 | Initial implementation completed |
| | | - Database migration (009) |
| | | - Service layer methods |
| | | - API endpoints (5) |
| | | - Unit tests (9 cases) |
| | | - Full MySQL compatibility |

---

**Last Updated**: April 12, 2026  
**Maintained By**: Development Team  
**Status**: ✅ Production Ready
