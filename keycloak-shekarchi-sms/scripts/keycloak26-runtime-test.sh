#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Disposable Keycloak 26 + PostgreSQL + authenticated Redis test stack.
# No project Compose file, production secret, host volume, or operational container is used.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAVEN="${MAVEN:-/home/app/.local/opt/apache-maven-3.9.9/bin/mvn}"
KEYCLOAK_VERSION="${KEYCLOAK_VERSION:-26.0.8}"
KC_BASE_IMAGE="${KC_BASE_IMAGE:-quay.io/keycloak/keycloak:$KEYCLOAK_VERSION}"
TEST_KEYCLOAK_IMAGE="${TEST_KEYCLOAK_IMAGE:-}"
MAVEN_OFFLINE="${MAVEN_OFFLINE:-0}"
PG_IMAGE="${PG_IMAGE:-postgres:16-alpine}"
REDIS_IMAGE="${REDIS_IMAGE:-redis:7-alpine}"
ALPINE_IMAGE="${ALPINE_IMAGE:-alpine:3.22}"
MAVEN_IMAGE="${MAVEN_IMAGE:-maven:3.9.9-eclipse-temurin-21}"
KC_PORT="${KC_PORT:-18089}"
REDIS_PORT="${REDIS_PORT:-16379}"
STACK="shekarchi-kc-test-$$"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/shekarchi-kc-test.XXXXXX")"
RESULTS="$TMP_DIR/results"
COMPOSE="$TMP_DIR/compose.yml"
DOCKERFILE="$TMP_DIR/Dockerfile"
mkdir -m 700 "$RESULTS"
KC_ADMIN_PASSWORD="$(openssl rand -hex 24)"
PG_PASSWORD="$(openssl rand -hex 24)"
REDIS_PASSWORD="$(openssl rand -hex 24)"
HMAC_SECRET="$(openssl rand -hex 32)"
E2E_USERNAME="kc_e2e_$(openssl rand -hex 4)"
E2E_PASSWORD="$(openssl rand -hex 24)"
AUTHJS_SECRET="$(openssl rand -hex 32)"
FRONTEND_DIR="$PROJECT_DIR/../frontend"
FRONTEND_IMAGE="${STACK}-frontend"
STACK_CREATED=0
IMAGE_TAG_RESERVED=0
KEYCLOAK_IMAGE="${STACK}-keycloak"
FRONTEND_IMAGE_RESERVED=0

fail() { echo "FAIL: $*" >&2; exit 1; }
redact() {
  sed -e "s/$KC_ADMIN_PASSWORD/[REDACTED]/g" \
      -e "s/$PG_PASSWORD/[REDACTED]/g" \
      -e "s/$REDIS_PASSWORD/[REDACTED]/g" \
      -e "s/$HMAC_SECRET/[REDACTED]/g" \
      -e "s/$E2E_PASSWORD/[REDACTED]/g" \
      -e "s/$AUTHJS_SECRET/[REDACTED]/g"
}

