# AVG CRM & MLS Core

**سامانه مدیریت املاک و شبکه همکاران (MLS) — هلدینگ AVG**
*Hybrid Edge-Cloud / Offline-First real-estate platform.*

- **Version:** `2.0.0-SCRAPER-HYBRID` (`pyproject.toml`)
- **Node modes:** `NODE_MODE=LOCAL` (نرم‌افزار مغازه) / `NODE_MODE=CLOUD_HUB` (هاب ابری)
- **AI engine:** `FEATURE_FLAG_AI_ENGINE=false` (AI-Ready stubs؛ پردازش قطعی و مکانی)
- **Auth:** `AUTH_MODE=KEYCLOAK` — Keycloak 26 realm `maskanchi` روی شبکه محلی
- **Backend:** FastAPI · Python 3.10+ · SQLModel/SQLAlchemy 2.0 · PostgreSQL 16 + PostGIS · Alembic · cryptography · Redis
- **Frontend:** Next.js 16 (App Router) · React 19 · TypeScript 5.7 · Tailwind v4 · shadcn/ui · next-auth v5 · TanStack Query/Table/Form · Leaflet · Recharts

> وضعیت: **فازهای ۱ تا ۵ پیاده‌سازی شد** — اسکفولدینگ، PostGIS، قفل لایسنس تجاری، رمزنگاری PII،
> موتور تطبیق، ارزش‌گذاری (AVM)، اسکرپر Divar/Sheypoor/Delta، بورد CRM، سهمیه PII،
> تم ورود کیکلاک و ۳۵۷ تست.

---

## Logical architecture

```
            ┌─────────────────────────────┐
            │   AVG CENTRAL CLOUD HUB     │  (NODE_MODE=CLOUD_HUB)
            │  Divar ingress · License    │
            │  Server · Cloud MLS Hub     │
            └───────────────┬─────────────┘
                            │  Sync Outbox / Heartbeat (E2E)
                            ▼
            ┌─────────────────────────────┐
            │   AVG ON-PREMISE NODE       │  (NODE_MODE=LOCAL)
            │  Local engine · Media vault │
            │  Encrypted PII · PostGIS    │  :8080  FastAPI
            └───────────────┬─────────────┘
                            │  LAN (192.168.31.168)
       ┌────────────────────┼───────────────────────┐
       ▼                    ▼                       ▼
  :3000 Next.js        :8082 Keycloak        :8081 OSM tile server
  office workspace     realm maskanchi       self-hosted raster tiles
                       (theme: shekarchi)
                                 │
                                 ▼
                    iran_locations (internal) — استان/شهر
```

## Repository layout

```
app/                FastAPI backend (port 8080)
  core/             config · licensing · crypto · security · logging
                    identity.py (Keycloak JWKS verification + role ladder)
  db/               session.py (async engine + session)
  models/           Property · ClientDemand · PropertyOwnerPII · PropertyMedia
                    SyncOutbox · NodeLicense · AgencyUser · OwnerAccessLog
                    PropertyMatch · PropertyPriceHistory · PropertyReport
                    ScrapeJob · PropertyBooking · PiiQuota · GeoCache · PoiCache
  services/         license · matching_engine · matching_repository
                    mls_masking · pii_vault · valuation · crm · market
                    keycloak_admin (user directory) · iran_locations
                    scraper/ (divar · sheypoor · delta + scheduler)
                    ingestion/ (pipeline · sanitizer · deduplicator)
                    osm_service · poi_service · geo · ai/stub
  api/v1/           health · license · users · crm · matching
                    properties · scraper · gis
  cli/              license_tool (keygen/fingerprint/issue/verify/install)
alembic/            env.py + 14 migrations
frontend/           Next.js 16 workspace (port 3000) — see frontend/AGENTS.md
keycloak/           realm-export.json + shekarchi login theme + README.md
services/
  iran-locations-api/  self-hosted استان/شهر dataset (internal, no host port)
tiles-data/         Geofabrik Iran extract for the OSM tile server
docs/               FINAL_PHASE_PLAN.md · divar_taxonomy.md
scripts/            setup_local.sh · dev.sh · generate_license.sh
                    keycloak_bootstrap.py (service-account roles + user profile)
tests/              unit + integration (357 tests)
docker-compose.yml  db · redis · iran_locations · keycloak · backend · tiles · frontend
```

