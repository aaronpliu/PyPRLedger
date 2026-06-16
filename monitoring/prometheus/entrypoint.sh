#!/bin/sh
# ───────────────────────────────────────────────────────────
# Prometheus Entrypoint
# ───────────────────────────────────────────────────────────
# Reads prometheus.template.yml, substitutes the scrape target
# placeholder with the PRLEDGER_SCRAPE_TARGET env var value,
# writes the final config to a temp location, then execs
# Prometheus with that config.
# ───────────────────────────────────────────────────────────
set -e

TEMPLATE_FILE="/etc/prometheus/prometheus.template.yml"
CONFIG_FILE="/etc/prometheus/prometheus.yml"
TARGET="${PRLEDGER_SCRAPE_TARGET:-api:8000}"

echo "PRLedger scrape target: ${TARGET}"

# Substitute placeholder with actual target value
sed "s/__PRLEDGER_SCRAPE_TARGET__/${TARGET}/g" "$TEMPLATE_FILE" > "$CONFIG_FILE"

echo "Config generated: ${CONFIG_FILE}"

# Exec Prometheus
exec /bin/prometheus \
  --config.file="$CONFIG_FILE" \
  --storage.tsdb.path="/prometheus" \
  --web.console.libraries=/usr/share/prometheus/console_libraries \
  --web.console.templates=/usr/share/prometheus/consoles \
  --web.enable-lifecycle \
  --storage.tsdb.retention.time="${PROMETHEUS_RETENTION_TIME:-15d}" \
  --storage.tsdb.retention.size="${PROMETHEUS_RETENTION_SIZE:-10GB}"
