# Location integration — 2026-10-26

## Multi-city demand expansion (local, not deployed)

- Vendored the source-owned Sheypoor `/api/v10.0.0/location` response: 1,130
  cities, retrieved October 26, 2026. Mapping uses province + normalized city,
  not GIS numeric IDs. 330/344 catalog rows currently match; the remaining 14
  are explicitly `needs_mapping`, never guessed. Ambiguous names require IDs.
- Demand now collects one page each of residential sale and rent, with no
  phone extraction. Category locks and cooldown reuse existing jobs. Background
  execution is capped at two per process (not a distributed global limit).
- `GET /api/v1/properties/inventory-coverage` reports mapping coverage behind
  the license guard. Demand accepts up to 400 explicitly selected city rows;
  nationwide/empty selection still never starts a crawl.
- `/home/app/real/scripts/collect_empty_cities.py` provides an offline dry-run
  and a license-gated `--execute` mode that processes empty cities sequentially.
  It refuses to queue anything when PostgreSQL lacks `property.agency_id`.
  Run from project root using `python -m scripts.collect_empty_cities`.
- Live database remains at `4f8b2d1c6a90`, without `property.agency_id`.
  No migration/deploy or live batch was performed for this expansion.
- Validation also found an unrelated application import failure: CRM imports
  `ListingShare` from `app.models.agency_network`, where it is unavailable in
  the current worktree. Full application/OpenAPI validation is blocked there.
- Earlier Maragheh-only notes below describe the initial implementation and
  are superseded by the expanded coverage above. UI navigation/scope and
  authenticated end-to-end live collection remain unverified.

## Implemented foundation

- `/api/v1/gis/locations` exposes the existing vendored catalog with composite
  `province_id:local_city_id` IDs. The catalog contains 31 provinces and 344 city
  rows; local numeric city IDs are not globally unique. This is catalog coverage,
  **not** inventory or scraper coverage.
- Inventory, bargain, and neighbourhood-market endpoints accept repeated
  `city_ids` and `province_ids`; selections are unioned. Invalid IDs return 422.
  Legacy names remain supported and, when supplied together with IDs, narrow the
  ID scope. Market totals share the same location predicate as map rows.
- Existing text columns remain in use; no migration or backfill was run. Persian
  yeh/kaf, spaces and ZWNJ are folded for querying. Homonymous cities require a
  matching stored province for ID filtering; missing province is not guessed.
- The normalizer recognizes catalog names before rejecting neighbourhood-like
  patterns. Ingestion/submission enrich unambiguous catalog matches.
- Header selection no longer calls the scraper or changes the activity-city
  preference. Empty URL city selection means all inventory. Inventory, showcase,
  bargain-list and market-map views use URL scope. Map neighbourhood identities
  include the city. Lease drilldown uses one server-side paginated query.
- Query placeholder data is retained only across window changes, not across
  location or other filter changes.

## Explicitly incomplete

### On-demand empty-city collection (local implementation, October 26, 2026)

- Requirement changed: an empty, explicitly selected city should request
  collection rather than requiring an operator click. Header itself still has
  no scraper side effects; the inventory page mounts `EmptyMarketCollector`
  after a successful zero-count response.
- New authenticated/license-gated POST `/properties/ensure-inventory` rechecks
  unfiltered city inventory server-side, takes a per-city PostgreSQL transaction
  advisory lock, reuses active/recent jobs and enforces a 10-minute cooldown.
  Nationwide selection never queues work. Each attempt is bounded to one page,
  with phone collection disabled. It currently supports only independently
  checked Maragheh/Sheypoor mapping; other mappings return `unsupported` rather
  than guessing portal IDs. Initial collection is house/apartment sales only.
- UI polls collection every five seconds while active and invalidates inventory,
  bargain and market caches. Permission/license/network failures are displayed,
  not reported as successful starts. This is wired to the inventory page, not
  yet every standalone market/bargain page.