cleanup() {
  local original_status=$?
  local cleanup_failed=0
  local log_file
  trap - EXIT INT TERM

  if (( STACK_CREATED )); then
    if (( original_status != 0 )); then
      docker compose -p "$STACK" -f "$COMPOSE" logs --no-color >"$RESULTS/compose-services.log" 2>&1 || true
    fi
    if ! docker compose -p "$STACK" -f "$COMPOSE" down --volumes --remove-orphans >"$RESULTS/cleanup.log" 2>&1; then
      echo "CLEANUP_FAIL: Compose could not fully remove resources for project $STACK" >&2
      cleanup_failed=1
    fi
  fi
  if (( IMAGE_TAG_RESERVED )) && docker image inspect "$KEYCLOAK_IMAGE" >/dev/null 2>&1; then
    if ! docker image rm "$KEYCLOAK_IMAGE" >>"$RESULTS/cleanup.log" 2>&1; then
      echo "CLEANUP_FAIL: test image $KEYCLOAK_IMAGE remains or could not be removed" >&2
      cleanup_failed=1
    fi
  fi
  if (( FRONTEND_IMAGE_RESERVED )) && docker image inspect "$FRONTEND_IMAGE" >/dev/null 2>&1; then
    if ! docker image rm "$FRONTEND_IMAGE" >>"$RESULTS/cleanup.log" 2>&1; then
      echo "CLEANUP_FAIL: test frontend image $FRONTEND_IMAGE remains or could not be removed" >&2
      cleanup_failed=1
    fi
  fi

  if [[ -d "$RESULTS" ]]; then
    for log_file in "$RESULTS"/*.log; do
      [[ -f "$log_file" ]] || continue
      redact <"$log_file" >"$log_file.redacted" && mv "$log_file.redacted" "$log_file"
    done
  fi

  # The generated Compose and Dockerfile contain ephemeral credentials; always erase them.
  rm -f "$COMPOSE" "$DOCKERFILE" "$TMP_DIR/shekarchi-sms.jar"
  if (( cleanup_failed )); then
    echo "CLEANUP_REMAINS for Compose project $STACK:" >&2
    docker ps -a --filter "label=com.docker.compose.project=$STACK" --format '  container={{.Names}} status={{.Status}}' >&2 || true
    docker network ls --filter "label=com.docker.compose.project=$STACK" --format '  network={{.Name}}' >&2 || true
    docker volume ls --filter "label=com.docker.compose.project=$STACK" --format '  volume={{.Name}}' >&2 || true
    if docker image inspect "$KEYCLOAK_IMAGE" >/dev/null 2>&1; then echo "  image=$KEYCLOAK_IMAGE" >&2; fi
    original_status=1
  fi
  if (( original_status != 0 || cleanup_failed )) || [[ "${KEEP_TEST_RESULTS:-0}" == "1" ]]; then
    echo "Private test reports retained at: $RESULTS" >&2
    rm -rf "$TMP_DIR"/compose.yml "$TMP_DIR"/Dockerfile 2>/dev/null || true
  else
    rm -rf "$TMP_DIR"
  fi
  unset TOKEN KC_ADMIN_PASSWORD PG_PASSWORD REDIS_PASSWORD HMAC_SECRET E2E_PASSWORD AUTHJS_SECRET
  exit "$original_status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

[[ -x "$MAVEN" ]] || fail "Maven executable unavailable"
command -v docker >/dev/null || fail "Docker CLI unavailable"
command -v openssl >/dev/null || fail "openssl unavailable"
command -v python3 >/dev/null || fail "Python 3 unavailable"
docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin unavailable"
docker info >/dev/null 2>&1 || fail "Docker daemon inaccessible; no permission changes attempted"
[[ -f "$PROJECT_DIR/pom.xml" ]] || fail "SPI pom.xml missing"
[[ -f "$FRONTEND_DIR/Dockerfile" && -f "$FRONTEND_DIR/package-lock.json" ]] || fail "Frontend build inputs unavailable"

# Fail closed on any pre-existing resource with this generated Compose project label or image tag.
if [[ -n "$(docker ps -aq --filter "label=com.docker.compose.project=$STACK")" ]]; then fail "Compose project resource collision"; fi
if [[ -z "$TEST_KEYCLOAK_IMAGE" ]] && docker image inspect "$KEYCLOAK_IMAGE" >/dev/null 2>&1; then fail "Disposable test image tag collision"; fi
if docker image inspect "$FRONTEND_IMAGE" >/dev/null 2>&1; then fail "Disposable test image tag collision"; fi

# Pull explicit pinned-major test images only. No existing container is stopped or restarted.
for image in "$PG_IMAGE" "$REDIS_IMAGE" "$ALPINE_IMAGE" "$MAVEN_IMAGE" "python:3.12-alpine"; do
  docker image inspect "$image" >/dev/null 2>&1 || docker pull "$image" >/dev/null
 done
if [[ -n "$TEST_KEYCLOAK_IMAGE" ]]; then
  docker image inspect "$TEST_KEYCLOAK_IMAGE" >/dev/null 2>&1 || fail "Requested final Keycloak image is not present locally"
  KEYCLOAK_IMAGE="$TEST_KEYCLOAK_IMAGE"
else
  docker image inspect "$KC_BASE_IMAGE" >/dev/null 2>&1 || docker pull "$KC_BASE_IMAGE" >/dev/null
fi

# Build the SPI against the same Keycloak API version as the disposable runtime.
MAVEN_ARGS=(-B -ntp "-Dkeycloak.version=$KEYCLOAK_VERSION")
if [[ "$MAVEN_OFFLINE" == "1" ]]; then MAVEN_ARGS+=(-o); fi
if [[ "${SKIP_MAVEN_PACKAGE:-0}" != "1" ]]; then
  "$MAVEN" "${MAVEN_ARGS[@]}" clean package -DskipTests=false >"$RESULTS/maven-package.log" 2>&1 || {
    redact <"$RESULTS/maven-package.log" | tail -80 >&2
    fail "Maven package failed"
  }
fi
JAR="${PROVIDER_JAR:-$PROJECT_DIR/target/keycloak-shekarchi-sms-1.0.0.jar}"
[[ -s "$JAR" ]] || fail "Provider JAR was not produced"
# Make the provider readable by the Keycloak user before Docker COPY only when
# it is not already readable. Container-built artifacts may be host-readable
# but owned by root in rootless/user-namespace Docker setups, where chmod fails.
if [[ ! -r "$JAR" ]]; then chmod 644 "$JAR"; fi

# Establish the control case first: the pinned Keycloak image must augment
# without any custom provider before we attribute a failure to the SPI.
if [[ "${SKIP_BASE_BUILD:-0}" != "1" ]]; then
  if ! docker run --rm --entrypoint /opt/keycloak/bin/kc.sh "$KC_BASE_IMAGE" \
    build --db=postgres --health-enabled=true >"$RESULTS/keycloak-base-build.log" 2>&1; then
    redact <"$RESULTS/keycloak-base-build.log" | tail -100 >&2
    fail "Keycloak base image build without provider failed"
  fi
  echo "KEYCLOAK_BASE_BUILD_PASS"
else
  echo "KEYCLOAK_BASE_BUILD_SKIPPED (previous result reused)"
fi

if [[ -z "$TEST_KEYCLOAK_IMAGE" ]]; then
cat >"$DOCKERFILE" <<DOCKERFILE_EOF
FROM $KC_BASE_IMAGE
ENV KC_DB=postgres KC_HEALTH_ENABLED=true
COPY --chown=keycloak:keycloak --chmod=644 shekarchi-sms.jar /opt/keycloak/providers/shekarchi-sms.jar
COPY --chown=keycloak:keycloak shekarchi-theme /opt/keycloak/themes/shekarchi
RUN /opt/keycloak/bin/kc.sh --version && /opt/keycloak/bin/kc.sh build --verbose
DOCKERFILE_EOF
cp "$JAR" "$TMP_DIR/shekarchi-sms.jar"
chmod 644 "$TMP_DIR/shekarchi-sms.jar"
cp -a "$PROJECT_DIR/../keycloak/themes/shekarchi" "$TMP_DIR/shekarchi-theme"
IMAGE_TAG_RESERVED=1
docker build --progress=plain --tag "$KEYCLOAK_IMAGE" --file "$DOCKERFILE" "$TMP_DIR" >"$RESULTS/keycloak-build.log" 2>&1 || {
  redact <"$RESULTS/keycloak-build.log" >"$RESULTS/keycloak-build.log.redacted"
  mv "$RESULTS/keycloak-build.log.redacted" "$RESULTS/keycloak-build.log"
  echo "Keycloak augmentation diagnostics (sanitized; image: $KC_BASE_IMAGE):" >&2
  if ! grep -n -E -C 4 'ERROR|Exception|Caused by:|Failed to|failure|BUILD FAILED' "$RESULTS/keycloak-build.log" | tail -160 >&2; then
    tail -160 "$RESULTS/keycloak-build.log" >&2
  fi
  echo "Full sanitized Keycloak build diagnostics: $RESULTS/keycloak-build.log" >&2
  fail "Keycloak kc.sh build / provider augmentation failed"
}
else
  echo "KEYCLOAK_FINAL_IMAGE_REUSED: $KEYCLOAK_IMAGE"
fi

# Build a test-only frontend against the private Keycloak service DNS name.
# Stream a sanitized context so frontend/.env and all other .env files never
# enter Docker build context or image layers.
FRONTEND_IMAGE_RESERVED=1
tar -C "$FRONTEND_DIR" \
  --exclude='.env*' --exclude='**/.env*' --exclude=node_modules --exclude=.next --exclude=.git \
  -cf - . | docker build --progress=plain --tag "$FRONTEND_IMAGE" \
    --build-arg "NEXT_PUBLIC_KEYCLOAK_ISSUER=http://keycloak:8080/realms/shekarchi-runtime-test" \
    --build-arg NEXT_PUBLIC_TILE_URL= -f Dockerfile - \
    >"$RESULTS/frontend-build.log" 2>&1 || {
  redact <"$RESULTS/frontend-build.log" | tail -100 >&2
  fail "Test-only Auth.js frontend build failed"
}

