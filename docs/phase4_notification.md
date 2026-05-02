# Phase 4: Notification System Implementation Plan

## Overview
This document outlines the implementation plan for building a comprehensive notification system for PyPRLedger, enabling real-time alerts for review assignments, status changes, and system events.

## Objectives
1. Enable automatic notifications when reviewers are assigned to PR reviews
2. Notify users of review status changes (pending → in_progress → completed)
3. Support multiple notification channels (in-app, email, optional Slack/Teams)
4. Provide user-configurable notification preferences
5. Maintain notification history with read/unread status tracking

## Architecture Design

### 1. Database Schema

#### Notification Table
```sql
CREATE TABLE notification (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES user(username),
    type VARCHAR(50) NOT NULL, -- 'review_assigned', 'review_completed', 'review_expired', etc.
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    related_id VARCHAR(100), -- pull_request_id or other related entity ID
    related_type VARCHAR(50), -- 'pull_request', 'delegation', etc.
    is_read BOOLEAN DEFAULT FALSE,
    priority VARCHAR(20) DEFAULT 'normal', -- 'low', 'normal', 'high', 'urgent'
    channel VARCHAR(50) DEFAULT 'in_app', -- 'in_app', 'email', 'slack'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    read_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE, -- Auto-cleanup after X days
    
    INDEX idx_notification_user (user_id, is_read),
    INDEX idx_notification_created (created_at DESC),
    INDEX idx_notification_type (type)
);
```

#### Notification Preferences Table
```sql
CREATE TABLE notification_preference (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES user(username),
    notification_type VARCHAR(50) NOT NULL, -- 'review_assigned', 'review_completed', etc.
    channel_enabled BOOLEAN DEFAULT TRUE,
    email_enabled BOOLEAN DEFAULT TRUE,
    in_app_enabled BOOLEAN DEFAULT TRUE,
    slack_enabled BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, notification_type)
);
```

### 2. Backend Implementation

#### Models (`src/models/notification.py`)
- `Notification` model with all fields from schema
- `NotificationPreference` model for user settings
- Helper methods: `mark_as_read()`, `mark_all_as_read()`, `get_unread_count()`

#### Schemas (`src/schemas/notification.py`)
- `NotificationCreate`: For creating new notifications
- `NotificationResponse`: Full notification data with user info
- `NotificationListResponse`: Paginated list response
- `NotificationPreferenceUpdate`: For updating user preferences
- `NotificationStats`: Unread count, breakdown by type

#### Service Layer (`src/services/notification_service.py`)
Key methods:
- `create_notification()`: Create and dispatch notification
- `get_user_notifications()`: Get paginated notifications with filters
- `mark_as_read()`: Mark single notification as read
- `mark_all_as_read()`: Bulk mark as read
- `delete_notification()`: Soft delete notification
- `get_unread_count()`: Get count of unread notifications
- `update_preferences()`: Update user notification preferences
- `get_preferences()`: Get user's current preferences
- `dispatch_notification()`: Route notification to appropriate channels

#### Notification Channels
- **InAppChannel**: Store in database, push via WebSocket
- **EmailChannel**: Send via SMTP/SendGrid
- **SlackChannel** (optional): Post to Slack webhook
- **TeamsChannel** (optional): Post to Teams webhook

#### Background Tasks
- `cleanup_expired_notifications()`: Remove notifications older than 30 days
- `send_digest_email()`: Daily/weekly digest for inactive users

### 3. API Endpoints (`src/api/v1/endpoints/notifications.py`)

```python
# GET /api/v1/notifications - List user's notifications (paginated)
# GET /api/v1/notifications/unread-count - Get unread count
# GET /api/v1/notifications/{id} - Get single notification
# POST /api/v1/notifications/{id}/read - Mark as read
# POST /api/v1/notifications/read-all - Mark all as read
# DELETE /api/v1/notifications/{id} - Delete notification
# GET /api/v1/notifications/preferences - Get user preferences
# PUT /api/v1/notifications/preferences - Update preferences
# POST /api/v1/notifications/test - Send test notification (admin only)
```

