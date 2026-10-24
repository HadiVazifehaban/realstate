# AVG CRM & MLS — مستند فنی پروژه

سامانهٔ مدیریت املاک و شبکهٔ همکاری مشاوران املاک AVG؛ شامل API، داشبورد وب، احراز هویت Keycloak، پایگاه دادهٔ مکانی و سرویس‌های زیرساختی. این مستند با ساختار مخزن و فایل‌های پیکربندی آن هماهنگ شده است؛ تنظیمات runtime را از فایل `.env` محلی بگیرید و هیچ secret واقعی را در مخزن ثبت نکنید.

> **وضعیت نسخه‌ها:** نسخه‌ها و قابلیت‌های runtime را با محیط مقصد تطبیق دهید. فایل‌های Compose توسعه و تولید پیکربندی‌های متفاوتی دارند؛ به‌ویژه نسخهٔ Keycloak، URLهای عمومی و تنظیمات SMS. این README جایگزین فایل `.env.example` یا راهنمای rollout تولید نیست.

## فهرست مطالب

- [نمای کلی معماری](#نمای-کلی-معماری)
- [ساختار مخزن](#ساختار-مخزن)
- [پیش‌نیازها](#پیشنیازها)
- [اجرای محلی با Docker Compose](#اجرای-محلی-با-docker-compose)
- [اجرای توسعه بدون Compose کامل](#اجرای-توسعه-بدون-compose-کامل)
- [تنظیمات و متغیرهای محیطی](#تنظیمات-و-متغیرهای-محیطی)
- [API و احراز هویت](#api-و-احراز-هویت)
- [داده، migration و پشتیبان‌گیری](#داده-migration-و-پشتیبانگیری)
- [ماژول‌های دامنه](#ماژولهای-دامنه)
- [فرانت‌اند](#فرانتاند)
- [Keycloak و افزونهٔ SMS/OTP](#keycloak-و-افزونهٔ-smsotp)
- [تست و کنترل کیفیت](#تست-و-کنترل-کیفیت)
- [استقرار تولید](#استقرار-تولید)
- [امنیت و عیب‌یابی](#امنیت-و-عیبیابی)
- [محدودیت مستند](#محدودیت-مستند)

## نمای کلی معماری

سامانه یک کدبیس مشترک برای دو نقش است: گرهٔ محلی دفتر (`NODE_MODE=LOCAL`) و هاب مرکزی (`NODE_MODE=CLOUD_HUB`). این دو نقش در `app/main.py` و تنظیمات `app/core/config.py` تعریف شده‌اند؛ جزئیات فعال‌سازی هر قابلیت را از تنظیمات و کد همان سرویس بررسی کنید.

```text
مرورگر ── Next.js :3000 ── API داخلی Next.js ── FastAPI :8080
    │              │                                  │
    └── OIDC ── Keycloak :8082                        ├── PostgreSQL + PostGIS
                                                      ├── Redis
                                                      ├── ایران‌مکان‌ها (داخلی)
                                                      └── OSM / Nominatim / Overpass

توسعه/تست: docker-compose.yml
تولید:     docker-compose.prod.yml (شبکه‌های internal و edge جدا)
```

اجزای اصلی:

| بخش | فناوری/مسیر | مسئولیت |
|---|---|---|
| API | Python 3.10+، FastAPI، SQLModel/SQLAlchemy async | منطق دامنه و REST API |
| داده | PostgreSQL 16، PostGIS، Alembic | داده‌های عملیاتی و مکانی |
| کش/زیرساخت OTP | Redis | کش و مؤلفه‌های وابسته به OTP |
| وب | Next.js App Router، React، TypeScript | داشبورد و BFF/proxy مرورگر به API |
| هویت | Keycloak و Auth.js/NextAuth | ورود OIDC و اعتبارسنجی bearer token |
| مکان | OSM، Nominatim/Overpass، سرویس داخلی استان/شهر | نقشه، geocoding و دادهٔ مکانی |
| افزونهٔ هویت | Java/Maven در `keycloak-shekarchi-sms/` | افزونهٔ SMS/OTP و CAPTCHA برای Keycloak |

## ساختار مخزن

```text
app/                         API، مدل‌ها، schemaها و سرویس‌های دامنه
  api/v1/endpoints/          مسیرهای REST و تجمیع آن‌ها در router.py
  core/                      تنظیمات، هویت، امنیت، رمزنگاری و لایسنس
  db/                        engine و session غیرهمزمان
  models/                    مدل‌های SQLModel
  schemas/                   قراردادهای ورودی/خروجی API
  services/                  CRM، matching، valuation، GIS، scraper و غیره
  cli/                       ابزارهای خط فرمان، از جمله لایسنس
alembic/versions/            migrationهای پایگاه داده
frontend/                    اپلیکیشن Next.js و تست‌های Vitest
keycloak/                    realm export و تم ورود
keycloak-shekarchi-sms/      افزونهٔ Java برای Keycloak، اسکریپت و مستند خودش
services/iran-locations-api/ submodule مستقل برای استان/شهر
tests/                       تست‌های Python
docs/                        طراحی/برنامه‌ها و مستندات دامنه
scripts/                     راه‌اندازی محلی و ابزارهای عملیاتی
docker-compose.yml           پشتهٔ توسعه/محلی
docker-compose.prod.yml      الگوی Compose تولید
```

`services/iran-locations-api` یک **Git submodule** است. پس از clone، آن را با `git submodule update --init --recursive` دریافت کنید. دسترسی clone به مخزن submodule نیز باید برای کاربر/CI فراهم باشد.

## پیش‌نیازها

- Docker Engine و Docker Compose plugin برای اجرای پشتهٔ کامل.
- Python نسخهٔ 3.10 یا بالاتر، برای توسعهٔ API.
- Node.js سازگار با نسخهٔ Next.js پروژه و یکی از package managerهای سازگار با lockfile فرانت‌اند؛ اسکریپت‌های توسعهٔ مخزن از Bun نیز استفاده می‌کنند.
- Maven و JDK سازگار با `pom.xml`، فقط برای ساخت/توسعهٔ افزونهٔ Keycloak.
- Git با پشتیبانی submodule.

## اجرای محلی با Docker Compose

از ریشهٔ مخزن (`/home/app/real`) اجرا کنید. پیکربندی محلی از `.env` استفاده می‌کند؛ نمونه را کپی و مقادیر محیط خود را تنظیم کنید:

```bash
cp .env.example .env
# ویرایش .env: URLهای issuer، رمزهای محلی و تنظیمات لازم را بررسی کنید
git submodule update --init --recursive
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

سرویس‌های Compose محلی شامل PostgreSQL/PostGIS، Redis، دیتابیس جداگانهٔ Keycloak، Keycloak، API، فرانت‌اند، سرویس ایران‌مکان‌ها و tile server هستند. پورت‌های پیش‌فرض در Compose تعریف شده‌اند؛ پورت‌های قابل انتشار را پیش از اجرا با فایل Compose تطبیق دهید. در Compose محلی، سرویس Iran Locations فقط روی شبکهٔ داخلی Compose در دسترس است و پورت میزبان ندارد.

برای مشاهدهٔ وضعیت و گزارش‌ها:

```bash
docker compose ps
docker compose logs -f backend keycloak frontend
```

برای خاموش‌کردن سرویس‌ها بدون حذف volumeها:

```bash
docker compose down
```

**هشدار:** `docker compose down -v` داده‌های volume از جمله دیتابیس را حذف می‌کند؛ فقط در محیط disposable اجرا شود.

## اجرای توسعه بدون Compose کامل

مسیر bootstrap رسمی مخزن:

```bash
make setup
```

`make setup` اسکریپت `scripts/setup_local.sh` را اجرا می‌کند و برای تنظیم کامل گرهٔ محلی (محیط Python، وابستگی‌ها، `.env`، دیتابیس و کلیدها) طراحی شده است. پیش از اجرا، محتوای اسکریپت و اثرهای محیطی آن را مرور کنید. مسیر مرحله‌ای:

```bash
make venv
make install
make db                 # PostgreSQL/PostGIS و Redis با Compose
make migrate            # alembic upgrade head
make run                # scripts/dev.sh
```

یا اجرای مستقیم API پس از نصب وابستگی‌ها و آماده‌سازی تنظیمات:

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

فرانت‌اند:

```bash
cd frontend
bun install
bun run dev
```

اسکریپت‌های فرانت‌اند در `frontend/package.json` شامل `dev`، `build`، `start`، `typecheck`، `lint` و `test` هستند. در CI، از package manager و lockfile تثبیت‌شدهٔ همان pipeline استفاده کنید.

## تنظیمات و متغیرهای محیطی

منبع مرجع نام‌ها و defaultها، `/.env.example` و `app/core/config.py` است. فایل `.env` محلی محرمانه است و نباید commit شود. تنظیمات با Pydantic Settings بارگذاری می‌شوند؛ نام متغیرهای محیطی به حروف کوچک/بزرگ حساس نیست. برخی secretها از فایل Docker secret نیز خوانده می‌شوند.

مواردی که در هر محیط باید هماهنگ باشند:

| دسته | نمونه/ملاحظه |
|---|---|
| توپولوژی | `NODE_MODE=LOCAL` یا `CLOUD_HUB` |
| پایگاه داده | `DATABASE_URL`؛ داخل Compose باید hostname سرویس DB را استفاده کند، نه `localhost` |
| هویت | `AUTH_MODE`، `KEYCLOAK_ISSUER` و تنظیمات audience/client؛ issuer باید دقیقاً با issuer داخل token یکی باشد |
| فرانت‌اند | `NEXT_PUBLIC_KEYCLOAK_ISSUER` و URLهای عمومی لازم؛ مقادیر `NEXT_PUBLIC_*` در build مرورگر قابل مشاهده‌اند و secret نیستند |
| کش | `REDIS_URL` و رمز Redis در محیط تولید |
| داده/کلیدها | مسیرهای `DATA_DIR`، رسانه، فایل لایسنس و کلید عمومی/خصوصی مطابق تنظیمات |
| جمع‌آوری | پرچم‌ها و پارامترهای scraper؛ زمان‌بند با تنظیمات خودش فعال می‌شود و به‌طور پیش‌فرض نباید فرض کرد فعال است |
| پیامک | provider و secretهای gateway/HMAC؛ در Compose محلی Fake SMS صریحاً برای توسعه تنظیم شده است، نه ارسال واقعی |
| نقشه | URL tile server و تنظیمات سرویس مکان؛ OSM/Nominatim/Overpass ممکن است به شبکهٔ بیرونی نیاز داشته باشند |

مقادیر نمونهٔ `.env.example` را در تولید به‌عنوان رمز قابل‌استفاده تلقی نکنید. همهٔ رمزها، secretهای OIDC/HMAC و کلیدهای رمزنگاری باید یکتا، قوی و خارج از Git نگهداری شوند.

## API و احراز هویت

- برنامه در `app/main.py` ساخته می‌شود و API نسخهٔ یک زیر پیشوند `/api/v1` ثبت شده است.
- مسیرهای health، registration و auth در routerهای جداگانه‌اند؛ بیشتر APIهای عملیاتی زیر `private_router` قرار دارند و به principal معتبر و مجوز API نیاز دارند.
- مدیریت کاربران Keycloak علاوه بر احراز هویت به نقش مدیریتی محدود شده است.
- مسیرهای دامنه در `app/api/v1/endpoints/` پیاده‌سازی شده‌اند؛ از جمله properties، CRM، matching، scraper، GIS، billing، network، statistics، users، preferences و license.
- `app/main.py`، به‌صورت عمدی، OpenAPI/Swagger URL عمومی را غیرفعال می‌کند (`openapi_url=None`, `docs_url=None`). برای کشف قرارداد، router/schemaهای کد و تست‌ها مرجع‌اند؛ در محیط توسعه هم docs بدون تغییر صریح پیکربندی در دسترس نیست.
- health endpoint برای healthcheck کانتینر استفاده می‌شود؛ مسیر دقیق آن را در `app/api/v1/endpoints/health.py` و Compose بررسی کنید.
- frontend دارای route واسط در `frontend/src/app/backend/api/v1/[...path]/route.ts` است؛ URL عمومی API و proxy را از تنظیمات همان کد و `.env.example` هماهنگ کنید.

برای درخواست‌های محافظت‌شده، token صادرشده از realm صحیح Keycloak و نقش/permission مجاز لازم است. CORS و اعتبارسنجی issuer را برای دامنهٔ واقعی deployment تنظیم کنید؛ بازکردن CORS عمومی در محیط production توصیه نمی‌شود.

## داده، migration و پشتیبان‌گیری

- اتصال async در `app/db/session.py` ساخته می‌شود؛ مدل‌ها SQLModel/SQLAlchemy هستند.
- migrationها با Alembic نگهداری می‌شوند. برای اعمال تغییرات:

  ```bash
  .venv/bin/alembic upgrade head
  ```

- در Compose تولید، migration پیش از اجرای Uvicorn در command سرویس backend اجرا می‌شود. برای چند replica یا تغییرهای ناسازگار، اجرای migration را به فرایند کنترل‌شدهٔ deployment بسپارید.
- DB اصلی املاک و DB مستقل Keycloak دو volume/schema مجزا دارند؛ برای بازیابی کامل، هر دو را همراه با داده‌های رسانه، فایل لایسنس و کلیدهای مورد نیاز پشتیبان بگیرید.
- رسانه، فایل‌های runtime، کلیدها و برخی داده‌ها زیر مسیرهای دادهٔ قابل تنظیم ذخیره می‌شوند؛ همهٔ آن‌ها الزاماً داخل PostgreSQL نیستند.
- پیش از restore/upgrade، نسخهٔ پشتیبان را در محیط جداگانه آزمایش کنید. حذف volume با `down -v` جایگزین backup نیست.

## ماژول‌های دامنه

- **املاک و PII:** مشخصات ملک از اطلاعات تماس/مالک جدا نگهداری می‌شود؛ دسترسی به دادهٔ حساس، سهمیه و audit مسیرهای مستقلی دارند.
- **CRM:** leadها، pipeline/board، برنامه‌ریزی بازدید و عملیات کاربرمحور در service و endpointهای CRM.
- **Matching:** تطبیق تقاضای مشتری و فایل ملک با محاسبات قطعی و قابلیت‌های مکانی؛ persistence در مدل‌های matching.
- **ارزش‌گذاری (AVM):** برآورد deterministic متکی به داده‌های comparable و سابقهٔ قیمت؛ مسیر فعلی AI به‌صورت stub است و نباید آن را inference واقعی ML تلقی کرد.
- **Scraper و ingestion:** adapterهای منبع در `app/services/scraper/` و pipeline پاک‌سازی/تشخیص تکرار در `app/services/ingestion/`. اجرا و زمان‌بندی به تنظیمات محیط وابسته است؛ قوانین سایت منبع و شرایط قانونی را رعایت کنید.
- **GIS:** مسیرهای GIS و سرویس‌های OSM در `app/services/`; دادهٔ استان/شهر از submodule داخلی `services/iran-locations-api` مصرف می‌شود. سرویس مکان در Compose محلی پورت host ندارد.
- **شبکه و billing:** همکاری دفترها، گزارش‌ها و صورت‌حساب در مدل‌ها/سرویس‌های مستقل.
- **لایسنس:** ابزار CLI در `app/cli/license_tool.py` و منطق اعتبارسنجی/وضعیت در `app/core/licensing.py` و سرویس لایسنس.

برای جزئیات دقیق قواعد کسب‌وکار، فایل‌های service، schema، endpoint و تست متناظر را مرجع قرار دهید؛ این بخش نمای کلی است، نه قرارداد جامع دامنه.

## فرانت‌اند

فرانت‌اند در `frontend/` با Next.js App Router ساخته شده است. صفحات اصلی داشبورد در `frontend/src/app/dashboard/` و قابلیت‌ها/کامپوننت‌ها در `frontend/src/features/` و `frontend/src/components/` قرار دارند. `frontend/AGENTS.md` راهنمای داخلی ساختار و conventionهای UI است.

احراز هویت وب در `frontend/src/lib/auth/` و `frontend/src/proxy.ts` قرار دارد؛ endpointهای Auth.js، logout و proxy backend را در `frontend/src/app/api/` و `frontend/src/app/backend/` می‌یابید. تنظیم URL عمومی Keycloak در build فرانت‌اند اهمیت دارد. از درج secret در متغیرهای `NEXT_PUBLIC_*` خودداری کنید.

برای توسعه و اعتبارسنجی:

```bash
cd frontend
bun run typecheck
bun run lint
bun run test
bun run build
```

برای تغییر تم/لوگوی فرانت‌اند که داخل image بسته‌بندی شده، image را دوباره build کنید. تم Keycloak در Compose از mount جداگانه می‌آید؛ روش اعمال تغییرات آن متفاوت است.

## Keycloak و افزونهٔ SMS/OTP

- realm export و تم ورود در `keycloak/` نگهداری می‌شوند. Compose محلی Keycloak را با دیتابیس اختصاصی و Redis اجرا می‌کند.
- افزونهٔ Java در `keycloak-shekarchi-sms/` است؛ README همان ماژول راهنمای build و نصب است. تغییر فایل‌های این ماژول الزاماً به معنی تغییر image/runtime نیست: image Keycloak باید با Dockerfile و فرایند deployment مربوطه دوباره ساخته شود.
- آزمون Java:

  ```bash
  cd keycloak-shekarchi-sms
  mvn test
  ```

- فایل realm export ممکن است شامل تنظیمات حساس یا دادهٔ قابل‌سوءاستفاده باشد؛ قبل از انتشار/تغییر آن، secretها و credentialهای exportشده را بازبینی کنید. در تولید، از حساب‌های bootstrap پیش‌فرض یا fake SMS استفاده نکنید.

## تست و کنترل کیفیت

Python:

```bash
.venv/bin/python -m pytest -q
make lint
```

فرانت‌اند و Keycloak در بخش‌های خود دستورهای test/typecheck/lint دارند. تست‌های integration پایگاه داده و PostGIS به سرویس و schema آماده وابسته‌اند؛ اگر dependency موجود نباشد ممکن است تست مربوطه skip شود. پیش از نتیجه‌گیری دربارهٔ وضعیت integration، خروجی pytest را بررسی کنید.

برای تست‌های واقعی محیط، سرویس‌های لازم را بالا بیاورید، migration را اعمال کنید و secret/URLهای test-only را جدا نگه دارید. تستی که صرفاً pass می‌شود، به‌تنهایی سلامت deployment، دسترسی Git submodule، ارسال SMS واقعی یا صحت تنظیمات production را ثابت نمی‌کند.

## استقرار تولید

`docker-compose.prod.yml` الگوی استقرار با شبکه‌های `internal` و `edge` و volumeهای پایدار است؛ پیش از استفاده، آن را با reverse proxy، TLS، DNS، secret manager و سیاست شبکهٔ محیط مقصد تطبیق دهید. این فایل به‌تنهایی reverse proxy/TLS یا مدیریت secretها را فراهم نمی‌کند.

چک‌لیست حداقلی:

1. همهٔ placeholderها را با secretهای مستقل و قوی جایگزین کنید؛ `.env` تولید را commit نکنید.
2. `KEYCLOAK_PUBLIC_URL`/`KEYCLOAK_ISSUER` و `NEXT_PUBLIC_KEYCLOAK_ISSUER` را با URL قابل دسترس مرورگر و claim واقعی `iss` تطبیق دهید.
3. redirect URIها، CORS، cookie/HTTPS و تنظیمات proxy را برای hostname واقعی تنظیم و OIDC login/logout را آزمایش کنید.
4. fake SMS را خاموش کنید، provider واقعی را فقط با تأیید عملیاتی فعال کنید و secretهای HMAC/provider را امن provision کنید.
5. submoduleها و imageها را از revision مشخص و قابل دسترسی build کنید؛ وضعیت Keycloak توسعه و تولید ممکن است متفاوت باشد.
6. backup/restore هر دو PostgreSQL، Redis در صورت نیاز عملیاتی، رسانه، کلیدها و license runtime را آزمایش کنید.
7. rollout migration، healthcheckها، logها، rollback و کنترل دسترسی endpointهای مدیریتی را بررسی کنید.

## امنیت و عیب‌یابی

- **401 یا issuer نامعتبر:** مقدار `KEYCLOAK_ISSUER` باید با `iss` توکن دقیقاً برابر باشد؛ hostname و scheme داخل/خارج proxy را بررسی کنید.
- **ورود loop یا cookie/session نامعتبر:** URL عمومی HTTPS، hostname/forwarded headers، callback و cookieهای Auth.js را در proxy و Keycloak تطبیق دهید.
- **API از فرانت‌اند قابل دسترسی نیست:** proxy route، base URL، شبکهٔ Docker، CORS و health backend را بررسی کنید؛ از `localhost` داخل کانتینر برای سرویس دیگر استفاده نکنید.
- **لیست استان/شهر خالی است:** وضعیت submodule، build سرویس `iran_locations`، دسترسی شبکهٔ داخلی و logهای backend را بررسی کنید.
- **مهاجرت شکست خورده:** اتصال DB، PostGIS، وضعیت revision Alembic و logهای backend را بررسی کنید؛ migration را روی دادهٔ تنها نسخهٔ موجود آزمایشی نکنید.
- **OTP/SMS کار نمی‌کند:** وضعیت Redis، flow و provider انتخاب‌شده، secretهای HMAC، تنظیمات realm و تفاوت fake محلی/real تولید را بررسی کنید. پاسخ سرویس را بی‌دلیل با ارسال‌های مکرر واقعی آزمایش نکنید.
- **scraper اجرا نمی‌شود:** feature flag، scheduler، license، source registry و log سرویس را بررسی کنید؛ اجرای خودکار در حالت خاموش طبیعی است.

داده‌های PII، token، secret، OTP، headerهای Authorization و محتوای `.env` را در log یا issue عمومی قرار ندهید.

## محدودیت مستند

README نقشهٔ راه‌اندازی و معماری کد را خلاصه می‌کند. پیکربندی مؤثر هر محیط می‌تواند به‌واسطهٔ `.env`، Compose override، secretها، وضعیت volume و نسخهٔ submodule با این توصیف فرق کند. در تعارض، فایل اجرایی محیط، کد runtime و خروجی health/log مرجع نهایی‌اند. تغییرات runtime و داده‌های خارج Git را نیز جداگانه بررسی کنید.

---

© AVG — گروه چشم‌انداز اوج فردا
