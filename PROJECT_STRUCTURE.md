# FastAPI Pull Request Code Review System - Project Structure

## 📁 Project Root Directory

### 📄 Configuration Files

- **`.env.example`** - Environment variables template
- **`.gitignore`** - Git ignore rules
- **`Dockerfile`** - Docker image definition for the application
- **`docker-compose.yml`** - Docker Compose configuration for all services
- **`alembic.ini`** - Alembic database migration configuration
- **`prometheus.yml`** - Prometheus monitoring configuration
- **`README.md`** - Project documentation

### 📁 Requirements Directory

- **`requirements/base.txt`** - Base dependencies
  - fastapi, uvicorn, sqlalchemy, aiomysql, redis, prometheus-client, etc.
  
- **`requirements/dev.txt`** - Development dependencies
  - pytest, pytest-asyncio, black, isort, mypy, etc.
  
- **`requirements/prod.txt`** - Production dependencies
  - gunicorn, opentelemetry, sentry-sdk, psutil, etc.

---

## 📁 src/ - Application Source Code

### 📁 api/ - API Routes

#### 📁 api/v1/ - API Version 1

##### 📁 api/v1/endpoints/ - API Endpoint Handlers

- **`reviews.py`** - Pull request review endpoints
  - POST `/api/v1/reviews` - Create review
  - POST `/api/v1/reviews/upsert` - Create or update review
  - GET `/api/v1/reviews` - List reviews with filters
  - GET `/api/v1/reviews/{review_id}` - Get specific review
  - PUT `/api/v1/reviews/{review_id}` - Update review
  - PATCH `/api/v1/reviews/{review_id}/status` - Update review status
  - DELETE `/api/v1/reviews/{review_id}` - Delete review
  - GET `/api/v1/reviews/statistics` - Get review statistics

- **`users.py`** - User management endpoints
  - POST `/api/v1/users` - Create user
  - GET `/api/v1/users` - List users
  - GET `/api/v1/users/{user_id}` - Get specific user
  - PUT `/api/v1/users/{user_id}` - Update user
  - DELETE `/api/v1/users/{user_id}` - Delete user
  - PATCH `/api/v1/users/{user_id}/toggle-reviewer` - Toggle reviewer status
  - PATCH `/api/v1/users/{user_id}/activate` - Activate user
  - PATCH `/api/v1/users/{user_id}/deactivate` - Deactivate user

- **`projects.py`** - Project management endpoints
  - POST `/api/v1/projects` - Create project
  - GET `/api/v1/projects` - List projects
  - GET `/api/v1/projects/{project_id}` - Get specific project
  - PUT `/api/v1/projects/{project_id}` - Update project
  - DELETE `/api/v1/projects/{project_id}` - Delete project
  - GET `/api/v1/projects/statistics` - Get project statistics
  - GET `/api/v1/projects/top/reviews` - Top projects by reviews
  - GET `/api/v1/projects/top/reviewers` - Top projects by reviewers

- **`api.py`** - API router composition
  - Includes all endpoint routers
  - API information endpoint

### 📁 core/ - Core Functionality

- **`config.py`** - Application configuration
  - Settings class with all configuration options
  - Environment variable handling
  - Database, Redis, and security configuration

- **`database.py`** - Database configuration
  - SQLAlchemy async engine setup
  - Connection pooling
  - Session management
  - Database initialization and cleanup

- **`exceptions.py`** - Custom exceptions
  - Application exception hierarchy
  - Error codes and messages
  - Exception handlers

- **`middleware.py`** - Custom middleware
  - Logging middleware
  - Rate limiting middleware
  - Cache control middleware
  - Security headers middleware
  - Timing middleware

### 📁 models/ - SQLAlchemy Models

- **`user.py`** - User model
  - User table definition
  - Relationships to reviews
  - User attributes and methods

- **`project.py`** - Project model
  - Project table definition
  - Relationships to repositories and reviews
  - Project attributes and methods

- **`repository.py`** - Repository model
  - Repository table definition
  - Relationships to projects
  - Repository attributes and methods

- **`pull_request.py`** - Pull request review model
  - Review table definition
  - Relationships to users and projects
  - Review attributes and status management

### 📁 schemas/ - Pydantic Schemas

- **`user.py`** - User schemas
  - UserCreate, UserUpdate, UserResponse
  - UserListResponse, UserStats
  - UserLogin schema

- **`project.py`** - Project schemas
  - ProjectCreate, ProjectUpdate, ProjectResponse
  - ProjectListResponse, ProjectStats
  - ProjectFilter schema

- **`repository.py`** - Repository schemas
  - RepositoryCreate, RepositoryUpdate, RepositoryResponse
  - RepositoryListResponse, RepositoryStats
  - RepositoryFilter schema

- **`pull_request.py`** - Review schemas
  - ReviewCreate, ReviewUpdate, ReviewResponse
  - ReviewListResponse, ReviewStats
  - ReviewFilter, ReviewTransition schemas

