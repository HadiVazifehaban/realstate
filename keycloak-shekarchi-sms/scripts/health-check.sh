#!/bin/bash
# Health-check the SPI deployment: JAR presence, provider discovery, and that
# the custom login theme still renders behind it.
set -uo pipefail
cd "$(dirname "$0")/.."

CONTAINER="${KEYCLOAK_CONTAINER:-avg_keycloak}"
KC_PORT="${KEYCLOAK_PORT:-8082}"
REALM="${KEYCLOAK_REALM:-maskanchi}"
FAIL=0

echo "== 1. JAR inside providers/ =="
if docker exec "$CONTAINER" sh -c 'ls /opt/keycloak/providers/keycloak-shekarchi-sms-*.jar' 2>/dev/null; then
  echo "OK: JAR present"
else
  echo "FAIL: JAR missing — run ./scripts/deploy.sh"; FAIL=1
fi

echo "== 2. Provider discovery in logs =="
if docker logs "$CONTAINER" 2>&1 | grep -E 'Loaded provider factory for SPI shekarchi-sms|shekarchi-sms' | tail -5; then
  echo "OK: SPI referenced in logs"
else
  echo "FAIL: no shekarchi-sms SPI in logs"; FAIL=1
fi

echo "== 3. Login page renders (custom shekarchi theme) =="
AUTH_URL="http://localhost:$KC_PORT/realms/$REALM/protocol/openid-connect/auth?client_id=shekarchi-frontend&redirect_uri=http%3A%2F%2Flocalhost%3A3000%2F&response_type=code&scope=openid&code_challenge_method=S256&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
HTML=$(curl -s -L --max-time 10 "$AUTH_URL" || true)
if echo "$HTML" | grep -q 'shekarchi'; then
  echo "OK: shekarchi theme markup present"
else
  echo "WARN: shekarchi marker not found (theme may still render via CSS only)"
fi

echo "== 4. Custom CSS reachable (resolve hashed theme path from login HTML) =="
CSS_HREF=$(echo "$HTML" | grep -o '/resources/[a-z0-9]*/login/shekarchi/css/shekarchi.css' | head -1)
if [ -n "$CSS_HREF" ] && curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
  "http://localhost:$KC_PORT$CSS_HREF" | grep -q 200; then
  echo "OK: shekarchi.css served (HTTP 200, $CSS_HREF)"
else
  echo "FAIL: shekarchi.css not served"; FAIL=1
fi

exit $FAIL
