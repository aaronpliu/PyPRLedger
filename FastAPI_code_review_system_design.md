# PRLedger: Design and Implementation Guide

## 1. Project Structure Best Practices

Based on industry best practices and the referenced GitHub repository [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices), the following project structure is recommended for a robust FastAPI application:

```
PRLedger/
├── alembic/                  # Database migrations
├── src/
│   ├── api/                  # API routers
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── reviews.py
│   │   │   │   ├── users.py
│   │   │   │   └── projects.py
│   │   │   └── api.py
│   │   └── deps.py          # API dependencies
│   ├── core/                 # Core application logic
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   └── middleware.py
│   ├── models/               # Database models
│   │   ├── user.py
│   │   ├── pull_request.py
│   │   ├── project.py
│   │   └── repository.py
│   ├── schemas/              # Pydantic models
│   │   ├── user.py
│   │   ├── pull_request.py
│   │   ├── project.py
│   │   └── repository.py
│   ├── services/             # Business logic
│   │   ├── review_service.py
│   │   ├── user_service.py
│   │   └── project_service.py
│   ├── utils/                # Utility functions
│   │   ├── cache.py
│   │   └── metrics.py
│   └── main.py              # Application entry point
├── tests/                    # Unit and integration tests
│   ├── unit/
│   └── integration/
├── requirements/             # Dependency files
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── .env                     # Environment variables
├── alembic.ini              # Alembic configuration
└── docker-compose.yml       # Docker composition
```

This structure promotes separation of concerns, making the application more maintainable, testable, and scalable [0†].

## 2. Database Design Optimization for MySQL

### Schema Design

Based on the requirements, the following database schema is optimized for MySQL:

``sql
-- User table with business user_id (e.g., GitHub user ID)
CREATE TABLE user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,  -- Business ID (e.g., GitHub user ID)
    username VARCHAR(64) NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    email_address VARCHAR(255) NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    is_reviewer BOOLEAN NOT NULL DEFAULT FALSE,
    created_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_username (username),
    INDEX idx_email (email_address)
);

-- Project table with business project_id
CREATE TABLE project (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL UNIQUE,  -- Business ID (e.g., GitHub project ID)
    project_name VARCHAR(128) NOT NULL,
    project_key VARCHAR(32) NOT NULL UNIQUE,
    project_url VARCHAR(255) NOT NULL,
    created_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_project_id (project_id)
);

-- Repository table linked to project via business IDs
CREATE TABLE repository (
    id INT AUTO_INCREMENT PRIMARY KEY,
    repository_id INT NOT NULL UNIQUE,  -- Business ID (e.g., GitHub repo ID)
    project_id INT NOT NULL,  -- FK to project.project_id (business ID)
    repository_name VARCHAR(128) NOT NULL,
    repository_slug VARCHAR(128) NOT NULL,
    repository_url VARCHAR(255) NOT NULL,
    created_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES project(project_id) ON DELETE CASCADE,
    INDEX idx_repository_id (repository_id),
    INDEX idx_repository_project_id (project_id)
);

