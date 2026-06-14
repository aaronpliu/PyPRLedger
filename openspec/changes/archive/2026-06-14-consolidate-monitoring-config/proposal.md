## Why

Prometheus, Grafana, and AlertManager configuration is currently scattered across the project root (`prometheus.yml`, `grafana/`, referenced in `docker-compose.yml`) with no AlertManager setup at all. As the project grows, this makes it hard to manage, deploy independently, or hand off to DevOps. Consolidating everything into a single `monitoring/` folder with a standalone `docker-compose.yml` makes it self-documenting, independently deployable, and follows infrastructure-as-code best practices.

## What Changes

- Create a `monitoring/` directory at the project root containing all Prometheus + Grafana + AlertManager configuration
- Create a standalone `monitoring/docker-compose.yml` to deploy the full monitoring stack independently
- Remove Prometheus and Grafana services from the root `docker-compose.yml`
- Remove the root-level `prometheus.yml` and `grafana/` provisioning directories
- Create AlertManager configuration from scratch (currently absent)
- Create Prometheus alert rule files (currently referenced but non-existent — `alerts/*.yml`)
- Optionally create starter Grafana dashboard JSON files (provisioning config exists but dashboards are empty)
- Fix the Prometheus config's rule file path from `alerts/*.yml` → `prometheus/rules/*.yml`

## Capabilities

### New Capabilities
- `observability`: Centralized monitoring stack configuration covering metrics collection (Prometheus), visualization (Grafana), and alerting (AlertManager) for the PRLedger application.

### Modified Capabilities
*None — this is infrastructure config, not application behavior.*

## Impact

- **Root `docker-compose.yml`**: Prometheus, Grafana services and their volumes/networks removed
- **Root files removed**: `prometheus.yml`, `grafana/` directory (provisioning + dashboards)
- **New files**: Entire `monitoring/` directory tree
- **No application code changes**: The API's `/api/metrics` endpoint and `MetricsCollector` class remain untouched
- **Backward compatibility**: Existing deployments using the root `docker-compose.yml` will lose monitoring; they must switch to `monitoring/docker-compose.yml`
- **Network**: The standalone stack must be on the same Docker network as the app stack to scrape metrics
