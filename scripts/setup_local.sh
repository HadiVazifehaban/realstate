#!/usr/bin/env bash
# =============================================================================
#  AVG CRM & MLS Core - Local Node bootstrap
#
#  Brings a fresh real-estate office machine to a running state:
#    1. creates a Python virtualenv + installs dependencies
#    2. creates .env from the template
#    3. starts PostgreSQL 16 + PostGIS (docker compose)
#    4. applies Alembic migrations
#    5. generates the license signing key pair (public key stays here)
#
#  Usage:  ./scripts/setup_local.sh
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
# The default index may be restricted in some networks; override with PIP_INDEX_URL.
PIP_INDEX_ENV="${PIP_INDEX_URL:-https://pypi.org/simple}"
VENV_DIR=".venv"

echo "==> [1/5] Creating virtualenv ($VENV_DIR)"
if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
echo "==> Installing dependencies from $PIP_INDEX_ENV"
"$VENV_DIR/bin/pip" install -q -i "$PIP_INDEX_ENV" \
  --trusted-host pypi.org --trusted-host files.pythonhosted.org \
  -r requirements.txt

echo "==> [2/5] Preparing .env"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    created .env from template (review it!)"
else
  echo "    .env already exists, leaving untouched"
fi

echo "==> [3/5] Starting PostgreSQL + PostGIS"
docker compose up -d db
echo -n "    waiting for the database"
for _ in $(seq 1 60); do
  if docker compose exec -T db pg_isready -U avg -d avgcrm >/dev/null 2>&1; then
    echo " ...ready"; break
  fi
  echo -n "."
  sleep 2
done

echo "==> [4/5] Applying Alembic migrations"
"$VENV_DIR/bin/alembic" upgrade head

echo "==> [5/5] Generating license key pair (if missing)"
if [ ! -f data/keys/license_public.pem ]; then
  "$VENV_DIR/bin/python" -m app.cli.license_tool keygen --out-dir data/keys
else
  echo "    key pair already present"
fi

echo
echo "======================================================================"
echo " AVG CRM & MLS Core local node is ready."
echo " Machine fingerprint (send this to AVG to obtain a license):"
"$VENV_DIR/bin/python" -m app.cli.license_tool fingerprint | sed 's/^/   /'
echo
echo " Start the API + LAN workspace:"
echo "   ./scripts/dev.sh"
echo "======================================================================"