# All services live only on this private Compose network; no host ports are published.
cat >"$COMPOSE" <<YAML
services:
  postgres:
    image: $PG_IMAGE
    environment:
      POSTGRES_DB: keycloak_test
      POSTGRES_USER: kc_test
      POSTGRES_PASSWORD: $PG_PASSWORD
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kc_test -d keycloak_test"]
      interval: 2s
      timeout: 2s
      retries: 30
    networks: [testnet]

  capture-init:
    image: $ALPINE_IMAGE
    command: ["sh", "-c", "chown 1000:0 /capture && chmod 700 /capture && touch /capture/otp /capture/captcha && chown 1000:0 /capture/otp /capture/captcha && chmod 600 /capture/otp /capture/captcha"]
    volumes: [otp_capture:/capture]
    networks: [testnet]
  redis:
    image: $REDIS_IMAGE
    command: ["redis-server", "--save", "", "--appendonly", "no", "--requirepass", "$REDIS_PASSWORD"]
    healthcheck:
      test: ["CMD-SHELL", "REDISCLI_AUTH='$REDIS_PASSWORD' redis-cli ping 2>/dev/null | grep -q PONG"]
      interval: 2s
      timeout: 2s
      retries: 30
    networks: [testnet]
  keycloak:
    image: $KEYCLOAK_IMAGE
    command: ["start-dev", "--http-port=8080", "--db=postgres", "--db-url=jdbc:postgresql://postgres:5432/keycloak_test", "--db-username=kc_test", "--db-password=$PG_PASSWORD", "--health-enabled=true"]
    environment:
      KC_BOOTSTRAP_ADMIN_USERNAME: kc_test_admin
      KC_BOOTSTRAP_ADMIN_PASSWORD: $KC_ADMIN_PASSWORD
      KC_HEALTH_ENABLED: "true"
      SHEKARCHI_ENV: test
      SHEKARCHI_SMS_FAKE: "true"
      SHEKARCHI_REDIS_URL: redis://:$REDIS_PASSWORD@redis:6379/0
      SHEKARCHI_OTP_REDIS_PREFIX: shekarchi:runtime-test
      SHEKARCHI_CAPTCHA_REDIS_PREFIX: shekarchi:runtime-test-captcha
      SHEKARCHI_OTP_HMAC_SECRET: $HMAC_SECRET
      SHEKARCHI_CAPTCHA_HMAC_SECRET: $HMAC_SECRET
      SHEKARCHI_TEST_CAPTURE_OTP: "true"
      SHEKARCHI_TEST_OTP_CAPTURE_PATH: /var/lib/shekarchi-test-capture/otp
      SHEKARCHI_TEST_CAPTURE_CAPTCHA: "true"
      SHEKARCHI_TEST_CAPTCHA_CAPTURE_PATH: /var/lib/shekarchi-test-capture/captcha
    volumes:
      - otp_capture:/var/lib/shekarchi-test-capture
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}
      capture-init: {condition: service_completed_successfully}
    healthcheck:
      test:
        - CMD-SHELL
        - >-
          bash -c 'exec 3<>/dev/tcp/127.0.0.1/9000 || exit 1;
          printf "GET /health/ready HTTP/1.0\r\nHost: localhost\r\n\r\n" >&3;
          IFS= read -r status <&3; [[ "\$\$status" == *"200"* ]]'
      interval: 3s
      timeout: 3s
      retries: 60
    networks: [testnet]
  frontend-test:
    image: $FRONTEND_IMAGE
    environment:
      NODE_ENV: production
      PORT: "3000"
      HOSTNAME: 0.0.0.0
      NEXT_PUBLIC_KEYCLOAK_ISSUER: http://keycloak:8080/realms/shekarchi-runtime-test
      NEXT_PUBLIC_AUTH_BYPASS: "false"
      KEYCLOAK_CLIENT_ID: shekarchi-runtime-browser
      AUTH_SECRET: $AUTHJS_SECRET
      NEXTAUTH_SECRET: $AUTHJS_SECRET
      AUTH_URL: http://frontend-test:3000
      NEXTAUTH_URL: http://frontend-test:3000
      AUTH_TRUST_HOST: "true"
    depends_on:
      keycloak: {condition: service_healthy}
    networks: [testnet]