---

## Quick start — full stack (docker compose)

```bash
# 1) Copy env templates and fill in the secrets
cp .env.example .env
cp frontend/env.example.txt frontend/.env

# 2) Keycloak realm imports on first boot; applies the service-account roles
#    and user-profile attributes the realm export cannot carry
docker compose up -d keycloak
python scripts/keycloak_bootstrap.py

# 3) Bring up everything (db · redis · iran_locations · keycloak · backend · tiles · frontend)
docker compose up -d --build
```

| Service | Port | Purpose |
| :--- | :--- | :--- |
| `frontend` | `3000` | Next.js office workspace |
| `backend` | `8080` | FastAPI engine + LAN API |
| `tiles` | `8081` | Self-hosted OSM raster tiles |
| `keycloak` | `8082` | OIDC identity provider |
| `db` | `5432` | PostgreSQL 16 + PostGIS |
| `redis` | `6379` | Sync/queue backend |
| `iran_locations` | internal | استان/شهر dataset (no host port) |

All services are pinned to the office machine's LAN IP `192.168.31.168` — the
Keycloak issuer, tile URL and frontend bundle all bake it in at build time, so
a stale `.env` cannot silently fall back to `localhost`. If the machine's
address ever changes, edit the literals in `docker-compose.yml`, `.env`,
`.env.example` and `frontend/.env` together.

**Map tiles** (one-time, needs internet):

```bash
mkdir -p tiles-data
curl -L -o tiles-data/region.osm.pbf https://download.geofabrik.de/asia/iran-latest.osm.pbf
docker compose run --rm tiles import
docker compose up -d tiles
# Tile URL: http://192.168.31.168:8081/tile/{z}/{x}/{y}.png
```

## Quick start — backend only (local office node)

```bash
# One command: venv + deps + .env + PostGIS (docker) + migrations + keys
./scripts/setup_local.sh

# Run the API (also serves the LAN workspace)
./scripts/dev.sh            # -> http://localhost:8080/api/v1/health
```

If your network blocks the default PyPI mirror, set `PIP_INDEX_URL` first:

```bash
PIP_INDEX_URL=https://pypi.org/simple ./scripts/setup_local.sh
```

Developer shortcuts: `make setup` · `make db` · `make migrate` · `make run`
· `make test` · `make license-fingerprint`.

## Manual setup

```bash
python3 -m venv .venv
PIP_INDEX_URL=https://pypi.org/simple .venv/bin/pip install -r requirements.txt

cp .env.example .env
docker compose up -d db redis
.venv/bin/alembic upgrade head

.venv/bin/python -m app.cli.license_tool keygen --out-dir data/keys
```

---

## Keycloak and the user directory

`/dashboard/users` is sourced from the **Keycloak realm**, not the local
`agency_user` table: the identity provider is the authority on who exists and
what tier they hold, so a user disabled in Keycloak no longer keeps an active
staff row. `agency_user` is still used for quota accounting and audit rows,
which have no business living in an external IdP.

With no Keycloak service account configured, the directory falls back to
`agency_user`, so a fresh clone works before Keycloak is ever started.

```bash
docker compose up -d keycloak          # realm imports on first boot
python scripts/keycloak_bootstrap.py   # REQUIRED, see below
```

Console: <http://192.168.31.168:8082> (`admin` / `admin` — change it).

Two things are **not** in `keycloak/realm-export.json` and cannot be, so
`scripts/keycloak_bootstrap.py` applies them. It is idempotent:

1. **The service account's roles.** A realm import silently drops the
   `clientRoles` block on a service-account user, so `maskanchi-admin-cli` gets
   no `realm-management` roles and every Admin REST call returns 403.
2. **The user profile attributes.** Keycloak 26 keeps that configuration
   outside the realm representation entirely. Without it, Keycloak *silently
   strips* `kyc_status`, `tenant_id`, `daily_pii_quota` and `phone` on any
   Admin REST write — a user invited from the dashboard would come out with no
   `kyc_status` and be refused by every API call.