### 📁 services/ - Business Logic

- **`user_service.py`** - User service
  - User CRUD operations
  - Authentication methods
  - User statistics
  - Cache management

- **`project_service.py`** - Project service
  - Project CRUD operations
  - Project statistics
  - Search functionality
  - Cache management

- **`review_service.py`** - Review service
  - Review CRUD operations
  - Upsert operations
  - Review statistics
  - Cache management

### 📁 utils/ - Utilities

- **`redis.py`** - Redis utilities
  - Redis connection management
  - Cache operations (get, set, delete, etc.)
  - RedisCache utility class

- **`metrics.py`** - Metrics collection
  - Prometheus metrics definition
  - MetricsCollector class
  - OperationTimer context manager
  - Various metric types (HTTP, DB, Cache, System)

### 📄 main.py - Application Entry Point

- FastAPI application initialization
- Lifespan management
- Exception handlers
- Middleware registration
- Router registration

---

## 📁 alembic/ - Database Migrations

- **`env.py`** - Alembic environment configuration
- **`script.py.mako`** - Migration script template

### 📁 alembic/versions/ - Migration Scripts

- **`001_initial_schema.py`** - Initial database schema
  - User table
  - Project table
  - Repository table
  - Pull request review table

---

## 📁 grafana/ - Grafana Configuration

### 📁 grafana/provisioning/ - Provisioning Configuration

#### 📁 grafana/provisioning/datasources/

- **`prometheus.yml`** - Prometheus datasource configuration

#### 📁 grafana/provisioning/dashboards/

- **`code_review.yml`** - Dashboard provisioning configuration

### 📁 grafana/dashboards/ - Dashboard Definitions

- Directory for storing custom Grafana dashboards

---

## 📁 tests/ - Test Suite

### 📁 tests/unit/ - Unit Tests

- Directory for unit tests
- Tests individual components in isolation

### 📁 tests/integration/ - Integration Tests

- Directory for integration tests
- Tests component interactions

### 📄 tests/conftest.py - Pytest Configuration

- Test fixtures
- Database setup/teardown
- Test client configuration

---

## 🔑 Key Features Implemented

### 1. API Layer
- ✅ RESTful API design
- ✅ Async/await patterns
- ✅ Request validation
- ✅ Comprehensive error handling
- ✅ Automatic API documentation (OpenAPI/Swagger)

### 2. Database Layer
- ✅ MySQL database with SQLAlchemy
- ✅ Async database operations
- ✅ Connection pooling
- ✅ Database migrations with Alembic
- ✅ Foreign key relationships
- ✅ Optimized indexes

### 3. Cache Layer
- ✅ Redis integration
- ✅ Multi-level caching
- ✅ Cache TTL management
- ✅ Cache invalidation strategies
- ✅ Redis utility classes

### 4. Monitoring Layer
- ✅ Prometheus metrics
- ✅ Custom metrics collection
- ✅ Grafana dashboards
- ✅ System metrics
- ✅ Business metrics

### 5. Security
- ✅ Input validation
- ✅ Rate limiting
- ✅ CORS configuration
- ✅ Security headers
- ✅ Error handling

### 6. DevOps
- ✅ Docker support
- ✅ Docker Compose setup
- ✅ Environment configuration
- ✅ Health checks
- ✅ Production-ready deployment

---

## 🚀 Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd fastapi-code-review
   cp .env.example .env
   ```

2. **Start Services**
   ```bash
   docker-compose up -d
   ```

3. **Access Application**
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/api/docs
   - Grafana: http://localhost:3000
   - Prometheus: http://localhost:9090

---

## 📊 Monitoring Dashboard

The system includes pre-configured Grafana dashboards for monitoring:
- API performance metrics
- Database query metrics
- Cache hit/miss rates
- User and project statistics
- System resource usage

---

## 🧪 Testing

Run the test suite:
```bash
pytest
```

With coverage:
```bash
pytest --cov=src
```

---

## 📝 Documentation

- **API Documentation**: Available at `/api/docs`
- **OpenAPI Spec**: Available at `/api/openapi.json`
- **README.md**: Complete project documentation

---

## 🎯 Production Deployment Checklist

- [ ] Update environment variables for production
- [ ] Set strong SECRET_KEY
- [ ] Configure production database
- [ ] Set up SSL/TLS
- [ ] Configure backup strategy
- [ ] Set up monitoring alerts
- [ ] Configure log aggregation
- [ ] Set up CDN for static assets (if needed)
- [ ] Configure rate limiting
- [ ] Set up CI/CD pipeline
- [ ] Create runbooks for operations
- [ ] Set up disaster recovery plan

---

## 📞 Support

For issues and questions:
- Check documentation in README.md
- Review API docs at /api/docs
- Open an issue on GitHub