networks:
  testnet:
    internal: true
volumes:
  otp_capture:
    name: ${STACK}-otp-capture
YAML
chmod 600 "$COMPOSE"

# Mark ownership before `up`: Compose can create some resources and still return non-zero.
# Cleanup remains scoped to this unique project name and removes only its resources.
STACK_CREATED=1
docker compose -p "$STACK" -f "$COMPOSE" up -d >"$RESULTS/compose-up.log" 2>&1 || {
  fail "Disposable test stack failed to start; details retained in private results"
}

# Run Maven in a disposable sidecar attached to the private Compose network.
# Service DNS (`redis`) is the only endpoint used; Docker Host loopback is not
# shared with the Codex execution namespace.
if ! docker run --rm --network "${STACK}_testnet" \
  --mount "type=bind,src=$PROJECT_DIR,dst=/workspace" \
  --mount "type=bind,src=/home/app/.m2/repository,dst=/root/.m2/repository,readonly" \
  --workdir /workspace \
  -e "SHEKARCHI_TEST_REDIS_URL=redis://:$REDIS_PASSWORD@redis:6379/0" \
  "$MAVEN_IMAGE" mvn -o -B -ntp "-Dkeycloak.version=$KEYCLOAK_VERSION" \
    -Dtest=OtpRedisStoreIntegrationTest,CaptchaChallengeStoreTest test >"$RESULTS/maven-redis-tests.log" 2>&1; then
  redact <"$RESULTS/maven-redis-tests.log" | tail -100 >&2
  fail "Maven verification or Redis integration tests failed"
