# Initial Assessment — SHEKARCHI (AVG CRM & MLS Core)

## Repository
- Path: /home/app/real
- Git: not a git repository (no .git). No branch/status available.
- Working tree contains local changes/untracked by filesystem (no git tracking).

## Stack
- Backend: FastAPI (Python 3.12 in image; host Python 3.14.4), SQLModel/SQLAlchemy, PostgreSQL 16 + PostGIS, Alembic, Redis.
- Frontend: Next.js 16 (App Router), React 19, TS 5.7, Tailwind v4, next-auth v5.
- Identity: Keycloak 26.0 realm `maskanchi`, custom theme `shekarchi`, SMS OTP SPI (Java/Maven).
- Services: db (postgis), redis, iran_locations (Node), keycloak-db, keycloak, backend, tiles (OSM), frontend.

## Entry points
- Backend: `app/main.py` (uvicorn app.main:app, port 8080), health `/api/v1/health`.
- Frontend: Next.js standalone server.js port 3000.
- Keycloak: 8080 internal, host 8082.

## Containers / ports
- db 5432, redis 6379, keycloak 8082->8080 + 9000 mgmt, backend 8080, tiles 8081->80, frontend 3000, iran_locations internal 3000.

## Migrations
- alembic/versions: 10 revisions from initial_schema to advisor_poi_and_reports.

## Tests
- pytest suite: ~30 test files under tests/.

## Keycloak SMS SPI
- keycloak-shekarchi-sms Maven project; providers: Kavenegar, MelliPayamak, Faraz, Fake. Fake enabled via SHEKARCHI_SMS_FAKE=true (dev only).

## Security gaps (initial)
- Default secrets in .env.example (JWT_SECRET change-me, DB passwords avg_secret).
- Keycloak admin password default admin/admin.
- SHEKARCHI_SMS_FAKE=true in compose (must be false in prod).
- LAN IP 192.168.31.168 hardcoded in compose; needs domain/env parametrization for Dokploy.
- DB ports published to host (5432, 6379) — should be internal only in prod.
- Backend mounts ./app and ./alembic as volumes (dev-style) — not production.
- Keycloak runs start-dev (dev mode) — must switch to production start.
- No TLS/HTTPS config; needs reverse proxy.

## Risks
- Data persistence volumes; no backup documented.
- OSM tiles require one-time import (~219MB).
- No CI/CD config present.
- No git repo → no version control/rollback via git.

## Acceptance criteria for next phase
- Human approval before any production changes.
