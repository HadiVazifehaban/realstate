#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Compare Quarkus augmentation on one immutable local Keycloak image:
#   1) without a custom provider
#   2) with the SHEKARCHI provider JAR mounted read-only
# No network, published ports, Compose project, persistent volume, or existing
# container/image is modified. Each docker run is disposable (--rm).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_REF="quay.io/keycloak/keycloak:26.0"
PROVIDER_JAR="$PROJECT_DIR/target/keycloak-shekarchi-sms-1.0.0.jar"
RESULTS="$(mktemp -d "/tmp/shekarchi-kc-compare.XXXXXX")"
if [[ -n "${KC_IMAGE-}" ]]; then IMAGE_REF="$KC_IMAGE"; fi
if [[ -n "${PROVIDER_JAR-}" ]]; then PROVIDER_JAR="$PROVIDER_JAR"; fi

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 2; }

mkdir -p "$RESULTS"
chmod 700 "$RESULTS"

command -v docker >/dev/null || fail 'Docker CLI is unavailable'
docker info >/dev/null 2>&1 || fail 'Docker daemon is inaccessible; no permission changes attempted'
[[ -s "$PROVIDER_JAR" ]] || fail "Provider JAR not found: $PROVIDER_JAR"

# Resolve the tag once. Both tests use this immutable image ID even if the tag
# is moved while the script is running.
IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE_REF" 2>/dev/null)" || \
  fail "Image is not present locally; refusing to pull or change image state: $IMAGE_REF"
[[ "$IMAGE_ID" =~ ^sha256:[0-9a-f]{64}$ ]] || fail 'Docker returned an unexpected image ID'

printf 'Image ref: %s\nImage ID: %s\n' "$IMAGE_REF" "$IMAGE_ID" | tee "$RESULTS/image.txt"
sha256sum "$PROVIDER_JAR" | awk '{print "Provider JAR SHA-256: "$1}' | tee "$RESULTS/provider-sha256.txt"

set +e
docker run --rm --pull=never --network none "$IMAGE_ID" --version \
  >"$RESULTS/image-version.log" 2>&1
VERSION_STATUS=$?
set -e
printf 'Version command: %s\n' "$([[ $VERSION_STATUS -eq 0 ]] && echo PASS || echo FAIL)" | tee "$RESULTS/version-status.txt"
cat "$RESULTS/image-version.log"

set +e
docker run --rm --pull=never --network none "$IMAGE_ID" build --verbose \
  >"$RESULTS/build-without-provider.log" 2>&1
BASE_STATUS=$?
docker run --rm --pull=never --network none \
  --mount "type=bind,src=$PROVIDER_JAR,dst=/opt/keycloak/providers/shekarchi-sms.jar,readonly" \
  "$IMAGE_ID" build --verbose \
  >"$RESULTS/build-with-provider.log" 2>&1
PROVIDER_STATUS=$?
set -e

if (( BASE_STATUS == 0 )); then BASE_RESULT=PASS; else BASE_RESULT=FAIL; fi
if (( PROVIDER_STATUS == 0 )); then PROVIDER_RESULT=PASS; else PROVIDER_RESULT=FAIL; fi

printf '\nBUILD WITHOUT PROVIDER: %s (exit=%d)\n' "$BASE_RESULT" "$BASE_STATUS"
printf 'Log: %s\n' "$RESULTS/build-without-provider.log"
printf 'BUILD WITH SHEKARCHI JAR: %s (exit=%d)\n' "$PROVIDER_RESULT" "$PROVIDER_STATUS"
printf 'Log: %s\n' "$RESULTS/build-with-provider.log"
printf 'Results directory: %s\n' "$RESULTS"

if (( VERSION_STATUS != 0 )); then
  printf 'OVERALL: FAIL (could not record Keycloak/Java version)\n'
  exit 1
elif (( BASE_STATUS == 0 && PROVIDER_STATUS == 0 )); then
  printf 'OVERALL: PASS (both builds succeeded on image %s)\n' "$IMAGE_ID"
  exit 0
elif (( BASE_STATUS != 0 && PROVIDER_STATUS != 0 )); then
  printf 'OVERALL: FAIL (both builds failed; inspect base-image/bootstrap log first)\n'
  exit 1
elif (( BASE_STATUS == 0 && PROVIDER_STATUS != 0 )); then
  printf 'OVERALL: FAIL (failure is associated with provider-present case; this alone does not distinguish JAR contents, ServiceLoader, or provider path)\n'
  exit 1
else
  printf 'OVERALL: FAIL (provider build passed while provider-free baseline failed; compare logs and verify image behavior)\n'
  exit 1
fi
