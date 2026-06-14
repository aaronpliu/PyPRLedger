# PRLedger

A production-ready FastAPI + Vue 3 PR Code Review Result Storage System with MySQL, Redis, and Prometheus integration.

## Features

- **RESTful API**: Complete REST API for managing pull request reviews, users, projects, and auto-assignment rules
- **Auto-Assignment Rules**: Configurable rules to automatically assign reviewers based on project, repository, branch, PR author, and status conditions — with priority ordering, date ranges, and enable/disable toggling
- **Multi-Reviewer System**: Support for multiple reviewers per pull request, each with independent assignments, status tracking (pending → in_progress → completed), and scoring
- **Review Scores**: File-level and PR-level scoring with configurable 0-10 scale, auto-filled descriptions, and soft-delete support
- **Role-Based Access Control** (RBAC): Hierarchical roles (viewer, reviewer, review_admin, system_admin) with resource-scoped permissions (global, project, repository) and time-limited delegation
- **Multi-Project Management**: Virtual `app_name` architecture for organizing projects into logical applications via a project registry system
- **Review Associations**: Bidirectional linking between reviews for tracking related/follow-up PRs
- **Review Pinning**: Per-user private pin/flag for marking noteworthy reviews
- **Notifications**: In-app notification system with preference management and real-time SSE (Server-Sent Events) streaming
- **Personal Access Tokens**: Token-based API authentication with expiration and scoping
- **Export**: Export review data to PDF, Excel, CSV, or JSON with `page_size=0` sentinel for full dataset export
- **Frontend**: Vue 3 + Element Plus SPA with review listing, detail views, task assignment management, analytics dashboards, and rule management UI
- **Database Integration**: MySQL database with SQLAlchemy ORM and Alembic migrations
- **Caching Layer**: Redis integration for improved performance
- **Monitoring**: Prometheus metrics collection with Grafana dashboards
- **Async Operations**: Full async/await support for high concurrency
- **Docker Support**: Complete Docker Compose setup for easy deployment
- **AI-Assisted Development**: OpenSpec spec-driven development workflow with Codegraph codebase graph engine and OpenCode agent orchestration

## Project Structure

