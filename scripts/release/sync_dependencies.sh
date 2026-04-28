#!/usr/bin/env bash
# Synchronize all dependencies (backend + frontend)

set -e

echo "=== Synchronizing Python dependencies ==="
uv sync --all-extras

echo ""
echo "=== Synchronizing frontend dependencies ==="
cd frontend
npm install
cd ..

echo ""
echo "✓ Dependencies synchronized successfully"
