#!/usr/bin/env bash
# =============================================================================
#  AVG CRM & MLS Core - issue a commercial license for an agency node.
#
#  Run this ON THE HUB (or wherever the RSA private key lives).
#
#  1. Collect the machine fingerprint on the office node:
#       ./scripts/generate_license.sh fingerprint
#  2. Issue a signed license bound to that fingerprint:
#       ./scripts/generate_license.sh issue "<fingerprint>" "املاک آفتاب" 365 10
#  3. Install the produced node.lic on the office node:
#       ./scripts/generate_license.sh install /path/to/node.lic
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

CMD="${1:-fingerprint}"

case "$CMD" in
  fingerprint)
    exec "$PY" -m app.cli.license_tool fingerprint
    ;;
  keygen)
    exec "$PY" -m app.cli.license_tool keygen --out-dir "${2:-data/keys}"
    ;;
  issue)
    FINGERPRINT="${2:?usage: issue <fingerprint> <agency> [days] [max-users]}"
    AGENCY="${3:?usage: issue <fingerprint> <agency> [days] [max-users]}"
    DAYS="${4:-365}"
    MAX_USERS="${5:-5}"
    exec "$PY" -m app.cli.license_tool issue \
      --agency "$AGENCY" --fingerprint "$FINGERPRINT" \
      --days "$DAYS" --max-users "$MAX_USERS" --out node.lic
    ;;
  verify)
    exec "$PY" -m app.cli.license_tool verify
    ;;
  install)
    TOKEN="${2:?usage: install <token-file>}"
    exec "$PY" -m app.cli.license_tool install "$TOKEN"
    ;;
  *)
    echo "usage: $0 {fingerprint|keygen|issue|verify|install} ..." >&2
    exit 2
    ;;
esac
