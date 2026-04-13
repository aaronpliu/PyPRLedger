# PRLedger

A production-ready FastAPI-based PR Code Review Result Storage System with MySQL, Redis, and Prometheus integration.

**Current API Version**: 1.6.0
**Current UI Version**: 1.1.0
See `pyproject.toml`, `frontend/package.json`, or run `python scripts/bump_version.py show`.

## Features

- **RESTful API**: Complete REST API for managing pull request reviews, users, and projects
- **Database Integration**: MySQL database with SQLAlchemy ORM and Alembic migrations
- **Caching Layer**: Redis integration for improved performance
- **Monitoring**: Prometheus metrics collection with Grafana dashboards
- **Async Operations**: Full async/await support for high concurrency
- **Error Handling**: Comprehensive error handling and validation
- **Docker Support**: Complete Docker Compose setup for easy deployment
- **Security**: Rate limiting, CORS, and security headers
- **Multi-Project Management** (NEW v1.3.0): Virtual app_name architecture for organizing projects into logical applications
  - Project registry system maps (project_key, repository_slug) pairs to application names
  - Query-time resolution without schema proliferation
  - Support for filtering reviews by multiple apps simultaneously
  - Admin APIs for registry management

## Project Structure

```
PyPRLedger/
├── alembic/                      # Database migrations
│   ├── versions/                 # Migration scripts
│   └── env.py                    # Alembic environment
├── docs/                         # Documentation
├── grafana/                      # Grafana configuration
│   └── provisioning/             # Data sources and dashboard 
├── logs/                         # Application logs
├── requirements/                 # Python dependencies
│   ├── base.txt                  # Base dependencies
│   ├── dev.txt                   # Development dependencies
│   └── prod.txt                  # Production dependencies
├── scripts/                      # Utility scripts
│   ├── bump_version.py           # Version management
│   └── validate_commit_msg.py    # Commit message validation
├── src/                          # Application source code
│   ├── api/                      # API routes
│   │   └── v1/                   # API v1 endpoints
│   │       ├── endpoints/        # Endpoint handlers
│   │       │   ├── __init__.py
│   │       │   ├── projects.py   # Project endpoints
│   │       │   ├── project_registry.py  # Project registry endpoints (NEW)
│   │       │   ├── reviews.py    # Review endpoints
│   │       │   └── users.py      # User endpoints
│   │       ├── __init__.py
│   │       └── api.py            # API router
│   ├── conf/                     # Configuration files
│   │   ├── LOGGING_GUIDE.md      # Logging documentation
│   │   └── logging.yaml          # Logging configuration
│   ├── core/                     # Core functionality
│   │   ├── config.py             # Application configuration
│   │   ├── database.py           # Database configuration
│   │   ├── exceptions.py         # Custom exceptions
│   │   └── middleware.py         # Custom middleware
│   ├── models/                   # SQLAlchemy models
│   │   ├── project.py            # Project model
│   │   ├── project_registry.py   # Project registry model (NEW)
│   │   ├── pull_request.py       # Pull request model
│   │   ├── repository.py         # Repository model
│   │   └── user.py               # User model
│   ├── schemas/                  # Pydantic schemas
│   │   ├── project.py            # Project schemas
│   │   ├── pull_request.py       # Pull request schemas
│   │   ├── repository.py         # Repository schemas
│   │   └── user.py               # User schemas
│   ├── services/                 # Business logic
│   │   ├── project_service.py    # Project service
│   │   ├── project_registry_service.py  # Project registry service (NEW)
│   │   ├── review_service.py     # Review service
│   │   └── user_service.py       # User service
│   ├── utils/                    # Utilities
│   │   ├── log.py                # Logging utilities
│   │   ├── metrics.py            # Metrics collection
│   │   └── redis.py              # Redis utilities
│   ├── __init__.py
│   └── main.py                   # Application entry point
├── tests/                        # Test suite
│   └── conftest.py               # Pytest fixtures and configuration
├── .env.example                  # Environment variables template
├── .gitignore                    # Git ignore rules
├── .pre-commit-config.yaml       # Pre-commit hooks configuration
├── alembic.ini                   # Alembic configuration
├── docker-compose.yml            # Docker Compose configuration
├── Dockerfile                    # Docker image definition
├── init.sql                      # Database initialization script
├── prometheus.yml                # Prometheus configuration
├── pyproject.toml                # Python project metadata
├── pytest.ini                    # Pytest configuration
├── ruff.toml                     # Ruff linter configuration
└── README.md                     # This file
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
- **Metrics**: http://localhost:8000/metrics

## API Endpoints

### Reviews (`/api/v1/reviews`)

- `POST /api/v1/reviews` - Create or update a review (upsert operation)
- `GET /api/v1/reviews` - List reviews with filters (supports `app_names` parameter for multi-app queries)
- `GET /api/v1/reviews/{review_id}` - Get a specific review
- `PUT /api/v1/reviews/{review_id}` - Update a review
- `PATCH /api/v1/reviews/{review_id}/status` - Update review status
- `DELETE /api/v1/reviews/{review_id}` - Delete a review
- `GET /api/v1/reviews/statistics` - Get review statistics
- `PUT /api/v1/reviews/score` - Update review score by composite key

### Project Registry (`/api/v1/`)

**Public Endpoints:**
- `GET /api/v1/apps` - List all registered applications with project counts
- `GET /api/v1/apps/{app_name}/projects` - List projects in specific application
- `GET /api/v1/projects/{project_key}/{repository_slug}/app-name` - Get app name for project

**Admin Endpoints (Authentication TODO):**
- `POST /api/v1/admin/registry/register` - Register project-repo pair to application
- `PUT /api/v1/admin/registry/update` - Move project to different application
- `DELETE /api/v1/admin/registry/unregister` - Remove project from registry

### Users (`/api/v1/users`)

- `POST /api/v1/users` - Create a new user
- `GET /api/v1/users` - List users with filters
- `GET /api/v1/users/{user_id}` - Get a specific user
- `PUT /api/v1/users/{user_id}` - Update a user
- `DELETE /api/v1/users/{user_id}` - Delete a user
- `GET /api/v1/users/statistics` - Get user statistics

### Projects (`/api/v1/projects`)

- `POST /api/v1/projects` - Create a new project
- `GET /api/v1/projects` - List projects with filters
- `GET /api/v1/projects/{project_id}` - Get a specific project
- `PUT /api/v1/projects/{project_id}` - Update a project
- `DELETE /api/v1/projects/{project_id}` - Delete a project
- `GET /api/v1/projects/statistics` - Get project statistics

## Configuration

### Environment Variables

See `.env.example` for all available environment variables.

Key configuration options:
- `DATABASE_*`: MySQL database configuration
- `REDIS_*`: Redis cache configuration
- `PROMETHEUS_ENABLED`: Enable/disable Prometheus metrics
- `RATE_LIMIT_*`: Rate limiting configuration
- `CACHE_TTL_*`: Cache TTL settings

## Database

The system uses MySQL with the following tables:
- `user`: User accounts
- `project`: Projects
- `repository`: Code repositories
- `pull_request_review`: Pull request reviews
- `project_registry`: Project-to-application mappings (NEW in v1.3.0)

### Running Migrations

```bash
alembic upgrade head
```

### Database Schema (v1.3.0+)

**project_registry** table:
- `id` (INT, PK): Auto-increment primary key
- `app_name` (VARCHAR(64)): Application name (indexed)
- `project_key` (VARCHAR(32)): Foreign key to project.project_key
- `repository_slug` (VARCHAR(128)): Repository slug
- `description` (VARCHAR(255)): Optional description
- `created_date`, `updated_date` (DATETIME): Timestamps
- **Unique Constraint**: (project_key, repository_slug) - Each repo pair maps to ONE app
- **Composite Index**: (app_name, project_key, repository_slug) - Fast app-based queries

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

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/unit/test_reviews.py
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
