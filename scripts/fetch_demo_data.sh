#!/usr/bin/env bash
# fetch_demo_data.sh — download the arktrace demo bundle from R2 (no credentials required).
#
# Downloads candidate_watchlist.parquet, composite_scores.parquet,
# causal_effects.parquet, and validation_metrics.json into data/processed/.
# These files are enough to run the Streamlit dashboard without a local pipeline run.
#
# Usage:
#   bash scripts/fetch_demo_data.sh
#
# Requirements: uv must be installed (https://docs.astral.sh/uv/)
# No R2 credentials are needed — the demo bundle is publicly accessible.
#
# To also download the OpenSanctions DuckDB (needed for integration tests):
#   uv run python scripts/sync_r2.py pull-sanctions-db

set -euo pipefail

cd "$(dirname "$0")/.."

echo "Fetching arktrace demo data from R2..."
uv run python scripts/sync_r2.py pull-demo

echo ""
echo "Start the dashboard:"
echo "  uv run streamlit run src/ui/app.py"
echo "  open http://localhost:8501"
