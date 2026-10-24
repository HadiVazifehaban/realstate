# Dokploy Deployment — SHEKARCHI

## Services
db, redis, keycloak-db, keycloak, backend, frontend. Internal network only; only frontend/keycloak exposed via Dokploy domains.

## Required env vars
See `.env.example`. Production must set strong secrets: POSTGRES_PASSWORD, KEYCLOAK_DB_PASSWORD, KEYCLOAK_ADMIN_PASSWORD, JWT_SECRET, REDIS_PASSWORD, KEYCLOAK_PUBLIC_URL, KEYCLOAK_ISSUER, NEXT_PUBLIC_*.

## Steps
1. Create project in Dokploy, connect repo/branch.
2. Use docker-compose.prod.yml as compose source.
3. Set env vars in Dokploy.
4. Deploy.
5. Run migration: `docker compose exec backend alembic upgrade head` (or Dokploy exec).
6. Configure domains + HTTPS in Dokploy.
7. Verify health endpoints.