### 4. Integration Points

#### Review Assignment Trigger
In `ReviewScoreService.assign_reviewer()`:
```python
# After successful assignment
await notification_service.create_notification(
    user_id=reviewer_username,
    type='review_assigned',
    title=f'New Review Assigned: {pr_id}',
    message=f'You have been assigned to review PR #{pr_id} in {project_key}/{repository_slug}',
    related_id=pull_request_id,
    related_type='pull_request',
    priority='high'
)
```

#### Review Completion Trigger
When reviewer submits score:
```python
await notification_service.create_notification(
    user_id=pr_author,
    type='review_completed',
    title=f'Review Completed: {pr_id}',
    message=f'{reviewer} has completed their review of PR #{pr_id}',
    related_id=pull_request_id,
    related_type='pull_request',
    priority='normal'
)
```

#### Delegation Expiry Warning
In background task (7 days before expiry):
```python
await notification_service.create_notification(
    user_id=delegate_username,
    type='delegation_expiring',
    title='Role Delegation Expiring Soon',
    message=f'Your delegated role will expire in 7 days',
    related_id=str(delegation_id),
    related_type='delegation',
    priority='normal'
)
```

### 5. Frontend Implementation

#### API Client (`frontend/src/api/notifications.ts`)
```typescript
export interface Notification {
  id: number
  user_id: string
  type: string
  title: string
  message: string
  related_id?: string
  related_type?: string
  is_read: boolean
  priority: 'low' | 'normal' | 'high' | 'urgent'
  channel: string
  created_at: string
  read_at?: string
}

export interface NotificationPreference {
  notification_type: string
  channel_enabled: boolean
  email_enabled: boolean
  in_app_enabled: boolean
  slack_enabled: boolean
}

// API methods
export function getNotifications(params: PaginationParams)
export function getUnreadCount()
export function markAsRead(id: number)
export function markAllAsRead()
export function deleteNotification(id: number)
export function getPreferences()
export function updatePreferences(prefs: NotificationPreference[])
```

#### Components

**NotificationBell.vue** (Header component)
- Display unread count badge
- Dropdown menu showing recent notifications
- Quick actions: "Mark all as read", "View all"
- Real-time updates via WebSocket (Phase 5)

**NotificationListView.vue** (Dedicated page)
- Full notification history with filters
- Filter by: type, read status, date range, priority
- Actions per notification: Mark as read, Delete, Navigate to related content
- Bulk actions: Mark selected as read, Delete selected
- Infinite scroll or pagination

**NotificationPreferenceView.vue** (Settings page)
- Toggle switches for each notification type
- Channel selection checkboxes (in-app, email, slack)
- Test notification button
- Save/Cancel actions

#### Routes
```typescript
{
  path: '/notifications',
  name: 'Notifications',
  component: () => import('@/views/notifications/NotificationListView.vue'),
  meta: { requiresAuth: true }
},
{
  path: '/settings/notifications',
  name: 'NotificationPreferences',
  component: () => import('@/views/settings/NotificationPreferenceView.vue'),
  meta: { requiresAuth: true }
}
```

### 6. WebSocket Integration (Phase 5 Preparation)
- Setup WebSocket connection in `main.ts`
- Listen for `notification:new` events
- Update unread count badge in real-time
- Show toast notification for high-priority items

## Implementation Phases

### Phase 4.1: Core Infrastructure (Week 1)
- [ ] Create database migrations for notification tables
- [ ] Implement Notification and NotificationPreference models
- [ ] Create Pydantic schemas
- [ ] Build NotificationService with basic CRUD operations
- [ ] Add unit tests for service layer

### Phase 4.2: API & Integration (Week 2)
- [ ] Create notification API endpoints
- [ ] Integrate with review assignment flow
- [ ] Integrate with review completion flow
- [ ] Add delegation expiry warnings
- [ ] Write API integration tests