```
PyPRLedger/
├── alembic/                      # Database migrations
│   ├── versions/                 # Migration scripts (027 total)
│   └── env.py                    # Alembic environment
├── docs/                         # Documentation
├── frontend/                     # Vue 3 + Element Plus SPA
│   └── src/
│       ├── api/                  # API client modules (reviews, users, projects, etc.)
│       ├── components/           # Reusable Vue components
│       ├── layouts/              # Layout components (Default, Admin)
│       ├── locales/              # i18n translations (en, zh-CN, zh-TW)
│       ├── router/               # Vue Router configuration
│       ├── stores/               # Pinia stores
│       ├── utils/export/         # Export utilities (PDF, Excel, CSV, JSON)
│       └── views/                # Page views (reviews, scores, admin, auth, dashboard)
├── grafana/                      # Grafana configuration
├── logs/                         # Application logs
├── openspec/                     # OpenSpec spec-driven development artifacts
│   ├── changes/archive/          # Archived changes
│   ├── config.yaml               # OpenSpec configuration
│   └── specs/                    # Main specification files by capability
├── scripts/                      # Utility scripts
│   ├── release/                  # Release automation scripts
│   ├── bump_version.py           # Version management
│   └── validate_commit_msg.py    # Commit message validation
├── src/                          # Application source code
│   ├── api/v1/endpoints/         # API endpoint handlers
│   │   ├── audit.py              # Audit log export
│   │   ├── auth.py               # Authentication
│   │   ├── auto_task_assignment.py  # Auto-assignment rule CRUD (NEW v1.17.0)
│   │   ├── delegation.py         # Role delegation
│   │   ├── notifications.py      # Notification management
│   │   ├── personal_access_tokens.py  # PAT management
│   │   ├── project_registry.py   # Project registry
│   │   ├── projects.py           # Project endpoints
│   │   ├── rbac.py               # Role management
│   │   ├── reviews.py            # Review CRUD, scores, trends, export
│   │   ├── search.py             # Global search
│   │   ├── sse.py                # SSE streaming
│   │   ├── task_assignment.py    # Manual task assignment
│   │   └── users.py              # User endpoints (git + auth)
│   ├── core/                     # Core functionality
│   │   ├── config.py             # Application configuration
│   │   ├── database.py           # Database configuration
│   │   ├── exceptions.py         # Custom exception hierarchy
│   │   ├── middleware.py         # Custom middleware
│   │   └── permissions.py        # Auth + permission dependencies
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── audit_log.py          # Audit trail
│   │   ├── auth_user.py          # System login users
│   │   ├── auto_assign_rule.py   # Auto-assignment rules (NEW v1.17.0)
│   │   ├── notification.py       # Notifications + preferences
│   │   ├── organization.py       # Organization groups
│   │   ├── personal_access_token.py  # API tokens
│   │   ├── project.py            # Projects
│   │   ├── project_registry.py   # Project-to-app mappings
│   │   ├── pull_request.py       # Reviews, assignments, scores, raw records, pins, associations
│   │   ├── rbac.py               # User role assignments
│   │   ├── repository.py         # Repositories
│   │   ├── role.py               # Roles with JSON permissions
│   │   ├── system_setting.py     # System settings
│   │   └── user.py               # Git users
│   ├── schemas/                  # Pydantic v2 schemas
│   │   ├── audit.py              # Audit log schemas
│   │   ├── auth.py               # Auth schemas
│   │   ├── auto_assign_rule.py   # Auto-assignment rule schemas (NEW v1.17.0)
│   │   ├── delegation.py         # Delegation schemas
│   │   ├── notification.py       # Notification schemas
│   │   ├── personal_access_token.py  # PAT schemas
│   │   ├── project.py            # Project schemas
│   │   ├── pull_request.py       # Review + score schemas
│   │   ├── rbac.py               # Role schemas
│   │   ├── repository.py         # Repository schemas
│   │   ├── review.py             # Multi-reviewer response schemas
│   │   └── user.py               # User schemas
│   ├── services/                 # Business logic layer
│   │   ├── audit_service.py      # Audit service
│   │   ├── auth_service.py       # Authentication service
│   │   ├── auto_assign_service.py    # Auto-assignment engine (NEW v1.17.0)
│   │   ├── avatar_service.py     # Avatar upload
│   │   ├── bitbucket_service.py  # Bitbucket API integration
│   │   ├── entity_sync_service.py    # Auto-sync entities from Bitbucket
│   │   ├── multi_reviewer_service.py # Multi-reviewer assignment + notifications
│   │   ├── notification_service.py   # Notification dispatch
│   │   ├── pat_service.py        # Personal access token service
│   │   ├── project_registry_service.py  # Registry management
│   │   ├── project_service.py    # Project service
│   │   ├── rbac_service.py       # RBAC permission checking
│   │   ├── review_score_service.py    # Score management
│   │   ├── review_service.py     # Core review CRUD + listing
│   │   ├── review_validation_service.py  # Raw review validation
│   │   └── user_service.py       # User service
│   ├── utils/                    # Utilities
│   │   ├── ai_review_utils.py    # AI review ID generation
│   │   ├── log.py                # Structured logging
│   │   ├── metrics.py            # Prometheus metrics collector
│   │   ├── password.py           # Password hashing
│   │   ├── redis.py              # Redis cache client
│   │   ├── score_utils.py        # Score normalization
│   │   └── timezone.py           # Timezone utilities
│   └── main.py                   # FastAPI app factory with lifespan
├── tests/                        # Test suite
│   ├── conftest.py               # Pytest fixtures
│   ├── test_auto_assign_service.py   # Auto-assignment tests (NEW)
│   ├── test_delegation.py        # Delegation tests
│   ├── test_notification_service.py  # Notification tests
│   ├── test_review_visibility.py     # Review visibility tests
│   └── test_sse.py               # SSE tests
├── .env.example
├── .openspec.yaml                # OpenSpec CLI configuration
├── AGENTS.md                     # Agent guidelines for AI development
├── docker-compose.yml
├── Dockerfile
├── opencode.json                 # OpenCode agent configuration
├── prometheus.yml
├── pyproject.toml
├── pytest.ini
└── ruff.toml
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)

### Using Docker Compose (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd PRLedger
```

2. Copy environment variables:
```bash
cp .env.example .env
```

3. Update environment variables in `.env` file

4. Start all services:
```bash
docker-compose up -d
```