Roles, clients, seed accounts and the sync details are in
[`keycloak/README.md`](keycloak/README.md).

Realm roles are translated to the internal ladder in `KEYCLOAK_ROLE_MAP`
(`app/core/identity.py`); a multi-role user resolves to the **highest** tier,
and an unknown role is ignored rather than trusted.

The login page uses the custom **shekarchi** theme (`keycloak/themes/shekarchi`),
bind-mounted read-only with `KC_THEME_CACHE=false` so CSS/FTL edits apply on a
plain page refresh. Its brand logo is
`keycloak/themes/shekarchi/login/resources/img/logo.png`.

## Frontend (office workspace)

Next.js 16 App Router dashboard served on the office LAN. Full reference in
[`frontend/AGENTS.md`](frontend/AGENTS.md).

```bash
cd frontend
bun install            # or: npm ci
bun run dev            # http://localhost:3000
bun run build          # production build
bun run typecheck      # tsc --noEmit
bun run lint           # oxlint
```

**Authentication** — `next-auth` v5 against the Keycloak realm
(`frontend/src/lib/auth/config.ts`). The `maskanchi-frontend` client is a
**public** client (PKCE), so no client secret is needed; the realm access token
is stashed on the session and forwarded to the FastAPI node as
`Authorization: Bearer …`. The FastAPI core is the sole enforcement point — it
re-verifies the token against the realm's JWKS and re-derives role/KYC from the
signed claims. The issuer is pinned to the LAN IP for the same reason as
everything else: a baked-in `localhost` would break the token exchange from
every phone on the network.

**Env** (`frontend/.env`, see `frontend/env.example.txt`) — `KEYCLOAK_CLIENT_ID`
(`maskanchi-frontend`), `KEYCLOAK_AUDIENCE` (`maskanchi-backend-api`),
`NEXT_PUBLIC_TILE_URL`, `NEXT_PUBLIC_NOMINATIM_URL`, `NEXT_PUBLIC_OSM_ENABLED`.
`NEXT_PUBLIC_AUTH_BYPASS=false` keeps the bypass off; the API server origin
stays server-side (`API_SERVER_ORIGIN`) so it never reaches the client bundle.

**Feature modules** (`frontend/src/features/`): `properties` (radar، جزییات
ملک، ویزارد ثبت ۳-مرحله‌ای) · `crm` (بورد ۵-ستونی DnD) · `map` (Leaflet) ·
`overview` · `users` · `kanban` · `chat` · `ai-chat` · `notifications` ·
`workspaces` · `billing` · `profile`.

Data fetching follows a strict layer per feature: `api/types.ts` →
`api/service.ts` → `api/queries.ts`, with React Query + `nuqs` for URL state.
Icons are centralised in `src/components/icons.tsx` — never import a tabler
icon directly.

## Commercial license lifecycle

The node is bound to physical hardware (`motherboard serial + CPU + MAC + machine-id`).
Licenses are **signed offline** with RSA-4096 and verified locally against an
embedded public key — no network round-trip is needed to boot the office.

```bash
# 1) On the office node — print its fingerprint hash
python -m app.cli.license_tool fingerprint

# 2) On the hub — sign a license bound to that fingerprint
python -m app.cli.license_tool issue \
    --agency "املاک آفتاب" \
    --fingerprint "<hash>" \
    --days 365 --max-users 10 \
    --out node.lic

# 3) On the office node — install + verify
python -m app.cli.license_tool install node.lic
python -m app.cli.license_tool verify
```

Statuses (`LicenseStatus`): `ACTIVE`, `GRACE_PERIOD`, `OFFLINE_GRACE_EXPIRED`,
`EXPIRED`, `LOCKED_HARDWARE_MISMATCH`, `NOT_INSTALLED`, `INVALID_SIGNATURE`.
Default offline grace period: **14 days** (`OFFLINE_GRACE_DAYS`).

---

## Security model

- **PII vault** — owner name/phone/address/pelak are encrypted with `cryptography.Fernet`
  using a per-agency key that never leaves the machine (`app/core/crypto.py`).
  Deterministic HMAC *blind indexes* allow exact-match search without decryption.
  A phone number is never stored or logged in plain text — only the encrypted
  value plus its blind index (`encrypted_contact_phone` + `blind_index_phone`).
