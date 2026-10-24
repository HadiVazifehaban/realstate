#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAVEN="${MAVEN:-/home/app/.local/opt/apache-maven-3.9.9/bin/mvn}"
IMAGE_TAG="${IMAGE_TAG:-shekarchi-keycloak:unified-final-26.0.8-20261020-r2}"
BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/shekarchi-provider-build.XXXXXX")"
trap 'rm -rf "$BUILD_DIR"' EXIT

[[ -x "$MAVEN" ]] || { echo 'Maven executable unavailable' >&2; exit 1; }
cp "$ROOT/keycloak-shekarchi-sms/pom.xml" "$BUILD_DIR/pom.xml"
cp -a "$ROOT/keycloak-shekarchi-sms/src" "$BUILD_DIR/src"
cd "$BUILD_DIR"
"$MAVEN" -B -ntp -Dkeycloak.version=26.0.8 clean verify
JAR="$BUILD_DIR/target/keycloak-shekarchi-sms-1.0.0.jar"
[[ -s "$JAR" ]] || { echo 'Maven provider JAR missing' >&2; exit 1; }
install -D -m 644 "$JAR" "$ROOT/keycloak-shekarchi-sms/build-output/keycloak-shekarchi-sms-1.0.0.jar"
cd "$ROOT"
docker build --pull=false -f Dockerfile.keycloak-26.0.8-candidate -t "$IMAGE_TAG" .
docker image inspect --format 'IMAGE_ID={{.Id}} PLATFORM={{.Os}}/{{.Architecture}}' "$IMAGE_TAG"
