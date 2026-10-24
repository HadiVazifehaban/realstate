# Deployment Guide

## Version Detection
Keycloak target: quay.io/keycloak/keycloak:26.0 (from docker-compose.yml)

## Build
```bash
docker build --pull -f keycloak-shekarchi-sms/Dockerfile.keycloak \
  -t shekarchi-keycloak:26.0.0 keycloak-shekarchi-sms
```

The multi-stage image build runs Maven tests and packaging, copies the exact
provider JAR into Keycloak 26.0.0, then runs `kc.sh build --db=postgres`.
No credentials or OTP configuration are baked into the image.

## Disposable Runtime Smoke Test
```bash
docker compose -f keycloak-shekarchi-sms/docker-compose.runtime-test.yml up --build
```
The test Compose file binds port 18089 to loopback and uses an isolated
temporary Redis. Stop it with `docker compose -f
keycloak-shekarchi-sms/docker-compose.runtime-test.yml down --volumes`.

The repository's normal Compose file now builds this image for its Keycloak
service. Applying that Compose change to a live container is a deployment and
must be reviewed and approved separately.

## Verification
Check logs for:
- Loaded SPI: shekarchi-sms
- Loaded providers for SPI shekarchi-sms
- Loaded authenticator factory: shekarchi-sms-authenticator
