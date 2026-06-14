## Context

The PRLedger application has rich Prometheus instrumentation (`MetricsCollector` in `src/utils/metrics.py` — 40+ metric families across 11 categories) exposed at `GET /api/metrics`. However, the monitoring infrastructure is disorganized:

- `prometheus.yml` sits at the project root
- `grafana/provisioning/` at the root with dashboard provider config but NO actual dashboards
- No AlertManager setup whatsoever
- Alert rule files (`alerts/*.yml`) are referenced in `prometheus.yml` but don't exist
- Prometheus and Grafana services are embedded in the main `docker-compose.yml` alongside api, mysql, redis, and nginx

This design consolidates all monitoring configuration into a self-contained `monitoring/` directory with a standalone Docker Compose file.

## Goals / Non-Goals

**Goals:**
- Single `monitoring/` folder containing all Prometheus, Grafana, and AlertManager config
- Standalone `monitoring/docker-compose.yml` that can deploy the full stack independently
- Prometheus alert rule files matching the app's rich metric surface
- AlertManager configuration with console + Slack receivers
- Starter Grafana dashboards (Overview, Review Analytics, Realtime Pipeline)
- Remove monitoring services from root `docker-compose.yml`
- Clean, production-ready defaults for retention, scrape intervals, and resource limits

**Non-Goals:**
- Not modifying the `MetricsCollector` class or any application code
- Not adding new application metrics (already comprehensive)
- Not configuring TLS/certificates for the monitoring stack (out of scope)
- Not setting up log aggregation (separate concern — Loki/ELK)
- Not configuring detailed per-endpoint alert thresholds (those emerge from usage)
- Not migrating existing Prometheus/Grafana data volumes

## Decisions

### Decision 1: Folder Structure — `monitoring/` at project root

**Chosen:** `monitoring/` at project root.

**Rationale:** The directory is self-documenting (`ls` reveals what it is), matches common conventions (Docker, Grafana, many open-source projects), and is at the same level as `src/`, `tests/`, `scripts/` — consistent with the project's flat structure.

Alternatives considered: `deploy/monitoring/` (too deep, adds unnecessary nesting), `infra/monitoring/` (less discoverable).

```
monitoring/
├── docker-compose.yml
├── .env.example
├── prometheus/
│   ├── prometheus.yml
│   └── rules/
│       ├── prledger_alerts.yml
│       └── infra_alerts.yml
├── alertmanager/
│   └── alertmanager.yml
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── prometheus.yml
    │   └── dashboards/
    │       └── dashboards.yml
    └── dashboards/
        ├── prledger_overview.json
        └── review_analytics.json
```

### Decision 2: Network Strategy — External Docker Network

**Chosen:** Both compose files declare `code-review-network` as an external network.

**Rationale:** Prometheus scrapes `api:8000` for metrics. If the monitoring stack and app stack are in different compose files, they must share a Docker network. Using an external network that both compose files reference (but neither creates) is the cleanest approach — user creates it once with `docker network create code-review-network`, and both stacks attach to it.

The monitoring `docker-compose.yml` documents this requirement clearly.

Alternatives considered:
- `network_mode: host` — only works on Linux, port conflicts
- Keeping monitoring in main compose — defeats the purpose of standalone
- Docker `network: code-review-network` declared inside monitoring compose with `external: false` — would fail if main stack creates it first

### Decision 3: AlertManager Receivers — Console (default) + Slack (optional via env)

**Chosen:** Default receiver logs to container stdout (visible via `docker logs`). Optional Slack receiver that activates when `SLACK_WEBHOOK_URL` env var is set.

**Rationale:** Console logging works out of the box with zero config. Slack integration is the most common dev team ask and can be toggled with a single environment variable — no config file changes needed.

Receivers follow a severity-based routing:
- `critical`: Slack + console (pages someone)
- `warning`: Slack only (team notification)
- `info`: Console only (debug visibility)

### Decision 4: Alert Rules — Two Rule Files, Partitioned by Concern

**Chosen:** Split alerts into `prledger_alerts.yml` (application-level) and `infra_alerts.yml` (infrastructure-level).

**Rationale:** Application owners and infrastructure owners are often different people. Separating them makes it easier to assign ownership, tune thresholds independently, and disable one category without touching the other.

| File | Alerts |
|------|--------|
| `prledger_alerts.yml` | API down, high error rate, high latency, review backlog growing, cache error rate > 0 |
| `infra_alerts.yml` | CPU > 80%, memory > 90%, disk < 10%, DB connections > 80% |

### Decision 5: Grafana Dashboards — Two Starter Dashboards (not three)

**Chosen:** Ship two dashboard JSON files for auto-provisioning:
1. **PRLedger Overview** — the main operational dashboard
2. **Review Analytics** — deep-dive into review process health

**Rationale:** SSE & Notifications dashboard is more maintenance overhead than value at this stage — those metrics can be inspected via Prometheus ad-hoc queries. Two dashboards keeps the initial scope manageable while covering the most important views. The provisioning config supports auto-loading from the `dashboards/` directory, so adding more later requires only a JSON file drop-in.

### Decision 6: Retention and Resource Defaults

**Chosen:**
- Prometheus: 15d retention (default), 256MB memory limit
- Grafana: 30d dashboard data retention in SQLite, 128MB memory limit
- AlertManager: 128MB memory limit, 120h silence + 30d retention

**Rationale:** Reasonable defaults for a development/staging environment. Users can override via environment variables in `.env`.

## Risks / Trade-offs

- **[Breaking Change] Removing monitoring from root compose**: Anyone running `docker compose up` from the project root will lose Prometheus/Grafana. → Document clearly in CHANGELOG and README. Leave a comment in the main `docker-compose.yml` referencing the new location.
- **[Network dependency] Standalone stack requires app stack to be running**: Prometheus will log errors if `api:8000` is unreachable. → Prometheus is resilient to this — it retries. Document startup order in the monitoring compose comments.
- **[Alert rule tuning] Alert thresholds are initial guesses**: Without production data, thresholds (e.g., "error rate > 5%") are starting points. → Design rule files with clear comments so they're easy to tune. Add a note that thresholds should be reviewed after the first week of production usage.
- **[Missing dashboards] No Grafana dashboards exist today**: Going from zero to two shipped dashboards requires writing JSON. → Use a known-good approach: build dashboards via Grafana UI first, export as JSON, then tweak for provisioning.
- **[No alert history] AlertManager starts from scratch**: No existing alert rule history or silenced alerts. → Acceptable — this is net new functionality.

## Open Questions

- Should we include a `docker-compose.override.yml` example for local dev (e.g., shorter retention, no resource limits)?
- Should the monitoring compose use `profiles` so components can be selectively enabled (e.g., `docker compose --profile no-alertmanager up`)?
- Do we want Grafana image rendering plugins for alert notification screenshots? (Adds ~200MB to image size.)