- **Access logs** — every owner-PII access is recorded in `owner_access_log`.
- **PII quota** — per-agency daily reveal budget enforced through `pii_quota`,
  with the reveal-contact path rate-limited on top of the audit row.
- **MLS masking** — shared listings strip all owner fields and fuzz coordinates to a
  ~300 m radius (`app/services/mls_masking.py`).
- **RBAC** — seven-role ladder (`app/models/enums.py`); Keycloak realm roles map
  through `KEYCLOAK_ROLE_MAP`, highest tier wins, unknown roles are untrusted.
- **Passwords** — `scrypt` (stdlib); API tokens via JWT (HS256, `JWT_SECRET`).

Two architectural invariants that must not regress: `visit_date` never exists as
a column/schema/payload — a visit time lives only as a `LeadInteraction` of type
`VISIT_EVENT`; and a WebSocket never carries PII.

## Deterministic matching engine

Weighted, bounded score `Score = 0.40·S_geo + 0.35·S_price + 0.25·S_specs`
(`app/services/matching_engine.py`), designed for < 30 ms offline runs using
PostGIS `ST_Contains` / `ST_Distance` with GiST indexes. Persisted matches live
in `property_match` (`app/services/matching_repository.py`).

## Valuation / AVM

Deterministic price model with neighbourhood comparables and price-history
trend (`app/services/valuation.py`, `property_price_history`,
`property_report`). No ML inference — the AI engine is stubbed by design
(`FEATURE_FLAG_AI_ENGINE=false`) so every valuation is reproducible offline.

## Scrapers and ingestion

Multi-source listing ingestion (`app/services/scraper/`): **Divar**, **Sheypoor**
and **Delta**, each with its own client + parser + taxonomy, registered in
`registry.py` and driven by `scraper_scheduler.py`. The ingestion pipeline
(`app/services/ingestion/`) sanitises, then deduplicates with a spatial
Haversine score (merge threshold `0.78`) before a listing ever touches the DB.

Source precedence is fixed: مستقیم مالک (100) > دفتر (80) > اسکرپ (40)
(`submitter_type` on `Property`).

## GIS stack

OpenStreetMap-only, no API key required: Nominatim (geocoding), Overpass (POI),
and the self-hosted raster tile server on `:8081`. Province/city cascades read
the internal `iran_locations` service first and fall back to the inventory when
it is down. `geo_cache` / `poi_cache` keep repeat lookups off the network.

## Tests

```bash
.venv/bin/python -m pytest -q
# 357 tests collected
```

Integration tests (PostGIS spatial queries, license persistence, matching
persistence) run automatically when a migrated database is reachable and are
skipped otherwise. `make test` runs the same suite.

## Phase map

| Phase | Focus | Status |
| :--- | :--- | :--- |
| 1 | Scaffolding, PostGIS, license lock, PII crypto, Alembic | ✅ done |
| 2 | Scraper hybrid — Divar/Sheypoor/Delta ingestion, dedup, sync outbox | ✅ done |
| 3 | Matching engine, valuation/AVM, media vault, MLS masking, POI/GIS | ✅ done |
| 4 | Next.js 16 office workspace, Keycloak login, LAN access, OSM map | ✅ done |
| 5 | CRM 5-column board, PII quota + audit, visit bookings, user directory | ✅ done |
| 6 | Keycloak wire-up hardening, interactive map picker, theme polish | ⏳ see `docs/FINAL_PHASE_PLAN.md` |

---

## Branding

Site logo and favicon live in `frontend/public/brand/` (`logo.png`,
`logo-light.png`, `logo-dark.png`, `icon.png`), consumed by
`frontend/src/components/brand/logo.tsx` per resolved theme. The Keycloak login
logo is `keycloak/themes/shekarchi/login/resources/img/logo.png`. Because
`public/` is baked into the frontend image, a logo change requires
`docker compose build frontend`; the Keycloak theme is bind-mounted with theme
cache off, so its logo applies on refresh.

---

© AVG — گروه چشم‌انداز اوج فردا · `avgcrm.com` · `avgcrm.ir`
# realstate
