# PRLedger - Deployment Guide

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Docker Deployment](#docker-deployment)
4. [Production Deployment](#production-deployment)
5. [Monitoring and Maintenance](#monitoring-and-maintenance)
6. [Troubleshooting](#troubleshooting)

---

## 🔧 Prerequisites

### Required Software

- **Docker**: 20.10 or higher
- **Docker Compose**: 2.0 or higher
- **Python**: 3.11+ (for local development)
- **MySQL**: 8.0+ (if not using Docker)
- **Redis**: 7.0+ (if not using Docker)

### Required Hardware

- **Minimum**: 2 CPU cores, 4GB RAM, 20GB storage
- **Recommended**: 4 CPU cores, 8GB RAM, 50GB storage
- **High Load**: 8+ CPU cores, 16GB+ RAM, 100GB+ storage

---

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

---

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)

#### 1. Start All Services

```bash
docker-compose up -d
```

#### 2. Check Service Status

```bash
docker-compose ps
```

Expected output:
```
NAME                     STATUS
PRLedger-api              Up
code-review-mysql          Up
code-review-redis           Up
code-review-prometheus      Up
code-review-grafana        Up
```

#### 3. Run Database Migrations

```bash
docker-compose exec api alembic upgrade head
```

#### 4. View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f mysql
docker-compose logs -f redis
```

#### 5. Stop Services

```bash
docker-compose down
```

#### 6. Stop Services and Remove Volumes

```bash
docker-compose down -v
```

### Docker Compose Services

#### API Service

- **Port**: 8000
- **Health Check**: http://localhost:8000/health
- **Restart Policy**: unless-stopped

#### MySQL Service

- **Port**: 3306
- **Volume**: mysql-data
- **Default Password**: rootpassword
- **Health Check**: mysqladmin ping

#### Redis Service

- **Port**: 6379
- **Volume**: redis-data
- **Max Memory**: 256MB
- **Eviction Policy**: allkeys-lru

#### Prometheus Service

- **Port**: 9090
- **Volume**: prometheus-data
- **Scrape Interval**: 15s

#### Grafana Service

- **Port**: 3000
- **Volume**: grafana-data
- **Default Credentials**: admin/admin

---

## 🚀 Production Deployment

### 1. Environment Configuration

Update `.env` file with production values:

```bash
ENV=production
DEBUG=False
SECRET_KEY=<your-strong-secret-key>
DATABASE_PASSWORD=<your-db-password>
```

### 2. SSL/TLS Configuration

#### Using Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Database Setup

#### For Production MySQL

```bash
# Configure MySQL with production settings
max_connections = 500
innodb_buffer_pool_size = 4G
innodb_log_file_size = 512M
query_cache_size = 256M
```

#### Backup Strategy

```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
mysqldump -u root -p code_review | gzip > /backup/code_review_$DATE.sql.gz

# Restore
gunzip < /backup/code_review_YYYYMMDD.sql.gz | mysql -u root -p code_review
```

### 4. Redis Configuration

#### For Production Redis

```bash
# Memory optimization
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000
appendonly yes
```

### 5. Application Scaling

#### Horizontal Scaling

```yaml
# docker-compose.yml
services:
  api:
    deploy:
      replicas: 3  # Run 3 instances
    # ... other config
```

#### Load Balancing

Configure your load balancer (e.g., Nginx, HAProxy) to distribute traffic across API instances.

### 6. CI/CD Pipeline

#### GitHub Actions Example

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to production
        run: |
          docker-compose -f docker-compose.prod.yml pull
          docker-compose -f docker-compose.prod.yml up -d
```

---

## 📊 Monitoring and Maintenance

### 1. Prometheus Metrics

Access metrics at: `http://your-server/metrics`

Key metrics to monitor:
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `review_total` - Total reviews created
- `db_connections_active` - Active DB connections
- `cache_hits_total` - Cache hit rate

### 2. Grafana Dashboards

Access Grafana at: `http://your-server:3000`

Pre-configured dashboards:
- Code Review Overview
- API Performance
- Database Performance
- Cache Performance
- System Resources

### 3. Health Checks

#### Application Health

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

#### Database Health

```bash
docker-compose exec mysql mysqladmin ping -h localhost -u root -prootpassword
```

#### Redis Health

```bash
docker-compose exec redis redis-cli ping
```

### 4. Log Management

#### Application Logs

```bash
docker-compose logs -f api --tail=100
```

#### Structured Logging

Logs are structured with JSON for easy parsing:
- Request ID tracking
- User ID (if authenticated)
- Timestamp
- Severity level
- Error details

### 5. Maintenance Tasks

#### Daily
- Check system health status
- Review error logs
- Verify backups completed

#### Weekly
- Review performance metrics
- Check disk space
- Review slow query logs

#### Monthly
- Update dependencies
- Review and update documentation
- Conduct security audit
- Review and optimize database queries

---

## 🔍 Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Symptoms**: Application fails to connect to MySQL

**Solutions**:
```bash
# Check MySQL is running
docker-compose ps mysql

# Check MySQL logs
docker-compose logs mysql

# Test connection
docker-compose exec api python -c "import aiomysql; ..."
```

#### 2. Redis Connection Errors

**Symptoms**: Cache operations failing

**Solutions**:
```bash
# Check Redis is running
docker-compose ps redis

# Check Redis logs
docker-compose logs redis

# Test connection
docker-compose exec redis redis-cli ping
```

#### 3. High Memory Usage

**Symptoms**: Application uses excessive memory

**Solutions**:
```bash
# Check memory usage
docker stats

# Restart services
docker-compose restart

# Scale horizontally
docker-compose up -d --scale api=3
```

#### 4. Slow API Responses

**Symptoms**: API requests take too long

**Solutions**:
1. Check Prometheus metrics for bottlenecks
2. Review database slow query log
3. Verify cache hit rate
4. Check network latency
5. Scale up resources if needed

#### 5. Migration Failures

**Symptoms**: Alembic migration fails

**Solutions**:
```bash
# Check current migration state
docker-compose exec api alembic current

# Stamp to specific version
docker-compose exec api alembic stamp <version>

# Rollback to previous version
docker-compose exec api alembic downgrade -1
```

### Getting Help

If issues persist:

1. Check application logs
2. Review documentation
3. Search existing issues
4. Create a new issue with:
   - Error messages
   - System specifications
   - Steps to reproduce
   - Expected vs actual behavior

---

## 📞 Support Resources

- **Documentation**: README.md
- **API Docs**: /api/docs
- **Project Structure**: PROJECT_STRUCTURE.md
- **Issues**: GitHub Issues