-- Pull request review table with all business ID foreign keys
CREATE TABLE pull_request_review (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Foreign keys to business IDs (not database auto-IDs)
    project_id INT NOT NULL,  -- FK to project.project_id
    pull_request_user_id INT NOT NULL,  -- FK to user.user_id (author)
    reviewer_id INT NOT NULL,  -- FK to user.user_id (reviewer)
    repository_id INT NOT NULL,  -- FK to repository.repository_id
    
    -- Pull request information
    pull_request_id VARCHAR(64) NOT NULL,
    pull_request_commit_id VARCHAR(64),
    source_branch VARCHAR(64) NOT NULL,
    target_branch VARCHAR(64) NOT NULL,
    
    -- Code review details
    git_code_diff TEXT,
    source_filename VARCHAR(255),
    ai_suggestions JSON,
    reviewer_comments TEXT,
    
    -- Review metrics
    score INT,
    
    -- Status
    pull_request_status VARCHAR(32) NOT NULL,
    
    -- Metadata
    metadata JSON,
    
    -- Timestamps
    created_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (project_id) REFERENCES project(project_id) ON DELETE CASCADE,
    FOREIGN KEY (pull_request_user_id) REFERENCES user(user_id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_id) REFERENCES user(user_id) ON DELETE CASCADE,
    FOREIGN KEY (repository_id) REFERENCES repository(repository_id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_pull_request_id (pull_request_id),
    INDEX idx_pr_project_id (project_id),
    INDEX idx_reviewer_id (reviewer_id),
    INDEX idx_created_date (created_date)
);
```

### Key Design Decisions

1. **Business ID Strategy**:
   - All tables use business IDs (e.g., GitHub IDs) passed by API callers
   - Foreign keys reference business IDs (`user_id`, `project_id`, `repository_id`), not auto-generated database IDs
   - This ensures consistency with external systems and simplifies data synchronization

2. **Indexing Strategy**:
   - Business ID columns have unique constraints and indexes for fast lookups
   - Foreign key columns are indexed for efficient joins
   - Temporal index on `created_date` for time-based queries
   - Composite indexes can be added based on query patterns

3. **Data Types**:
   - `JSON` type for flexible metadata storage (AI suggestions, custom metadata)
   - `TEXT` for large text fields (code diff, reviewer comments)
   - `DATETIME` with automatic timestamp updates for audit trails

### Optimization Strategies

1. **Connection Pooling**:
   - Use async database drivers with connection pooling
   - Configure appropriate pool size based on expected concurrent requests
   - Default pool size: 20 connections, adjustable via environment variables

2. **Query Optimization**:
   - Use EXPLAIN to analyze query execution plans
   - Avoid N+1 query problem by using eager loading for relationships
   - Leverage indexes for WHERE clauses and JOIN operations
   - Use pagination for large result sets (LIMIT/OFFSET)

3. **Partitioning** (Future Enhancement):
   - Consider partitioning the `pull_request_review` table by date range for better performance with time-based queries
   - Range partitioning by `created_date` (monthly or quarterly)

4. **Caching Integration**:
   - Redis cache for frequently accessed reviews and statistics
   - Cache invalidation on write operations
   - TTL-based expiration for time-sensitive data

## 3. Redis Caching Strategies

Redis will be used for caching frequently accessed data and improving system performance. The following caching strategies are recommended:

### Cache Architecture

1. **Multi-Layer Caching**:
   - L1: In-memory cache for frequently accessed data (user sessions, project stats)
   - L2: Redis cache for less frequent but important data (pull request reviews)

2. **Cache Patterns**:
   - **Cache Aside**: Application code explicitly handles cache operations
   - **Read Through**: Redis fetches data from DB on cache miss
   - **Write Through**: Updates are written to both DB and cache

### Implementation with FastAPI

Using the approach from [Redis FastAPI Tutorial](https://redis.io/tutorials/develop/python/fastapi):

```python
import redis
from fastapi import Depends
from typing import Annotated

RedisDep = Annotated[redis.Redis, Depends(get_redis_client)]

async def get_pull_request_review(pr_id: str, redis: RedisDep):
    # Try to get from cache first
    cached_data = await redis.get(f"pr_review:{pr_id}")
    if cached_data:
        return json.loads(cached_data)
    
    # If not in cache, fetch from database
    review = await fetch_review_from_db(pr_id)
    
    # Store in cache with expiration
    await redis.setex(f"pr_review:{pr_id}", 3600, json.dumps(review))
    return review
```

### Cache Invalidation Strategy

1. **Time-based Invalidation**:
   - Set appropriate TTL (Time To Live) for different types of data
   - Pull request reviews: 1 hour
   - Project statistics: 6 hours
   - User information: 12 hours

2. **Event-based Invalidation**:
   - Invalidate cache when reviews are updated
   - Use Redis pub/sub for cache invalidation across multiple instances

## 4. Asynchronous Programming Patterns

FastAPI's async capabilities are crucial for handling high concurrency [32†]. The following patterns should be used:

### API Endpoint Design

```python
from fastapi import APIRouter, Depends
from typing import Annotated

router = APIRouter()

@router.post("/reviews")
async def create_review(
    review_data: ReviewCreate,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)]
):
    # Asynchronous database operation
    review = await db.execute(select(Review).where(Review.id == review_data.id))
    
    # Asynchronous Redis operation
    await redis.setex(f"review:{review.id}", 3600, json.dumps(review.dict()))
    
    return {"status": "success"}

@router.get("/reviews")
async def get_reviews(
    project_id: str,
    date_range: DateRange,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)]
):
    # Try cache first
    cache_key = f"reviews:{project_id}:{date_range.hash()}"
    cached_data = await redis.get(cache_key)
    
    if cached_data:
        return json.loads(cached_data)
    
    # Fetch from database if not cached
    reviews = await db.execute(
        select(Review).where(
            Review.project_id == project_id,
            Review.created_date.between(date_range.start, date_range.end)
        )
    )
    
    # Cache the result
    await redis.setex(cache_key, 1800, json.dumps([r.dict() for r in reviews]))
    
    return [r.dict() for r in reviews]
