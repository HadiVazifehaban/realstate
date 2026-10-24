#!/bin/bash
# Build the SPI JAR and deploy it into the running Keycloak container.
#
# Keycloak (Quarkus, 26.x) discovers providers in /opt/keycloak/providers/,
# then re-builds its augmented classes on `kc.sh build`. In start-dev mode the
# build step is cheap, but it is still required before a restart, or the
# provider (and its theme-resources/templates/shekarchi/*.ftl) will not load.
set -euo pipefail
cd "$(dirname "$0")/.."

CONTAINER="${KEYCLOAK_CONTAINER:-avg_keycloak}"
PROVIDERS_DIR="/opt/keycloak/providers"

mvn clean package -DskipTests
JAR=$(find target -name "keycloak-shekarchi-sms-*.jar" | head -1)
echo "Built: $JAR"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Keycloak container '$CONTAINER' is not running." >&2
  echo "Start it first (docker compose up -d keycloak), then re-run this script." >&2
  exit 1
fi

echo "Deploying to $CONTAINER:$PROVIDERS_DIR ..."
docker exec "$CONTAINER" sh -c "rm -f $PROVIDERS_DIR/keycloak-shekarchi-sms-*.jar"
docker cp "$JAR" "$CONTAINER:$PROVIDERS_DIR/"

echo "Running kc.sh build inside $CONTAINER ..."
docker exec "$CONTAINER" /opt/keycloak/bin/kc.sh build

echo "Restarting $CONTAINER to pick up the provider ..."
docker compose restart keycloak

echo "Deployed: $JAR"
echo "Verify with ./scripts/health-check.sh"