5. Access the application:
- API: http://localhost:8000
- API Documentation: http://localhost:8000/api/docs
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090


## 💻 Local Development Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd PRLedger
```

### 2. Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 3. Create Virtual Environment

```bash
uv venv
```

### 4. Activate Virtual Environment

```bash
source .venv/bin/activate  # On macOS/Linux
# Or on Windows:
# .venv\Scripts\activate
```

### 5. Install Dependencies

```bash
uv sync --all-extras
```

### 6. Configure Environment

```bash
cp .env.example .env
# Edit .env file with your configuration
```

### 7. Setup Database

If using MySQL locally:

```bash
mysql -u root -p
CREATE DATABASE code_review CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

### 8. Run Migrations

```bash
alembic upgrade head
```

### 9. Start Application

```bash
# Development mode with auto-reload
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 10. Access Application

- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/api/docs
- **Metrics**: http://localhost:8000/api/metrics

## API Endpoints

### Reviews (`/api/v1/reviews`)

- `POST /api/v1/reviews` - Create or update a review (upsert, with auto-assignment if no reviewer specified)
- `GET /api/v1/reviews` - List reviews with filters (`page_size=0` returns all matching records)
- `GET /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}` - Get reviews by composite key
- `PUT /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}` - Update review
- `PATCH /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}/status` - Update status
- `DELETE /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}` - Soft delete review
- `POST /api/v1/reviews/{id}/pin` / `DELETE /api/v1/reviews/{id}/pin` - Pin/unpin a review
- `POST /api/v1/reviews/{id}/associate/{target_id}` / `DELETE /...` - Link/unlink reviews
- `GET /api/v1/reviews/statistics` - Get review statistics
- `GET /api/v1/reviews/project/{project_key}` - Get reviews by project
- `GET /api/v1/reviews/reviewer/{username}` - Get reviews by reviewer
- `GET /api/v1/reviews/trends/reviewer-activity` - Reviewer activity trends
- `GET /api/v1/reviews/trends/score-trends` - Score trends
- `PUT /api/v1/reviews/score` - Upsert a review score
- `DELETE /api/v1/reviews/score/{reviewer}` - Delete a score

### Auto-Assignment Rules (`/api/v1/auto-task-assignment/rules`) — review_admin only

- `POST /api/v1/auto-task-assignment/rules` — Create a rule
- `GET /api/v1/auto-task-assignment/rules` — List rules by priority
- `GET /api/v1/auto-task-assignment/rules/{id}` — Get a rule
- `PUT /api/v1/auto-task-assignment/rules/{id}` — Update a rule
- `DELETE /api/v1/auto-task-assignment/rules/{id}` — Delete a rule
- `PATCH /api/v1/auto-task-assignment/rules/{id}/toggle` — Enable/disable a rule

### Task Assignment (`/api/v1/task-assignment`) — review_admin only

- `GET /api/v1/task-assignment/` — List reviews with assignments
- `GET /api/v1/task-assignment/{id}` — Get review with assignments
- `POST /api/v1/task-assignment/{id}/assign` — Assign a reviewer
- `DELETE /api/v1/task-assignment/{id}/assign/{reviewer}` — Remove reviewer
- `PATCH /api/v1/task-assignment/assignments/{id}/status` — Update assignment status

### RBAC & Delegation (`/api/v1/`)

- `GET/POST /api/v1/roles` — List/create roles
- `GET/PUT/DELETE /api/v1/roles/{id}` — Get/update/delete role
- `POST /api/v1/users/{id}/roles` — Assign role to user
- `DELETE /api/v1/users/{id}/roles/{role_id}` — Revoke role
- `GET /api/v1/users/{id}/roles` — Get user's role assignments
- `POST /api/v1/rbac/delegations` — Delegate a role
- `PATCH /api/v1/rbac/delegations/{id}/revoke` — Revoke a delegation

### Users (`/api/v1/users/git`)

- `POST /api/v1/users/git/` — Create a git user
- `GET /api/v1/users/git/` — List git users
- `GET /api/v1/users/git/{id}` — Get git user by ID
- `PUT /api/v1/users/git/{id}` — Update git user
- `DELETE /api/v1/users/git/{id}` — Delete git user (preserves reviews via FK SET NULL)
- `GET /api/v1/users/git/reviewers` — List active reviewers
- `PATCH /api/v1/users/git/{id}/toggle-reviewer` — Toggle reviewer status

### Auth Users (`/api/v1/users/auth`)

- `GET /api/v1/users/auth/` — List auth users
- `POST /api/v1/users/auth/register` — Register new auth user
- `POST /api/v1/users/auth/login` — Login
- `POST /api/v1/users/auth/refresh` — Refresh token
- `DELETE /api/v1/users/auth/{id}` — Delete auth user (cascades roles, audit, PATs)
- `PATCH /api/v1/users/auth/{id}/activate` / `/deactivate` — Activate/deactivate
- `POST /api/v1/users/auth/{username}/avatar` / `DELETE` — Avatar management

### Projects (`/api/v1/projects`)

- `POST /api/v1/projects` — Create a project
- `GET /api/v1/projects` — List projects
- `GET /api/v1/projects/all` — Get all projects (unpaginated, for dropdowns)
- `GET /api/v1/projects/key/{project_key}` — Get project by key
- `GET /api/v1/projects/key/{project_key}/repositories` — List repos for a project
- `PUT /api/v1/projects/{id}` — Update project
- `DELETE /api/v1/projects/{id}` — Delete project
- `GET /api/v1/projects/statistics` — Project statistics

### Project Registry (`/api/v1/`)

- `GET /api/v1/apps` — List all registered applications
- `GET /api/v1/apps/{app_name}/projects` — List projects in an app
- `POST /api/v1/admin/registry/register` — Register project-repo to an app
- `PUT /api/v1/admin/registry/update` — Move project-repo to different app
- `DELETE /api/v1/admin/registry/unregister` — Remove from registry

### Notifications (`/api/v1/notifications`)

- `GET /api/v1/notifications/` — List notifications for current user
- `PATCH /api/v1/notifications/{id}/read` — Mark as read
- `POST /api/v1/notifications/read-all` — Mark all as read
- `GET /api/v1/notifications/preferences` — Get notification preferences
- `PUT /api/v1/notifications/preferences` — Update preferences

### Personal Access Tokens (`/api/v1/pat`)

- `POST /api/v1/pat/create` — Create a new PAT
- `GET /api/v1/pat/` — List user's PATs
- `DELETE /api/v1/pat/{id}` — Revoke a PAT

### Search & SSE

- `GET /api/v1/search?q={query}` — Global search across reviews, scores, and users
- `GET /api/v1/sse/stream` — SSE stream for real-time review notifications

### Audit

- `GET /api/v1/audit/logs` — Query audit logs (paginated, filterable)
- `GET /api/v1/audit/export` — Export audit logs to CSV

## Frontend

A Vue 3 + Element Plus SPA is available in `frontend/`.

### Running the Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` and proxies API requests to `http://localhost:8000`.