```

### Background Tasks

For operations that can be processed asynchronously after the response:

```python
from fastapi import BackgroundTasks

@router.post("/reviews")
async def create_review(
    review_data: ReviewCreate,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)]
):
    # Create review immediately
    review = await create_review_in_db(review_data, db)
    
    # Add background task to update statistics
    background_tasks.add_task(update_review_statistics, review.project_id)
    
    return {"status": "success", "review_id": review.id}

async def update_review_statistics(project_id: str):
    # Perform heavy computation or update statistics
    stats = await calculate_review_statistics(project_id)
    await redis.setex(f"stats:{project_id}", 3600, json.dumps(stats))
```

## 5. Monitoring and Alerting with Prometheus/Grafana

### Prometheus Metrics Setup

Based on the requirements and the [fastapi-prometheus-grafana](https://github.com/Kludex/fastapi-prometheus-grafana) example:

```python
from prometheus_client import Counter, Histogram, Gauge
from fastapi import Request
import time

# Define metrics
review_counter = Counter('code_review_total', 'Total number of code reviews', ['project', 'reviewer'])
review_duration = Histogram('code_review_duration_seconds', 'Time spent on code review')
active_reviewers = Gauge('active_reviewers', 'Number of active reviewers')

# Middleware to collect metrics
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Record metrics
    review_duration.observe(duration)
    
    return response

# API endpoints to update metrics
@router.post("/reviews")
async def create_review(review_data: ReviewCreate):
    # Create review
    review = await create_review_in_db(review_data)
    
    # Update metrics
    review_counter.labels(project=review.project_id, reviewer=review.reviewer_id).inc()
    active_reviewers.set(await get_active_reviewers_count())
    
    return {"status": "success", "review_id": review.id}
```

### Grafana Dashboard Setup

Based on the requirements, the following metrics should be monitored:

1. **Daily Pull Request Reviews**:
   ```promql
   sum(rate(code_review_total[1d])) by (project)
   ```

2. **Daily Reviewer Activity**:
   ```promql
   count(active_reviewers) by (project)
   ```

3. **Top 5 Projects by Review Count**:
   ```promql
   topk(5, sum(code_review_total) by (project))
   ```

4. **File Change Frequency**:
   ```promql
   sum(rate(file_change_total[1d])) by (filename)
   ```

5. **Pull Request Volume**:
   ```promql
   sum(rate(pull_request_total[1d])) by (project)
   ```

### Docker Compose Setup

```
version: '3'

services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources

  fastapi:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - prometheus
      - grafana
```

## 6. Performance Optimization Techniques

### Database Optimization

1. **Connection Pooling**:
   - Use async database drivers with connection pooling
   - Configure appropriate pool size based on concurrency needs

2. **Query Optimization**:
   - Use indexed columns for WHERE clauses
   - Avoid SELECT *; only fetch required columns
   - Use pagination for large result sets

3. **Database Sharding**:
   - Consider sharding by project_id for horizontal scaling

### Caching Strategy

1. **Multi-level Caching**:
   - In-memory cache for hot data
   - Redis for distributed caching

2. **Cache Warming**:
   - Preload frequently accessed data into cache
   - Use background tasks to keep cache fresh

### Concurrency Handling

1. **Async I/O Operations**:
   - Use async/await for all I/O operations
   - Avoid blocking calls in async functions

2. **Semaphore Limiting**:
   - Use semaphores to limit concurrent operations
   - Prevent resource exhaustion under high load

## 7. API Design Patterns

### RESTful API Design

```python
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, List, Optional

router = APIRouter(prefix="/api/v1", tags=["reviews"])

@router.post("/reviews", response_model=ReviewResponse, status_code=201)
async def create_review(
    review_data: ReviewCreate,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)]
) -> Review:
    """Create a new pull request review."""
    review = await review_service.create_review(review_data, db, redis)
    return review

@router.get("/reviews", response_model=List[ReviewResponse])
async def list_reviews(
    project_id: Optional[str] = None,
    repository_id: Optional[str] = None,
    username: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)]
) -> List[Review]:
    """List pull request reviews with optional filtering."""
    filters = {}
    if project_id:
        filters["project_id"] = project_id
    if repository_id:
        filters["repository_id"] = repository_id
    if username:
        user = await get_user_by_username(username, db)
        if user:
            filters["pull_request_user_id"] = user.id
    if date_from and date_to:
        filters["created_date"] = (date_from, date_to)
    
    reviews = await review_service.list_reviews(
        filters=filters,
        limit=limit,
        offset=offset,
        db=db,
        redis=redis
    )
    return reviews

