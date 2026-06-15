## Why

After consolidating metrics onto the shared Prometheus registry, many metrics are registered but never appear in Grafana dashboards because `prometheus_client` silently omits metrics from `generate_latest()` output until they receive an explicit value. The `startup()` method only initializes 4 of ~40 metric families to 0, leaving the rest invisible until a business operation (review, PR creation, etc.) triggers their first `.inc()` or `.set()` call. This means Grafana panels for "Open PRs and Backlog", "Active Reviewers", error rates, system resources, and others show "No data" until the first real action happens.

## What Changes

- Expand `MetricsCollector.startup()` to initialize all Gauge metrics to 0 with sensible default label values
- Initialize all Counter metrics with `.inc(0)` for sensible default label combinations so they appear at zero
- This ensures ALL metrics appear in `generate_latest()` output from the moment the app starts, even before any business operations occur

## Capabilities

### New Capabilities
*None — this is a bug fix, not a new capability.*

### Modified Capabilities
- `observability`: Update requirement for metrics initialization at startup to cover all registered metrics, not just a subset.

## Impact

- Only `src/utils/metrics.py` — the `startup()` method
- No API, config, or infrastructure changes
- All existing metrics that were already working continue to work
- Metrics that were missing now appear at zero value until real operations increment them
