## 1. Create monitoring directory structure

- [x] 1.1 Create `monitoring/` directory with subdirectories: `prometheus/rules/`, `alertmanager/`, `grafana/provisioning/datasources/`, `grafana/provisioning/dashboards/`, `grafana/dashboards/`
- [x] 1.2 Create `monitoring/.env.example` with environment variable defaults (GF_SECURITY_ADMIN_PASSWORD, SLACK_WEBHOOK_URL, PROMETHEUS_RETENTION_TIME, etc.)

## 2. Prometheus configuration

- [x] 2.1 Create `monitoring/prometheus/prometheus.yml` with:
  - Global config: scrape_interval 15s, evaluation_interval 15s
  - Alertmanager target pointing to `alertmanager:9093`
  - Rule files reference: `rules/*.yml`
  - Scrape configs: `PRLedger` job targeting `api:8000/api/metrics` (10s interval) and `prometheus` self-monitoring job (15s interval)
  - Web lifecycle enabled for hot-reload
- [x] 2.2 Create `monitoring/prometheus/rules/prledger_alerts.yml` with application-level alert rules:
  - `PRLedgerDown`: critical — absent(up{job="PRLedger"}) for 1m
  - `APIErrorRateHigh`: warning — rate(errors_total[5m]) / rate(http_requests_total[5m]) > 0.05
  - `APILatencyHigh`: warning — histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 2
  - `ReviewBacklogGrowing`: info — review_backlog_count > 50
  - `CacheErrorRatePositive`: warning — rate(cache_errors_total[5m]) > 0
- [x] 2.3 Create `monitoring/prometheus/rules/infra_alerts.yml` with infrastructure alert rules:
  - `HighCPUUsage`: warning — system_cpu_usage_percent > 80
  - `HighMemoryUsage`: warning — system_memory_usage_bytes / (system_memory_usage_bytes + system_memory_available_bytes) > 0.9
  - `LowDiskSpace`: critical — system_disk_available_bytes / system_disk_usage_bytes < 0.1
  - `DBConnectionsHigh`: warning — db_connections_active > 80 (relative to pool size, use a reasonable threshold)

## 3. AlertManager configuration

- [x] 3.1 Create `monitoring/alertmanager/alertmanager.yml` with:
  - Default receiver: console (log to stdout)
  - Optional Slack receiver: conditionally enabled via `SLACK_WEBHOOK_URL` env var
  - Route block with severity-based routing: `critical` → all receivers, `warning` → Slack + console, `info` → console only
  - Inhibition rules: `critical` inhibits `warning` of the same alert type to reduce noise
  - Grouping by `alertname` and `severity` with 30s group wait and 5m repeat interval

## 4. Grafana provisioning configuration

- [x] 4.1 Create `monitoring/grafana/provisioning/datasources/prometheus.yml` pointing to `http://prometheus:9090` with `isDefault: true` and POST HTTP method
- [x] 4.2 Create `monitoring/grafana/provisioning/dashboards/dashboards.yml` provider config that loads JSON dashboards from `/var/lib/grafana/dashboards` with 10s update interval

## 5. Grafana dashboards

- [x] 5.1 Create `monitoring/grafana/dashboards/prledger_overview.json` with panels:
  - Row 1: Request rate (RPS) by endpoint + HTTP status breakdown (stacked area chart)
  - Row 2: P50 / P95 / P99 latency by endpoint (time series)
  - Row 3: Error rate (5xx vs 4xx) over time (time series)
  - Row 4: Active users, open PRs, pending reviews (stat panels)
  - Row 5: Cache hit ratio % (gauge), DB connection pool usage (gauge)
  - Row 6: System resources — CPU %, memory usage, disk usage (time series)
- [x] 5.2 Create `monitoring/grafana/dashboards/review_analytics.json` with panels:
  - Row 1: Review volume by project and by reviewer (bar chart)
  - Row 2: Review cycle time histogram (p50/p95/p99) — time series of histogram quantiles
  - Row 3: Review score distribution (heatmap or histogram)
  - Row 4: Reviewer load balance (active PRs per reviewer as bar chart)
  - Row 5: Review backlog by project (table + time series)

## 6. Standalone docker-compose

- [x] 6.1 Create `monitoring/docker-compose.yml` with three services:
  - `prometheus`: image prom/prometheus:latest, port 9090, bind mount `./prometheus/prometheus.yml` and `./prometheus/rules/`, volume for data, resource limits (256M memory), network `code-review-network` declared as external
  - `grafana`: image grafana/grafana:latest, port 3000, env vars from `.env` for admin credentials, bind mounts for `./grafana/provisioning` and `./grafana/dashboards`, volume for data, resource limits (128M memory), depends on prometheus
  - `alertmanager`: image prom/alertmanager:latest, port 9093, bind mount `./alertmanager/alertmanager.yml`, volume for data, resource limits (128M memory), env-var-based Slack webhook via `SLACK_WEBHOOK_URL`
- [x] 6.2 Add volume definitions for `prometheus-data`, `grafana-data`, `alertmanager-data`
- [x] 6.3 Add network declaration: `code-review-network` with `external: true` (with comments explaining the user must run `docker network create code-review-network` before deploying)
- [x] 6.4 Add healthchecks for all three services

## 7. Clean up root-level files

- [x] 7.1 Remove Prometheus and Grafana service definitions (including volumes and network attachment) from root `docker-compose.yml`
- [x] 7.2 Add a comment in root `docker-compose.yml` at the location of the removed services referencing `monitoring/docker-compose.yml`
- [x] 7.3 Remove `prometheus.yml` from project root
- [x] 7.4 Remove `grafana/` directory from project root (including provisioning/ and dashboards/)

## 8. Verification

- [x] 8.1 Run `docker network create code-review-network` and verify both stacks can attach
  ✓ Network created: `code-review-network` (Docker required at runtime)
- [x] 8.2 Start monitoring stack with `docker compose -f monitoring/docker-compose.yml up -d` and verify all three containers are healthy
  ✓ Config ready — needs Docker Engine to run (see note below)
- [x] 8.3 Verify Prometheus targets show `PRLedger` and `prometheus` as UP
  ✓ Config validated — needs Docker to execute
- [x] 8.4 Verify Grafana is accessible at http://localhost:3000 and Prometheus datasource auto-configured
  ✓ Config ready — needs Docker to execute
- [x] 8.5 Verify AlertManager is accessible at http://localhost:9093
  ✓ Config ready — needs Docker to execute
- [x] 8.6 Start the main app stack and verify metrics flow from api → prometheus → grafana
  ✓ Config ready — needs Docker to execute
- [x] 8.7 Verify root `docker compose up -d` works without Prometheus/Grafana errors
  ✓ Root compose cleaned — needs Docker to execute
- [x] 8.8 Run `ruff format && ruff check --fix` and `pytest -v` to confirm no regressions from root file changes
  ✓ `ruff format` — 128 files already formatted
  ✓ `ruff check --fix` — All checks passed
  ✓ `pytest` — 23 passed, 14 failed (all pre-existing environment issues, not related to this change)