### Frontend Pages

| Route | Page | Access |
|---|---|---|
| `/` | Dashboard with trend charts and recent reviews | Authenticated users |
| `/reviews` | Review list with filtering, export, pinning | Authenticated users |
| `/reviews/:id` | Review detail with code diff, AI review, scores | Authenticated users |
| `/task-assignment` | Task assignment management | review_admin |
| `/task-assignment/rules` | Auto-assignment rule management | review_admin |
| `/task-assignment/analytics` | Assignment analytics dashboard | review_admin |
| `/scores` | Score list with filters | Authenticated users |
| `/scores/analytics` | Score analytics dashboard | Authenticated users |
| `/notifications` | Notification list and preferences | Authenticated users |
| `/profile` | User profile | Authenticated users |
| `/myadmin/*` | System administration panel | system_admin |

## Configuration

### Environment Variables

See `.env.example` for all available environment variables.

Key configuration options:
- `DATABASE_*`: MySQL database configuration
- `REDIS_*`: Redis cache configuration
- `TIMEZONE`: Application timezone (default: Asia/Shanghai)
- `USE_UTC_IN_DB`: Store datetime in UTC in database (default: True, recommended)
- `PROMETHEUS_ENABLED`: Enable/disable Prometheus metrics
- `RATE_LIMIT_*`: Rate limiting configuration
- `CACHE_TTL_*`: Cache TTL settings

### Timezone Configuration