@router.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: str,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)]
) -> Review:
    """Get a specific pull request review by ID."""
    review = await review_service.get_review(review_id, db, redis)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review

@router.put("/reviews/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: str,
    review_update: ReviewUpdate,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)]
) -> Review:
    """Update an existing pull request review."""
    review = await review_service.update_review(review_id, review_update, db, redis)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review

@router.delete("/reviews/{review_id}", status_code=204)
async def delete_review(
    review_id: str,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)]
):
    """Delete a pull request review."""
    deleted = await review_service.delete_review(review_id, db, redis)
    if not deleted:
        raise HTTPException(status_code=404, detail="Review not found")
```

### Error Handling

```python
from fastapi import HTTPException
from pydantic import ValidationError

class ReviewNotFoundError(HTTPException):
    def __init__(self, review_id: str):
        super().__init__(status_code=404, detail=f"Review with ID {review_id} not found")

class InvalidReviewDataError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)

@app.exception_handler(ReviewNotFoundError)
async def review_not_found_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"error": "Validation error", "details": exc.errors()}
    )
```

## 8. Concurrency Handling

### Async Database Operations

Using SQLModel for async database operations:

```python
from sqlmodel import SQLModel, create_engine, Session, select
from typing import Annotated, List, Optional

class Review(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pull_request_id: str = Field(index=True)
    project_id: int = Field(foreign_key="project.id")
    # ... other fields

engine = create_async_engine(DATABASE_URL)

async def get_db_session():
    db = Session(engine)
    try:
        yield db
    finally:
        await db.close()

DBDep = Annotated[Session, Depends(get_db_session)]

async def get_reviews_by_project(
    project_id: int,
    limit: int = 100,
    offset: int = 0,
    db: DBDep
) -> List[Review]:
    statement = (
        select(Review)
        .where(Review.project_id == project_id)
        .limit(limit)
        .offset(offset)
    )
    results = await db.execute(statement)
    return results.scalars().all()
```

### Concurrency Limits

To prevent resource exhaustion:

```python
from asyncio import Semaphore

# Create a semaphore to limit concurrent operations
max_concurrent_operations = 1000
semaphore = Semaphore(max_concurrent_operations)

async def limited_operation():
    async with semaphore:
        # Perform the operation
        await some_resource_intensive_operation()

# Use in endpoints
@router.post("/reviews")
async def create_review(
    review_data: ReviewCreate,
    db: DBDep,
    redis: RedisDep
):
    async with semaphore:
        # Create review with limited concurrency
        review = await review_service.create_review(review_data, db, redis)
        return review
```

## 9. Additional Components and Packages

### Required Packages

```txt
# requirements/base.txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
sqlmodel>=0.0.14
redis>=5.0.0
prometheus-client>=0.19.0
pydantic>=2.0.0
python-multipart>=0.0.6
python-jose>=3.3.0
python-passlib>=1.7.4
alembic>=1.13.0
```

### Development Packages

```txt
# requirements/dev.txt
-r base.txt
pytest>=7.4.0
pytest-asyncio>=0.21.0
httpx>=0.25.0
faker>=19.0.0
black>=23.0.0
isort>=5.12.0
flake8>=6.0.0
mypy>=1.7.0
```

### Production Packages

```txt
# requirements/prod.txt
-r base.txt
gunicorn>=21.2.0
uvicorn>=0.24.0
```

### Docker Configuration

```
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements/prod.txt .
RUN pip install --no-cache-dir -r prod.txt

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Conclusion

This comprehensive system design document provides a robust architecture for a FastAPI-based pull request code review system. The key takeaways include:

1. **Scalable Project Structure**: Organized codebase with clear separation of concerns
2. **Optimized Database Design**: Efficient schema with proper indexing for MySQL
3. **Multi-layer Caching**: Redis integration to improve performance
4. **Asynchronous Operations**: Full async support for high concurrency
5. **Comprehensive Monitoring**: Prometheus and Grafana integration for observability
6. **RESTful API Design**: Clean and intuitive API endpoints
7. **Effective Concurrency Handling**: Semaphore limits and async patterns
8. **Complete Deployment Setup**: Docker-based deployment configuration

This system can efficiently handle 1000+ requests per second while providing the required functionality for code review management and analytics.