- Live read-only verification exposed that Sheypoor's bare search endpoint
  ignores location/category query parameters. Updated client to the city/category
  path, unwrapped sectioned results and preserved search-city identity in detail
  parsing. Local demand ingestion excludes out-of-city recommendation cards.
  Source check read 47 summaries, including national recommendations; a Maragheh
  detail retained city `مراغه`. No listings were persisted by that check.
- Validation: 69 offline backend tests, 14 frontend tests, TypeScript, targeted
  lint, production frontend build, OpenAPI route and Python compilation passed.
- NOT deployed: the live backend still has the previously documented schema
  incompatibility (`property.agency_id` absent), and its startup command runs
  migrations. Do not deploy the new frontend alone: its new POST needs the new
  backend. No schema migration or production ingestion job was run here.

- Header still uses legacy city-name URL parameters and province expansion, not
  the new ID catalog. Homonymous selections remain ambiguous in that legacy UI.
- Activity-city account persistence is intentionally separate; cross-route,
  cross-device persistence of the multi-location market selection is not done.
- Independent verified source mappings and coverage states (`unsupported`,
  `never_crawled`, `empty`, `failed`, `available`) are not implemented. Existing
  Divar IDs are marked unverified; Delta IDs must not be copied from Divar.
- Real database/source coverage has not been measured. No crawl was started.
- SQL normalization uses expressions over text columns. An ID-column/index
  migration needs a measured query plan and explicit ambiguous-row policy.

## Validation and environment

- Offline backend suite: 28 passed; database-backed grouped-query test excluded.
- Frontend targeted suite: 8 passed across Header, request-cache and map tests.
- Final serial typecheck and production build both exited 0; targeted frontend
  lint reported zero warnings/errors. Python compilation and diff whitespace
  checks passed.
- An attempted broader suite reached localhost PostgreSQL and failed before
  inserting its fixtures because `property.agency_id` is missing. Its transaction
  rolled back. No schema repair or operational migration was attempted.
- Frontend build completed with exit 0 (existing OpenTelemetry bundler warning).
  A concurrent typecheck raced generated `.next` files; serial rerun passed.
- Test logs are in `/tmp/real-location-*`. Initial resumed worktree status is in
  `/tmp/real-location-resumed-status.txt`; unrelated pre-existing edits remain.

## Rollback

### Ardabil follow-up — October 26, 2026

- Deployed frontend only, using `docker compose up -d --no-deps --no-build frontend`.
  Active image: `sha256:e0c5fa5d89b53eb1394aa5b3da77c816769667cf82e341b3ec0abfd1769b4dea`.
  Active Next build ID: `XUecVHvG5pQm-7_JPcE1U`. Local HTTP check returned 200;
  the new empty-state message was found in the running container's static bundle.
- Added regressions for selecting all Ardabil cities without crawl/activity-city
  side effects and for passing the selected cities to showcase queries (including
  clearing that restriction for nationwide scope). Targeted suite: 10 passed;
  TypeScript, targeted oxlint and production image build passed.
- Empty-state copy now describes missing stored inventory in the selected scope,
  rather than promising that a scheduled crawl will populate that location.
- Backend deployment deliberately stopped: Compose runs `alembic upgrade head`
  on startup, while the current database lacks `property.agency_id` required by
  the working-tree model. No migrations or schema changes were authorized here.
  Backend, DB and Keycloak image IDs and start times were unchanged after deployment.
  The new backend catalog image is therefore still NOT active.
- Authenticated end-to-end browser validation remains outstanding. This deployment
  is not confirmation that all backend ID-based location paths are live.
- Previous frontend image is tagged `real-frontend:before-location-fix`
  (`sha256:53f5e521bc539fb8acf1b29a982fed180f919cd3655a5051ac3d825f98d079b0`).
  To roll back only the frontend, retag that image as `real-frontend:latest` and
  recreate only frontend with `--no-deps --no-build`. Backend's previous image
  is also retained under `real-backend:before-location-fix`.

### Local code rollback

No database rollback is needed. Revert only this location patch (including the
new catalog module, URL hook, tests and Docker catalog COPY), preserving unrelated
local modifications. Do not use a whole-worktree reset: several touched files
already had unrelated modifications before this work.