fi

# Report actual Surefire totals. A skipped test is never counted as passed.
python3 - "$PROJECT_DIR/target/surefire-reports" <<'PY'
import glob,os,sys,xml.etree.ElementTree as ET
files=glob.glob(os.path.join(sys.argv[1], 'TEST-*.xml'))
expected={'TEST-com.shekarchi.auth.otp.OtpRedisStoreIntegrationTest.xml',
          'TEST-com.shekarchi.auth.captcha.CaptchaChallengeStoreTest.xml'}
reports={os.path.basename(path):ET.parse(path).getroot() for path in files if os.path.basename(path) in expected}
if set(reports) != expected:
    raise SystemExit('Redis integration test reports missing or ambiguous')
tests=sum(int(root.get('tests','0')) for root in reports.values())
failures=sum(int(root.get('failures','0')) for root in reports.values())
errors=sum(int(root.get('errors','0')) for root in reports.values())
skipped=sum(int(root.get('skipped','0')) for root in reports.values())
passed=tests-failures-errors-skipped
print(f"REDIS_CAPTCHA_INTEGRATION: PASS={passed} FAIL={failures+errors} SKIP={skipped} TOTAL={tests}")
if tests == 0 or failures or errors or skipped:
    raise SystemExit(1)
PY

# Poll Keycloak 26 readiness on its internal management interface (9000); it is not host-published.
ready=0
for _ in $(seq 1 90); do
  if docker compose -p "$STACK" -f "$COMPOSE" exec -T keycloak bash -c \
    'exec 3<>/dev/tcp/127.0.0.1/9000 || exit 1; printf "GET /health/ready HTTP/1.0\r\nHost: localhost\r\n\r\n" >&3; IFS= read -r status <&3; [[ "$status" == *"200"* ]]' \
    >/dev/null 2>&1; then ready=1; break; fi
  sleep 2
done
[[ "$ready" == 1 ]] || fail "Keycloak management readiness endpoint did not return HTTP 200"

