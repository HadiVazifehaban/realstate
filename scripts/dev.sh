#!/usr/bin/env bash
# =============================================================================
#  AVG CRM & MLS Core - run the local node API (serves the LAN workspace too)
#  Usage:  ./scripts/dev.sh           (defaults to 0.0.0.0:8080)
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"

exec .venv/bin/uvicorn app.main:app --host "$HOST" --port "$PORT" ${RELOAD:+--reload}