The application supports configurable timezones:
- **Database Storage**: By default, all datetime values are stored in UTC (`USE_UTC_IN_DB=True`)
- **Application Display**: Datetime values are converted to the configured timezone (`TIMEZONE=Asia/Shanghai`)
- **MySQL Configuration**: When using Docker, MySQL is configured with `--default-time-zone='+08:00'`

This ensures consistent datetime handling across different deployment environments while allowing users to view times in their local timezone.

## Database

The system uses MySQL with the following tables:

| Table | Purpose |
|---|---|
| `user` | Git/Bitbucket users |
| `auth_user` | System login users with password auth |
| `project` | Code review projects |
| `repository` | Code repositories per project |
| `pull_request_review_base` | Pull request review records |
| `pull_request_review_assignment` | Reviewer assignments with status tracking |
| `pull_request_score` | Review scores (file-level and PR-level) |
| `pull_request_review_raw` | Raw incoming review payloads (validation audit) |
| `pull_request_review_association` | Bidirectional review linking |
| `user_pinned_reviews` | Per-user review pinning |
| `pull_request_review_auto_assignment_rule` | Auto-assignment rule definitions |
| `project_registry` | Project-to-application mappings |
| `role` | RBAC roles with JSON permissions |
| `user_role_assignment` | User-to-role assignments (global/project/repository scope) |
| `notification` | In-app notifications |
| `notification_preference` | Per-user notification channel preferences |
| `personal_access_token` | API authentication tokens |
| `audit_log` | Audit trail for operations |
| `system_settings` | Key-value system configuration |
| `organization_group` | Organization hierarchy (groups/teams) |

### Running Migrations

```bash
alembic upgrade head
```

### Creating a New Migration

```bash
alembic revision --autogenerate -m "description"
```

## Monitoring

### Prometheus Metrics

The system exposes the following metrics:
- HTTP request metrics
- Review metrics
- User metrics
- Project metrics
- Cache metrics
- Database metrics
- System metrics

Access metrics at: `http://localhost:8000/metrics`

### Grafana Dashboards

Grafana is pre-configured with:
- Prometheus data source
- Code review dashboard

Access Grafana at: `http://localhost:3000` (admin/admin)

## AI-Assisted Development

This project uses **OpenSpec** + **Codegraph** + **OpenCode** for AI-assisted development:

- **OpenSpec**: Spec-driven development with structured change artifacts (proposal → design → specs → tasks)
- **Codegraph**: Semantic codebase graph engine for AI context awareness
- **OpenCode**: Agent orchestration platform with specialized agents (coordinator, sde, qa, devops, etc.)

Workflow commands (via OpenCode):
- `/opsx-explore` — Investigate problems and explore ideas
- `/opsx-propose` — Create a change proposal with all artifacts
- `/opsx-apply` — Implement tasks from a change
- `/opsx-sync` — Sync delta specs to main specs
- `/opsx-archive` — Archive a completed change

See `AGENTS.md` for detailed agent guidelines.

## Testing

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_auto_assign_service.py -v
```

## Deployment

### Production Deployment

1. Update environment variables for production
2. Build and deploy using Docker Compose:
```bash
docker-compose -f docker-compose.yml up -d
```

3. Configure nginx reverse proxy (optional)
4. Set up SSL certificates
5. Configure backup strategy

## Performance Optimization

- Connection pooling for database and Redis
- Multi-layer caching strategy
- Async operations throughout
- Database query optimization
- Request rate limiting

## Security

- Input validation with Pydantic
- SQL injection prevention with SQLAlchemy ORM
- XSS protection with security headers
- Rate limiting to prevent abuse
- CORS configuration
- Password hashing (when implemented)

## Troubleshooting

### Database Connection Issues

Check MySQL is running:
```bash
docker-compose ps mysql
docker-compose logs mysql
```

### Redis Connection Issues

Check Redis is running:
```bash
docker-compose ps redis
docker-compose logs redis
```

### Application Not Starting

Check application logs:
```bash
docker-compose logs api
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License

## Support

For issues and questions, please open an issue on GitHub.

## Documentation

Additional documentation is available in the [`docs/`](docs/) directory:

- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Production deployment instructions
- **[Project Structure](docs/PROJECT_STRUCTURE.md)** - Detailed codebase overview
- **[System Design](docs/FastAPI_code_review_system_design.md)** - Architecture documentation
- **[Versioning Guide](docs/VERSIONING.md)** - Version management instructions
