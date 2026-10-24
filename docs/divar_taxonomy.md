# Divar Taxonomy & Data Schemas (Phase 2)

Reference for the ingestion engine. The scraper must tolerate Divar's two
naming layers and the three widget shapes documented here.

## 1. City / district addressing

Two layers must be reconciled per request:

| Layer | Example |
|---|---|
| **Web slug** (what a user types in `SCRAPER_CITIES`) | `tehran`, `saadat-abad` |
| **API id** (what `/v8/postlist/w/search` requires) | `city_ids: [1]`, `district: {"int": {"value": [1529]}}` |

`app/services/scraper/cities.py` is the single source of truth:

```python
from app.services.scraper import cities
cities.resolve_city_id("tehran")        # -> 1
cities.resolve_city_id("تهران")          # Persian labels work too
cities.resolve_district_ids("tehran", ["tehran-saat-abad"])  # -> [1529]
```

Unknown values raise `UnknownCityError` / `UnknownDistrictError` listing the
valid slugs, and the trigger endpoint turns that into **422** before a job is
created — a typo in `SCRAPER_CITIES` can never become a silent empty scrape.

> **ID provenance:** the registry ids are Divar-internal and are **not yet
> verified against the live API** (this environment gets `403 AccessDenied`
> from `api.divar.ir`). Every entry carries `is_verified=False`, the client
> logs a warning when using one, and the registry can be checked/refreshed:
>
> ```bash
> python -m app.cli.divar_cities list
> python -m app.cli.divar_cities show tehran
> python -m app.cli.divar_cities verify tehran   # live search; needs a
>                                                # Divar-accepted egress IP
> ```

## 2. Two naming layers

| Layer | Where it appears | Example |
|---|---|---|
| **Web (URL slugs)** | `https://divar.ir/s/{city}/{category}[/{district}]` | `buy-apartment` |
| **API / internal** | `category` field sent to `api.divar.ir/v8/*` | `apartment-sell` |

Both map to the same domain values. `map_category()` accepts either, and falls
back to ordered keyword matching for unknown slugs.

### Category tree

```text
real-estate (املاک)
├── فروش مسکونی      buy-residential / residential-sell
│   ├── آپارتمان      buy-apartment       / apartment-sell
│   ├── خانه و ویلا  buy-villa           / house-villa-sell
│   └── زمین و کلنگی buy-old-house       / plot-old          -> LAND
├── اجاره مسکونی     rent-residential / residential-rent
│   ├── آپارتمان      rent-apartment      / apartment-rent
│   └── خانه و ویلا  rent-villa          / house-villa-rent
├── فروش اداری       buy-commercial-property / commercial-sell
│   ├── دفتر کار      buy-office          / office-sell       -> OFFICE
│   ├── مغازه         buy-store           / store-sell        -> STORE
│   └── صنعتی         buy-industrial-agricultural-property  -> INDUSTRIAL
├── اجاره اداری      rent-commercial-property / commercial-rent
│   └── (office / store / industrial variants)               -> RENT
├── اجاره کوتاه‌مدت   temporary-rent
│   ├── سوئیت و اتاق suite-apartment                         -> SUITE + RENT
│   ├── ویلا و باغ    villa
│   └── دفتر و اشتراکی
└── خدمات و پروژه‌ها  real-estate-services
    ├── مشارکت در ساخت construction-partnership   (non-transferable)
    └── پیش‌فروش        pre-sell-home              (non-transferable)
```

`is_transferable_category()` flags the service/project slugs so the Phase 3
matching engine can de-prioritise them.

## 3. Post card (search feed)

| Field | Meaning |
|---|---|
| `token` | unique post id → `property.external_id` (dedupe key) |
| `title` | listing title |
| `top_description_text` | publish time + district ("دقایقی پیش در سعادت‌آباد") |
| `middle_description_text` | quick specs (area • rooms • build year) |
| `bottom_description_text` | **price line** (total / per-meter / deposit) |
| `image_url` | cover image |
| `district`, `city` | geo keys for PostGIS + content hash |
| `has_chat` | Divar chat enabled |
| `red_text` | urgency tags ("فوری") |

## 4. Post detail

```json
{
  "token": "gZ1234AB",
  "category": "apartment-sell",
  "city": "tehran",
  "district": "saadat-abad",
  "contact": {
    "phone": "0912xxxxxxx",
    "business_type": "real-estate-business",
    "agent_name": "املاک نام‌آوران",
    "slug": "amlak-namavaran"
  },
  "widgets": {
    "list_data": [
      {"title": "متراژ", "value": "۱۱۰"},
      {"title": "ساخت", "value": "۱۴۰۱"},
      {"title": "طبقه", "value": "۳ از ۵"}
    ],
    "amenities": [{"title": "آسانسور", "available": true}],
    "financial": {
      "total_price": 12500000000,
      "price_per_meter": 113636000,
      "deposit": null,
      "monthly_rent": null,
      "convertible": false
    },
    "location": {"latitude": 35.7812, "longitude": 51.3725, "radius": 150},
    "images": ["https://s100.divarcdn.com/.../1.jpg"]
  }
}
```

### Three widget shapes (each needs its own parser)

| Shape | Example | Handled by |
|---|---|---|
| label/value rows | `{"title": "متراژ", "value": "۱۱۰"}` | `collect_label_value_pairs()` |
| amenity rows | `{"title": "آسانسور", "available": true}` | `collect_amenities()` |
| structured numerics | `financial: {...}` | `find_financial()` |