# Provision a fresh realm and synthetic user, then run unified Password/SMS +
# Auth.js E2E against this stack's private, fresh PostgreSQL and Redis.
if ! docker run --rm -i --network "${STACK}_testnet" \
  -e "KC_ADMIN_PASSWORD=$KC_ADMIN_PASSWORD" \
  -e "SHEKARCHI_TEST_USERNAME=$E2E_USERNAME" -e "SHEKARCHI_TEST_PASSWORD=$E2E_PASSWORD" \
  -e SHEKARCHI_TEST_CAPTCHA_TTL=6 -e SHEKARCHI_TEST_OTP_TTL=30 \
  --mount "type=bind,src=$PROJECT_DIR/scripts/keycloak26-unified-test-setup.py,dst=/setup.py,readonly" \
  python:3.12-alpine python3 /setup.py >"$RESULTS/unified-test-setup.log" 2>&1; then
  redact <"$RESULTS/unified-test-setup.log" | tail -100 >&2
  fail "Unified Keycloak test realm setup failed"
fi
cat "$RESULTS/unified-test-setup.log"

if ! docker run --rm --network "${STACK}_testnet" \
  -e "SHEKARCHI_KC_BASE=http://keycloak:8080" \
  -e "SHEKARCHI_FRONTEND_BASE=http://frontend-test:3000" \
  -e "SHEKARCHI_TEST_REALM=shekarchi-runtime-test" \
  -e "SHEKARCHI_TEST_USERNAME=$E2E_USERNAME" -e "SHEKARCHI_TEST_PASSWORD=$E2E_PASSWORD" \
  -e "SHEKARCHI_TEST_CAPTCHA_USERNAME=${E2E_USERNAME}_captcha_probe" \
  -e SHEKARCHI_TEST_CAPTCHA_TTL=6 -e SHEKARCHI_TEST_OTP_TTL=30 \
  -e SHEKARCHI_TEST_OTP_CAPTURE_FILE=/test-capture/otp \
  -e SHEKARCHI_TEST_CAPTCHA_CAPTURE_FILE=/test-capture/captcha \
  --mount "type=volume,src=$STACK-otp-capture,dst=/test-capture" \
  --mount "type=bind,src=$PROJECT_DIR/scripts/keycloak26-unified-authjs-e2e.py,dst=/e2e.py,readonly" \
  python:3.12-alpine python3 /e2e.py >"$RESULTS/keycloak-unified-authjs-e2e.log" 2>&1; then
  redact <"$RESULTS/keycloak-unified-authjs-e2e.log" | tail -100 >&2
  fail "Unified Password/SMS Auth.js E2E failed"
fi
cat "$RESULTS/keycloak-unified-authjs-e2e.log"

# CAPTCHA storage must fail closed if Redis becomes unavailable.
docker compose -p "$STACK" -f "$COMPOSE" stop redis >"$RESULTS/redis-stop.log" 2>&1
if ! docker run --rm --network "${STACK}_testnet" \
  -e "SHEKARCHI_KC_BASE=http://keycloak:8080" \
  -e "SHEKARCHI_FRONTEND_BASE=http://frontend-test:3000" \
  -e "SHEKARCHI_TEST_REALM=shekarchi-runtime-test" \
  -e "SHEKARCHI_TEST_CAPTCHA_USERNAME=${E2E_USERNAME}_captcha_probe" \
  --mount "type=bind,src=$PROJECT_DIR/scripts/keycloak26-captcha-redis-down-smoke.py,dst=/smoke.py,readonly" \
  python:3.12-alpine python3 /smoke.py >"$RESULTS/captcha-redis-down.log" 2>&1; then
  redact <"$RESULTS/captcha-redis-down.log" | tail -100 >&2
  fail "CAPTCHA Redis-down fail-closed test failed"
fi
cat "$RESULTS/captcha-redis-down.log"
docker compose -p "$STACK" -f "$COMPOSE" start redis >"$RESULTS/redis-start.log" 2>&1

sha256sum "$JAR" >"$RESULTS/provider.sha256"
echo "Runtime classification: Keycloak 26.0.8, custom theme/provider, Redis/CAPTCHA integration, unified Password/SMS, OIDC/Auth.js and Redis-down fail-closed checks passed."
echo "Runtime and Redis cleanup will run automatically."