### Phase 4.3: Frontend UI (Week 3)
- [ ] Build NotificationBell component
- [ ] Create NotificationListView page
- [ ] Build NotificationPreferenceView page
- [ ] Add API client methods
- [ ] Implement routing and navigation
- [ ] Add i18n translations

### Phase 4.4: Email & Advanced Features (Week 4)
- [ ] Implement EmailChannel with SMTP configuration
- [ ] Add notification preference enforcement
- [ ] Create background cleanup task
- [ ] Add notification stats/analytics endpoint
- [ ] Performance testing and optimization

### Phase 4.5: Testing & Polish (Week 5)
- [ ] End-to-end testing
- [ ] Load testing for notification delivery
- [ ] UI/UX refinements based on feedback
- [ ] Documentation updates
- [ ] Deploy to staging environment

## Configuration

### Environment Variables
```env
# Notification Settings
NOTIFICATION_RETENTION_DAYS=30
NOTIFICATION_DIGEST_ENABLED=true
NOTIFICATION_DIGEST_FREQUENCY=daily  # daily, weekly

# Email Configuration
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=notifications@example.com
SMTP_PASSWORD=***
EMAIL_FROM=noreply@example.com
EMAIL_FROM_NAME=PyPRLedger Notifications

# Slack Integration (Optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_ENABLED=false
```

### Default Preferences
```python
DEFAULT_PREFERENCES = {
    'review_assigned': {
        'in_app_enabled': True,
        'email_enabled': True,
        'slack_enabled': False
    },
    'review_completed': {
        'in_app_enabled': True,
        'email_enabled': False,
        'slack_enabled': False
    },
    'delegation_expiring': {
        'in_app_enabled': True,
        'email_enabled': True,
        'slack_enabled': False
    }
}
```

## Security Considerations
1. **Authorization**: Users can only access their own notifications
2. **Rate Limiting**: Prevent notification spam (max 100/day per user)
3. **Data Privacy**: Never expose other users' notification data
4. **XSS Prevention**: Sanitize notification messages before display
5. **CSRF Protection**: All mutation endpoints require CSRF tokens

## Performance Targets
- Notification creation: < 100ms (async, non-blocking)
- Notification list load: < 500ms for first page
- Unread count query: < 50ms (indexed)
- Email delivery: < 5 seconds (async queue)
- Database cleanup: Run daily at 2 AM, process < 1000 records/batch

## Monitoring & Observability
- Track notification delivery success rate
- Monitor email bounce rates
- Alert on notification queue backlog > 1000
- Log all notification dispatch attempts
- Dashboard metrics: notifications sent/day, read rate, channel distribution

## Future Enhancements (Post-Phase 4)
1. **Real-time WebSocket** push notifications (Phase 5)
2. **Mobile push** notifications (iOS/Android)
3. **Notification templates** with dynamic content
4. **Batch notifications** for digest emails
5. **Advanced filtering** and search capabilities
6. **Notification analytics** dashboard for admins
7. **Slack/Teams bot** integration for team notifications

## Success Metrics
- 95%+ notification delivery success rate
- < 2% email bounce rate
- Average time to read: < 24 hours for high-priority
- User satisfaction score: > 4.0/5.0 for notification system
- Reduction in missed review assignments: > 80%

## Dependencies
- SQLAlchemy ORM for database operations
- FastAPI for REST API
- Vue 3 + Element Plus for UI
- SMTP server or SendGrid for email
- Redis for async task queue (optional)
- pytest for testing

## Risk Mitigation
1. **Email delivery failures**: Implement retry logic with exponential backoff
2. **Database performance**: Add proper indexes, implement pagination limits
3. **Notification spam**: Enforce rate limits and user preferences strictly
4. **WebSocket complexity**: Defer to Phase 5, use polling initially
5. **Third-party integrations**: Make Slack/Teams optional, fallback gracefully

---

**Document Version**: 1.0  
**Last Updated**: 2026-04-27  
**Status**: Planning  
**Owner**: Development Team