Gotchas encoded in the parser:
- `طبقه` carries **"۳ از ۵"** → `floor=3`, `total_floors=5` (`parse_floor_and_total`).
- `ساخت` is the build-year label (not `سال ساخت`).
- `convertible` / "توافقی" means negotiable → `price_is_convertible`, price `None`.
- For rentals the generic `قیمت` is the **deposit**, not the total.
- `location.radius` (~150 m) marks Divar's coordinate fuzzing.
- Coordinates are `(latitude, longitude)`; PostGIS `POINT` is `(lng, lat)`.
- `contact.phone` may be absent without an authenticated session; the
  dedicated extractor (`phone_extractor`) handles that path.

## 5. Mapping to PostGIS / CRM

| Divar | Target |
|---|---|
| `token` | `property.external_id` (unique) |
| `city` + `district` + area + floor + rounded price | `property.content_hash` (SHA256) |
| `widgets.location` | `location` = `SRID=4326;POINT(lng lat)` |
| `category` | `property_type` + `deal_type` |
| `contact.phone` | encrypted into `property_owner_pii` (never the property row) |
| `widgets.*` | physical/financial columns; full payload kept in `raw_data` |

## 6. Scheduled autonomous ingestion (Phase 2b)

`app/services/scraper_scheduler.py` sweeps `SCRAPER_CITIES x
SCRAPER_CATEGORIES` on an interval, creating one `ScrapeJob` per pair with
`trigger=SCHEDULED`.

```bash
SCRAPER_SCHEDULER_ENABLED=false          # off by default
SCRAPER_SCHEDULE_INTERVAL_MINUTES=60
SCRAPER_SCHEDULE_JITTER_SECONDS=90       # de-syncs N workers
SCRAPER_SCHEDULE_INITIAL_DELAY_SECONDS=30
SCRAPER_SCHEDULE_MAX_PAGES=3
SCRAPER_SCHEDULE_SKIP_OVERLAPPING=true
```

Four safety rules:

1. **License gate** — `sync_license_from_disk().is_usable` is checked every
   tick; an unlicensed node never schedules (same contract as `LicenseGuard`).
2. **Single runner** — a Postgres advisory lock (`pg_try_advisory_lock`) means
   only one worker schedules a tick even under `--workers 4`. On SQLite the
   lock is a no-op.
3. **No overlap** — a city/category with a PENDING or RUNNING job is skipped,
   so a slow crawl cannot pile up.
4. **Self-healing loop** — a failing tick is logged and the next interval still
   runs; `stop()` is awaited on shutdown.

## 7. Dashboard statistics

`GET /api/v1/scraper/stats?hours=24` (license-gated) returns one payload with
everything the Phase 4 operations panel needs:

| Field | Meaning |
|---|---|
| `jobs` | totals per status in the window |
| `items` | found / new / duplicate / failed sums |
| `rates` | `new` + `duplicate` + `failure` (sum to 1.0) |
| `health[]` | per city+category: runs completed vs failed, dup/failure rate, last run, `healthy` flag |
| `stuck[]` | pairs still PENDING/RUNNING and for how many minutes |
| `recent_errors[]` | latest FAILED jobs, message truncated to 200 chars |

```bash
curl "http://localhost:8080/api/v1/scraper/stats?hours=24"
curl "http://localhost:8080/api/v1/scraper/stats?hours=168&include_details=false"
```

Everything is aggregated in SQL (`GROUP BY`), so cost stays flat as
`scrape_job` grows. `hours` (1–720) applies to both `jobs` and `health`, so the
totals and the per-city panel always describe the same slice of time.

`healthy` means *at least one run succeeded and none failed* — a job that
finished **because it failed** still has `finished_at` set and must not read as
healthy.

`app/services/scraper_scheduler.py` sweeps `SCRAPER_CITIES x
SCRAPER_CATEGORIES` on an interval, creating one `ScrapeJob` per pair with
`trigger=SCHEDULED`.

```bash
SCRAPER_SCHEDULER_ENABLED=false          # off by default
SCRAPER_SCHEDULE_INTERVAL_MINUTES=60
SCRAPER_SCHEDULE_JITTER_SECONDS=90       # de-syncs N workers
SCRAPER_SCHEDULE_INITIAL_DELAY_SECONDS=30
SCRAPER_SCHEDULE_MAX_PAGES=3
SCRAPER_SCHEDULE_SKIP_OVERLAPPING=true
```

Four safety rules:

1. **License gate** — `sync_license_from_disk().is_usable` is checked every
   tick; an unlicensed node never schedules (same contract as `LicenseGuard`).
2. **Single runner** — a Postgres advisory lock (`pg_try_advisory_lock`) means
   only one worker schedules a tick even under `--workers 4`. On SQLite the
   lock is a no-op.
3. **No overlap** — a city/category with a PENDING or RUNNING job is skipped,
   so a slow crawl cannot pile up.
4. **Self-healing loop** — a failing tick is logged and the next interval still
   runs; `stop()` is awaited on shutdown.

| Divar | Target |
|---|---|
| `token` | `property.external_id` (unique) |
| `city` + `district` + area + floor + rounded price | `property.content_hash` (SHA256) |
| `widgets.location` | `location` = `SRID=4326;POINT(lng lat)` |
| `category` | `property_type` + `deal_type` |
| `contact.phone` | encrypted into `property_owner_pii` (never the property row) |
| `widgets.*` | physical/financial columns; full payload kept in `raw_data` |