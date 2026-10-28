# SHEKARCHI — ممیزی معماری دسترسی و اشتراک

تاریخ ممیزی: 2026-10-28

## دامنه و وضعیت تغییرات

- مسیر بررسی: `/home/app/real`
- Keycloak عملیاتی، Production، Schema و Migration تغییر نکردند.
- تغییرات موجود در Git حفظ شدند و در این ممیزی دست‌کاری نشدند.
- Working tree پیشاپیش dirty و دارای فایل‌های untracked متعدد بود؛ تغییرات Phase 1 در انتهای این گزارش ثبت شده‌اند.
- ایمیج‌های جدید خارج از کد پروژه در مسیر `/home/app/backups/shekarchi-images-20261028T084833Z-v1/images/edited` قرار دارند و در تصمیم امنیتی نقشی ندارند.

## 1. Architecture Gap Analysis

### نقاط قوت موجود

- اعتبارسنجی توکن در `app/core/identity.py` با RS256، issuer، audience، expiry، `typ=Bearer` و `azp` انجام می‌شود.
- نگاشت Realm Role به نقش داخلی در یک نقطه متمرکز است: `KEYCLOAK_ROLE_MAP`.
- KYC برای مسیرهای private که `get_principal` دارند اجباری است؛ مسیرهای public مانند health و plan catalog از این dependency مستثنا هستند.
- Workspace در مسیر عادی از جدول `agency_membership` resolve می‌شود و صرفاً از claim توکن پذیرفته نمی‌شود؛ مسیرهای synthetic admin و legacy tenant fallback استثناهای سازگاری هستند.
- PII در `property_owner_pii` رمزنگاری می‌شود؛ `pii_vault` نقش، quota و audit را پیش از decrypt بررسی می‌کند.
- سهمیه ثبت آگهی به Subscription/Workspace متصل است و با lock از race جلوگیری می‌کند.
- سفارش پرداخت کلید idempotency دارد؛ فعال‌سازی سمت سرور انجام می‌شود و سفارش آزمایشی اشتراک واقعی فعال نمی‌کند.
- دسترسی‌های همکاری بین دفاتر با permission matrix و حالت deny-by-default مدل شده‌اند.

### شکاف‌های مهم

| شدت | شکاف | شاهد | اثر |
|---|---|---|---|
| بالا | Public Listing در Backend واقعاً عمومی نیست | `app/api/v1/router.py:57-88` همه `properties.router` را زیر `API_GUARD` قرار می‌دهد؛ `app/api/v1/endpoints/properties.py:530-531` شاخه anonymous دارد اما `get_principal` بدون Bearer، 401 می‌دهد | Guest Preview فعلی با قرارداد Frontend هم‌خوان نیست |
| بالا | DTO عمومی از DTO داخلی جدا نیست | `PropertySummary` در `app/schemas/properties.py:122-210` برای هر دو حالت استفاده می‌شود | تغییرات آینده می‌تواند فیلد حساس را ناخواسته public کند |
| بالا | جزئیات ملک بررسی visibility/ownership کافی ندارد | `GET /properties/{property_id}` در `app/api/v1/endpoints/properties.py:1371-1387` فقط `LicenseGuard` دارد | principal تأییدشده ممکن است draft/withdrawn یا ملک workspace دیگر را بخواند |
| بالا | status filter برای caller احراز‌شده مستقیماً پذیرفته می‌شود | `properties.py:528-531` فقط anonymous را ACTIVE می‌کند و `:549-550` `status_filter` را اعمال می‌کند | احتمال افشای inventory غیرفعال |
| بالا | Decision مرکزی با خروجی‌های پنج‌گانه وجود ندارد | تصمیم‌ها میان `identity.py`، `deps.py`، endpointها و `pii_vault.py` پخش شده‌اند | ممیزی یک درخواست به‌صورت یکنواخت دشوار است |
| متوسط | Internal Role و Realm Role همیشه یک‌به‌یک نیستند | analyst به `UserRole.GUEST` نگاشت شده ولی `PII_DENY_ROLES` veto جدا دارد | وضعیت authenticated-but-unverified با Guest داخلی مخلوط می‌شود |
| متوسط | Entitlement فقط بخشی از قابلیت‌ها را مدل می‌کند | `app/services/entitlements.py` فعلاً listing quota را پیاده می‌کند؛ مدل billing شامل listing/SMS/regions/advisor است | radar/AVM/PDF/SMS هنوز contract واحد entitlement ندارند |
| متوسط | Cache عمومی و Rate Limit عمومی مشخص نشده‌اند | Redis/TTL برای OTP و cacheهای GIS/POI موجود است، اما Public Listings cache policy ندارد | فشار query و خطر اشتباه در cache key |
| متوسط | Frontend policy با Backend policy واگرا است | `frontend/src/lib/auth/route-policy.ts:15-30` APIهای properties را public اعلام می‌کند، در حالی که Backend private است؛ صفحه نیز در `approval-gate.tsx` متفاوت فرض شده | UX و پاسخ API متناقض می‌شوند |
| متوسط | ApprovalGate و proxy رفتار یکسان ندارند | `frontend/src/features/auth/components/approval-gate.tsx` properties را عبور می‌دهد ولی proxy و Backend token/KYC می‌خواهند | flash/redirect و تجربه‌ی متناقض |
| متوسط | AVM و market preview قرارداد public/private نامشخص دارند | صفحات landing از APIهای authدار استفاده می‌کنند | Guest به‌جای preview واقعی خطا یا CTA مبهم می‌بیند |
| متوسط | Heatmap واقعی وجود ندارد | `frontend/src/features/properties/components/market-map*.tsx` bubble map است | نباید bubble map به‌عنوان heatmap مکانی معرفی شود |
| پایین | ادعاهای health درباره cache واقعی نیستند | `app/api/v1/endpoints/health.py` وضعیت cache را ثابت گزارش می‌کند | observability قابل اتکا نیست |

### Keycloak-specific gaps

- `ROLE_OWNER` و `ROLE_UNVERIFIED_USER` در export تعریف شده‌اند اما کاربر seed متناظر در `keycloak/realm-export.json` ندارند؛ مستندات `keycloak/README.md` با export واقعی هم‌خوان نیستند.
- `financial_admin` در Realm export تعریف نشده، در حالی که Backend و Frontend آن را permission مستقل بررسی می‌کنند.
- aliasهای قدیمی `ROLE_SUPER_ADMIN`، `admin` و `super_admin` فقط در بخشی از Frontend پذیرفته می‌شوند و Realm role واقعی نیستند.
- membershipهای legacy مانند `LEGACY_OFFICE_OPERATOR` نقش Realm نیستند و حذف آن‌ها بدون migration می‌تواند کاربران قدیمی را قطع کند.
- fallback tenant legacy در `app/api/deps.py:272-304` بدون برنامه‌ی حذف مشخص، در صورت نبود membership DB یک membership موقت برای برخی نقش‌های privileged می‌سازد؛ این مسیر باید دائمی‌بودن یا sunset آن صریحاً تعیین شود.
- tier/quota از دو منبع مستقل می‌آیند: claim توکن برای PII و DB subscription برای listing؛ binding و refresh contract واحدی برای تغییر plan در توکن وجود ندارد.
- export فعلی `sslRequired=none`، `directAccessGrantsEnabled=true` و `fullScopeAllowed=true` دارد؛ تغییر این موارد فقط در clone و پس از بررسی اثر مجاز است.
- مستندات PKCE/S256 را ادعا می‌کنند اما attribute مربوط به PKCE در export دیده نمی‌شود.
- `maskanchi-frontend` در بعضی مستندات با client واقعی `shekarchi-frontend` اختلاف نام دارد.
- نبود MFA و brute-force enforcement در گزارش آمادگی cutover باید پیش از Production به‌عنوان ریسک باز باقی بماند.

## 2. ماتریس نقش / مجوز / Workspace / Plan

| Realm Role | Internal Role | مجوز پایه | Workspace | Plan/Entitlement | PII |
|---|---|---|---|---|---|
| بدون توکن | ANONYMOUS | فقط Public DTO، read-only | ندارد | ندارد | Deny |
| `ROLE_UNVERIFIED_USER` | فعلاً `GUEST` | احراز هویت، مسیرهای غیرحساس طبق policy | عضویت لازم برای workspace | FREE/بدون entitlement قطعی | Deny |
| `ROLE_VERIFIED_USER` | `USER` | امکانات کاربر تأییدشده | فقط membership فعال | FREE | Deny |
| `ROLE_OWNER` | `OWNER` | ثبت ملک شخصی، read محدود | شخصی یا workspace انتخاب‌شده | FREE/plan workspace | Deny |
| `ROLE_JUNIOR_BROKER` | `AGENT` | desk، listing، CRM طبق guard | membership فعال | entitlement workspace | quota و audit |
| `ROLE_SENIOR_BROKER` | `AGENT` | desk کامل، network محدود | membership فعال | entitlement workspace | quota و audit |
| `ROLE_AGENCY_MANAGER` | `OFFICE_MANAGER` | مدیریت دفتر، اعضا و network | membership فعال | subscription workspace | quota و audit |
| `ROLE_SUPERVISOR` | `SUPERVISOR` | governance، audit، override | workspace/global طبق endpoint | plan/license | PII مجاز، دلیل audit |
| `ROLE_ADMIN` | `ADMIN` | system/admin/license | global یا workspace | license/enterprise | PII مجاز، audit |
| `ROLE_DATA_ANALYST` | فعلاً `GUEST` + veto | statistics/analysis طبق route policy | در صورت نیاز membership | entitlement جدا لازم است | Deny مطلق |
| `financial_admin` | permission مستقل | billing financial فقط | workspace مالی/طبق endpoint | خارج از نقش عملیاتی | بدون PII مگر قرارداد صریح |

این جدول طراحی هدف است؛ mapping فعلی Keycloak/Schema بدون تأیید تغییر نمی‌کند.

## 3. ماتریس Guest Access

| وضعیت | Token | نقش | Public listing | PII | AVM/Radar/Heatmap | CTA |
|---|---|---|---|---|---|---|
| `ANONYMOUS` | ندارد | ندارد | فقط ACTIVE و DTO عمومی، پس از تصویب public route | Deny | preview read-only یا نمونه با برچسب واضح، بدون query سنگین | ورود/ثبت‌نام |
| `AUTHENTICATED_UNVERIFIED` | معتبر | نقش unverified یا بدون verified grant | فقط public DTO | Deny | preview محدود | تکمیل احراز/تأیید |
| `AUTHENTICATED_VERIFIED` | معتبر | `ROLE_VERIFIED_USER` با mobile proof و KYC | public + قابلیت‌های entitlement شده | Deny مگر role مجاز | طبق entitlement و quota | انتخاب Workspace/پلن |
| Professional | معتبر | OWNER/AGENT/… | public + internal scope | طبق role، share و quota | واقعی، فقط با entitlement | اقدام عملیاتی |

## 4. Public DTO پیشنهادی

پیشنهاد: `PublicListingDTO` جدا از `PropertySummary` با allowlist صریح. فیلدهای مجاز: شناسه عمومی غیرقابل‌حدس یا UUID موجود، عنوان، نوع/معامله، شهر/محله، متراژ تقریبی، اتاق، قیمت‌های مجاز، امکانات، وضعیت `ACTIVE`، منبع کلی، تصویر public، description پاک‌سازی‌شده و مختصات blurشده. موارد ممنوع: `phone_number`، `owner_id`، `exact_address`، `precise_coordinates`، `private_notes`، ciphertext/صاحب ملک، اطلاعات تماس و هر شناسه‌ای که هویت مالک را افشا کند.

شرط query: فقط `PropertyStatus.ACTIVE`، pagination سخت، فیلترهای allowlisted و بدون `status` قابل‌گسترش برای Guest. تغییر route یا response model نیازمند تأیید قرارداد API است.

## 5. Cache و Rate Limit پیشنهادی

- Redis با namespace جدا: `shekarchi:public:listings:v1`.
- Cache key شامل نسخه DTO، فیلتر canonical، صفحه/limit و workspace scope؛ هرگز token، PII یا پاسخ private در key عمومی وارد نشود.
- TTL پیشنهادی 30 تا 120 ثانیه برای فهرست، purge/invalidation پس از تغییر status یا publish؛ stale-while-revalidate فقط برای داده public.
- سقف `limit` عمومی حداکثر 50 تا 100 تا زمان benchmark؛ offset بزرگ محدود یا cursor-based شود.
- Rate limit بر IP/تنظیمات proxy قابل اعتماد و در صورت login بر subject؛ پاسخ 429 با `Retry-After`.
- `Vary: Authorization, Cookie` برای مسیرهایی که public/private مشترک نیستند؛ ترجیحاً public و private مسیر/کلید جدا داشته باشند.
- متریک‌های لازم: hit ratio، miss، latency، key cardinality، 429، invalidation lag و query duration.
- Read Replica فعلاً لازم نیست؛ پس از load test و مشاهده bottleneck واقعی تصمیم‌گیری شود.

## 6. Entitlement و Quota

مدل پیشنهادی entitlement مستقل از role:

| Entitlement | واحد | دوره | Reset | پایان |
|---|---|---|---|---|
| `listing.max_active` | تعداد آگهی فعال workspace | دوره plan | با publish/unpublish و تمدید | `QUOTA_EXCEEDED` |
| `lead_sms.period_limit` | پیام موفق | دوره plan | شروع دوره جدید | `QUOTA_EXCEEDED` |
| `radar.area_limit` | شهر/ناحیه | دوره plan | دوره‌ای | `SUBSCRIPTION_REQUIRED` یا quota |
| `agency.member_limit` | عضو فعال | همزمان | با revoke آزاد می‌شود | `QUOTA_EXCEEDED` |
| `avm.basic` | feature flag | plan | ندارد | `SUBSCRIPTION_REQUIRED` |
| `avm.pdf_export` | export | دوره plan | period reset | `SUBSCRIPTION_REQUIRED`/quota |

پیاده‌سازی فعلی فقط بخشی از `listing` را enforce می‌کند. مقدارهای GOLD، FREE و Fair Usage تصمیم محصولی هستند و عمداً قطعی نشده‌اند.

## 7. Conversion Funnel

1. Guest preview → CTA با `returnTo` کوتاه و فقط internal path.
2. ورود/ثبت‌نام → اعتبارسنجی server-side session و callback.
3. احراز mobile/KYC → ایجاد یا انتخاب Workspace از membership DB.
4. انتخاب plan → intent کوتاه‌مدت و bind‌شده به subject/workspace/plan.
5. ایجاد order با `Idempotency-Key`.
6. پرداخت/ارسال رسید → هیچ callback query به‌تنهایی proof نیست.
7. verify server-side درگاه یا review مالی.
8. activation idempotent با snapshot plan و audit.

در کد موجود بخش عمده سفارش، callback verification و idempotency وجود دارد؛ پرداخت واقعی یا تغییر درگاه انجام نشد.

## 8. ریسک‌های امنیتی

- فعال‌کردن anonymous بدون DTO جدا می‌تواند اطلاعات داخلی را public کند.
- قرار دادن public و private در یک endpoint با cache مشترک می‌تواند cache privacy را بشکند.
- `ROLE_DATA_ANALYST` به `GUEST` داخلی نگاشت شده و برای ABAC آینده باید وضعیت احراز از role جدا شود.
- status filtering برای Guest باید سمت Backend غیرقابل‌گسترش باشد.
- endpointهای حرفه‌ای باید entitlement/quota را در Backend enforce کنند؛ frontend guard کافی نیست.
- health response فعلی نباید وضعیت واقعی cache را ادعا کند.
- AVM، Bargain Radar، market/neighbourhood aggregation، matching و scraper داده/فرآیند واقعی دارند؛ endpoint مستقل `heatmap` وجود ندارد و heatmap از market aggregation تغذیه می‌شود. در مقابل درآمد ماهانه/سالانه در `app/api/v1/endpoints/statistics/router.py` صراحتاً mock است و نباید به‌عنوان تحلیل واقعی نمایش داده شود.
- ابزارهای حرفه‌ای خواندن AVM/radar/market quota محصولی مستقل ندارند؛ فعلاً فقط role، license و `VALUATION_ENABLED` اعمال می‌شود. این موضوع باید قبل از فروش entitlement جداگانه تعیین شود.
- funnel بازاریابی landing تا login/OTP/approval/اولین اقدام event contract و attribution ندارد؛ conversion CRM و referral نیز denominator و تعریف متفاوت دارند و نباید یک KPI واحد تلقی شوند.
- `AUTH_BYPASS_ENABLED` در Frontend یک ریسک deployment است و باید در preflight محیط Production صریحاً false بودنش بررسی شود.
- `GET /gis/static-map` عمداً 502 می‌دهد؛ نباید برای Guest تصویر mock جایگزین شود، و UI باید از tile layer یا پیام محدودیت استفاده کند.
- هر تغییر Realm Role یا migration می‌تواند توکن‌های قدیمی و membershipهای موجود را تحت تأثیر قرار دهد.

## 9. تغییرات کد مجاز و انجام‌شده

- در ممیزی اولیه هیچ تغییر عملیاتی انجام نشد؛ اصلاحات Phase 1 در الحاقیه انتهای گزارش ثبت شده‌اند.
- Phase 1 فقط policy خواندن/visibility، DTO مستقل بدون اتصال به endpoint عمومی و تست‌ها را تغییر داد.
- هیچ تغییر در LicenseGuard، Keycloak، Realm، Subscription، Database Schema، Migration، Production یا درگاه انجام نشد.

## 10. موارد نیازمند تأیید

1. آیا `/api/v1/properties` و `/cities` باید واقعاً anonymous public شوند؟
2. قرارداد دقیق `PublicListingDTO` و نام/شناسه endpoint عمومی چیست؟
3. آیا `ROLE_DATA_ANALYST` باید Internal Role مستقل داشته باشد یا veto فعلی حفظ شود؟
4. مقادیر قطعی FREE/GOLD، Fair Usage و reset دوره‌ها چیست؟
5. entitlementهای radar/heatmap/AVM/PDF/SMS و رفتار دقیق اتمام هرکدام چیست؟
6. آیا public cache در Redis فعال شود و TTL/rate limits محصولی چه باشد؟
7. سیاست نمایش نام agent/agency، source_ref و valuation fields به Guest چیست؟

## 11. تست و معیار پذیرش

تست‌های مرتبط موجود در `tests/test_public_access_policy.py`، `test_subscription_entitlements.py`، `test_workspace_membership.py`، `test_mls_masking.py`، `test_licensing.py` و تست‌های billing هستند. اجرای focused pytest در محیط فعلی به علت نصب نبودن dependency متوقف شد:

`ModuleNotFoundError: No module named 'sqlmodel'`

بنابراین تست‌های Python در این محیط قابل اعتبارسنجی نیستند. در مقابل، تست‌های Frontend مربوط به auth/route/origin و landing/preview با مجموع 62 تست موفق شدند و `tsc --noEmit` نیز بدون خطا پایان یافت. معیار پذیرش بعدی:

- anonymous فقط ACTIVE/Public DTO و بدون PII بگیرد؛
- unverified و anonymous از verified/professional جدا باشند؛
- workspace cross-tenant، PII، subscription و quota fail-closed باشند؛
- source `SCRAPED` هرگز به‌عنوان owner/internal عرضه نشود؛
- cache key عمومی با private داده overlap نداشته باشد؛
- open redirect، payment intent و callback replay رد شوند؛
- LicenseGuard regression و audit denied attempts پوشش داده شوند.

پوشش موجود، اما ناقص، شامل identity/KYC و role mapping، workspace revoke/isolation، listing quota، plan schema، payment idempotency، Zibal verification، PII masking/vault و Frontend origin/open-redirect است. شکاف‌های تستی مهم باقی‌مانده:

- تست مستقیم anonymous برای endpoint listing و بررسی نبود PII در پاسخ وجود ندارد.
- IDOR و cross-tenant برای همه endpointهای حساس به‌صورت جامع پوشش داده نشده است.
- expiration/renewal/downgrade/upgrade و concurrent enforcement همه quotaها کامل نیست.
- SMS، advisor و regions entitlement enforcement پوشش کامل ندارند.
- successful PII reveal همراه با quota decrement و audit end-to-end ناقص است.
- browser-level session expiry/refresh، authenticated redirect و dashboard server guard کامل نیست.
- sandbox/live callback خارجی، refund/chargeback و پرداخت هم‌زمان تست نشده‌اند.

## 12. Rollback

- چون تغییر عملیاتی یا migration انجام نشده، rollback کد/داده لازم نیست.
- برای مرحله بعد، هر تغییر باید در branch جدا و با migration قابل برگشت انجام شود.
- فعال‌سازی public route باید با feature flag خاموش‌شونده، DTO versioned و تست contract انجام شود.
- در صورت مشاهده‌ی نشت PII یا cache contamination، flag public access خاموش، cache namespace purge و route به حالت private برگردانده شود.

## الحاقیه Phase 1 — Property Access Security Hardening

### تغییرات انجام‌شده

- `app/api/v1/endpoints/properties.py`: policy مشترک visibility برای global ACTIVE، مالک شخصی، workspace فعال و share فعال با `view_summary` اضافه شد.
- `GET /properties/{property_id}` و read endpointهای media، POI، price history و visit availability قبل از پاسخ، مالکیت/workspace/share را بررسی می‌کنند و برای منبع غیرمجاز 404 یکنواخت می‌دهند.
- فهرست properties به scope caller محدود شد؛ `status` دیگر نمی‌تواند آگهی خارج از scope یا global غیرACTIVE را وارد نتیجه کند.
- synthetic global admin و legacy workspace resolution حذف نشدند و از مسیر موجود استفاده می‌کنند.
- `app/schemas/properties.py`: `PublicListingDTO` به‌عنوان allowlist مستقل اضافه شد، اما هیچ endpoint عمومی به آن متصل نشد.
- `tests/test_property_access_security.py`: تست‌های policy، cross-workspace denial، owner access، admin compatibility و عدم وجود فیلدهای PII در DTO اضافه شد.

### وضعیت تست Phase 1

- `py_compile` برای فایل‌های تغییر‌یافته موفق شد.
- pytest به‌دلیل نبودن `sqlmodel` در محیط فعلی در collection متوقف شد؛ تست روی دیتابیس/Production اجرا نشد.
- هیچ migration، schema change، Keycloak change، deploy یا restart انجام نشد.

### Rollback Phase 1

- حذف تغییرات فقط شامل revert فایل‌های `app/api/v1/endpoints/properties.py`، `app/schemas/properties.py` و فایل تست جدید است؛ migration یا داده‌ای برای rollback وجود ندارد.
- به‌دلیل dirty بودن اولیه‌ی worktree، rollback باید فقط روی hunkهای Phase 1 انجام شود و نباید با `git reset` یا revert کلی انجام شود.

## الحاقیه Phase 1.5 — Security Verification, Mutation Hardening & Test Fixture

### وضعیت محیط تست

- `.venv` معتبر پروژه موجود است و `sqlmodel 0.0.47` دارد؛ خطای قبلی `ModuleNotFoundError` ناشی از اجرای Python سیستم بود.
- `docker-compose.test.yml` فقط PostgreSQL/PostGIS disposable با volume و network مستقل تعریف می‌کند و به‌درستی بدون `PHASE23_TEST_DB_PASSWORD` اجرا نمی‌شود.
- هیچ container، volume، Keycloak realm یا دیتابیس عملیاتی برای Seed یا تست دست‌کاری نشد.
- Compose فعلی Realm/Keycloak تست ندارد؛ بنابراین ایجاد ۲۵ حساب در Keycloak اجرا نشده و اتصال به `avg_keycloak` ممنوع باقی مانده است.

### Mutation Policy انجام‌شده

`_require_property_manage` در `app/api/v1/endpoints/properties.py` اضافه شد. این policy فقط موارد زیر را مجاز می‌کند:

- synthetic global admin بدون workspace selector؛
- مالک personal property؛
- عضو فعال همان Workspace ملک.

Share با `view_summary` یا هر دسترسی read، هرگز به mutation تبدیل نمی‌شود. این policy روی valuation، price update، media upload و visit booking اعمال شد. مسیرهای read قبلی نیز با `_require_property_view` کنترل می‌شوند.

| Route | Method | Auth/Permission | Ownership/Workspace | Subscription | Audit | وضعیت |
|---|---|---|---|---|---|---|
| `/properties` | POST | KYC + property role + LicenseGuard | membership یا personal owner | listing quota | log | حفظ شد؛ lifecycle هنوز مستقیماً ACTIVE است |
| `/properties/{id}/value` | POST | property role + LicenseGuard | manage policy | license/valuation flag | log | hardening شد |
| `/properties/{id}/price` | POST | property role + LicenseGuard | manage policy | فعلاً entitlement مستقل ندارد | price history | hardening شد |
| `/properties/{id}/media` | POST | identity + property role + LicenseGuard | manage policy | فعلاً entitlement مستقل ندارد | log | hardening شد |
| `/properties/{id}/visit-slots` | POST | identity + property role + LicenseGuard | manage policy | فعلاً entitlement مستقل ندارد | booking row | hardening شد |
| `/properties/{id}/report` | POST | private router + LicenseGuard | existence/visibility نیازمند policy تکمیلی | ندارد | application log | ریسک باقی‌مانده |
| `/crm/properties/{id}/reveal-contact` | POST | PII role/share/quota/license | workspace + lead + share | PII quota | `OwnerAccessLog` | موجود و fail-closed |
| `/network/shares` و referral/transfer/commission | POST/PATCH | network role + LicenseGuard | source property و party membership در مسیرهای اصلی validate می‌شوند؛ dispute و relationهای قدیمی نیازمند review بیشترند | عمومی ندارد | network audit بخشی | hardening property binding انجام شد؛ audit کامل باقی است |

Mutationهای صریح PUT/PATCH/DELETE برای خود Property و lifecycleهای publish/withdraw/archive وجود ندارند. در Phase 1.5، merge در `POST /properties` فقط برای همان Workspace، همان مالک شخصی یا رکورد واقعاً unscoped/scraped مجاز شد؛ mismatch با پاسخ 404 به endpoint برمی‌گردد.

### تست‌های افزوده و نتایج

- `tests/test_property_access_security.py`: `6 passed` با `.venv` و `DEBUG=false`.
- `tests/test_property_submitter_type.py`: پس از اصلاح signature پارامتر `owner_subject`، `21 passed`.
- Focused security gate پس از اصلاح fixtureها: `96 passed, 1 warning`.
- Full Suite نهایی: `685 passed, 11 failed, 14 warnings`. این نتیجه برای Security Gate معتبر نیست، چون بخشی از integrationها به `localhost/avgcrm` متصل شدند؛ آن دیتابیس disposable تأییدنشده بود و Seed/cleanup روی آن اجرا نشد.
- شکست‌های باقی‌مانده شامل fixtureهای Chat، FK در Matching برای propertyهای موجود نبود، assertion قدیمی OSM و یک تست زمانی property است؛ هیچ Guard برای عبور تست غیرفعال نشد.
- Seed بدون marker با خطای مورد انتظار متوقف شد: `Set PHASE15_TEST_SEED_CONFIRM=YES`.

### Seed/Cleanup آماده‌شده

- `scripts/seed_phase15_test_fixture.py`: دقیقاً ۲۵ کاربر با ایمیل `@example.test`، پنج Workspace، پلن‌های واقعی `free/monthly/quarterly/yearly`، وضعیت‌های active/expired/pending و داده‌های Property سناریویی.
- `scripts/cleanup_phase15_test_fixture.py`: حذف ترتیبی فقط batch `phase15-20261028` و حذف کاربران Realm با همان prefix.
- هر دو اسکریپت بدون URL دیتابیس و issuerی که عبارت `phase15` داشته باشد، و بدون confirmation marker، fail-closed هستند.
- هیچ رمز عبور، OTP، token یا secret تولید یا چاپ نمی‌شود.

در این مرحله فقط PostgreSQL/PostGIS disposable با volume `phase23_test_pgdata` و network داخلی `phase23_test_net` راه‌اندازی و با `pg_isready` تأیید شد. Compose فعلی Keycloak test service ندارد؛ بنابراین استقلال Realm قابل اثبات نبود و اجرای Seed طبق policy متوقف شد. آمار واقعی ۲۵ حساب ایجادشده: صفر.

### موارد نیازمند تأیید/زیرساخت

1. ساخت یک Keycloak test realm و service account جدا با issuer شامل `phase15`.
2. اجرای PostgreSQL disposable طبق `docs/phase23-test-environment.md` و اعمال schema/migration تست.
3. تعیین entitlement مستقل برای price/media/valuation/visit/report/network mutations.
4. افزودن audit DB استاندارد برای mutationهای Property؛ در این فاز Schema/Enum جدید اضافه نشد.
5. اصلاح قرارداد تست plan catalog یا به‌روزرسانی assertion برای `payment_methods`.

### Rollback Phase 1.5

- حذف تغییرات کد فقط از فایل‌های `app/api/v1/endpoints/properties.py`، `app/services/submission.py` و تست جدید انجام می‌شود؛ هیچ migration یا دادهٔ عملیاتی ساخته نشده است.
- Seed در صورت فراهم‌شدن محیط تست فقط با cleanup script و همان batch پاک می‌شود؛ حذف volume فقط با نام دقیق پروژه‌ی disposable مجاز است.
- `git reset`، حذف volumeهای عملیاتی، حذف realm عملیاتی یا revert کلی ممنوع است.

## الحاقیه Phase 1.6 — Isolated Test Infrastructure Gate

### وضعیت اتصال و Preflight

- علت fallback مشخص شد: `Settings.database_url` در `app/core/config.py:87` مقدار `avgcrm` روی localhost دارد و `app/db/session.py:18-20` بدون guard همان مقدار را به engine می‌دهد.
- `scripts/phase15_preflight.py` اضافه شد. این preflight وجود `PHASE15_TEST_DATABASE_URL`، issuer/realm تست، fake SMS و payment disabled را اجباری می‌کند؛ دیتابیس را با `current_database()` و port بررسی می‌کند و discovery issuer را با realm تطبیق می‌دهد.
- PostgreSQL/PostGIS disposable با volume مستقل `phase23_test_pgdata` و network داخلی `phase23_test_net` healthy شد، اما Compose فعلی Keycloak تست ندارد.
- Full Suite پس از اصلاح fixtureها: `685 passed, 11 failed, 14 warnings` در 42.33 ثانیه. این نتیجه قابل قبول برای Security Gate نیست، چون دو Integration test به `localhost/avgcrm` متصل شدند؛ نتیجه‌ی آن اجرا invalid است.

### ۱۱ شکست باقی‌مانده

- Chat: fixture/schema ناسازگار؛ `chat_conversation.property_id` در fixture مقدار NULL می‌گیرد.
- Matching: fixture property واقعی ندارد و FK `property_match_property_id_fkey` روی targetی که در `property` نیست شکست می‌خورد؛ این تست به DB `avgcrm` نیز متصل شد.
- OSM: assertion قدیمی وجود `api_key` با تنظیمات فعلی SMS (`sms_api_key`) ناسازگار است و باید قرارداد امنیتی آن جدا تصمیم‌گیری شود.
- Property time-dependent: merge/deduplication باعث می‌شود برخی seedهای تکراری timestamp جدید نداشته باشند؛ باید fixture marker/content hash یکتا یا clock injection داشته باشد.

### وضعیت Keycloak و ۲۵ حساب

- هیچ Keycloak test container، database یا realm اختصاصی در Compose فعلی وجود ندارد.
- به‌دلیل نبود issuer/realm/service-account مستقل، preflight کامل قابل اجرا نبود و Seed اجرا نشد.
- تعداد حساب‌های آزمایشی ایجادشده در Realm تست: `0`.
- اسکریپت‌های fail-closed Seed/Cleanup همچنان آماده‌اند، اما تا اثبات test realm اجرای آن‌ها ممنوع است.

### وضعیت نهایی

Phase 1.6 **BLOCKED** است. اقدامات لازم: افزودن Keycloak test با database/volume/port مستقل، اجرای migration فقط روی PostgreSQL disposable، تنظیم service account محدود و اجرای preflight موفق؛ سپس اصلاح fixtureهای ۱۱ شکست و اجرای Full Suite بدون اتصال `avgcrm`.

## الحاقیه Phase 1.6.1 — Isolated Keycloak & Safe Test Bootstrap

### Guard ساختاری

- `tests/conftest.py` اکنون پیش از collection، `scripts/phase15_preflight.py` را اجرا می‌کند؛ اجرای مستقیم pytest بدون محیط تأییدشده متوقف می‌شود.
- پس از preflight، `DATABASE_URL` فقط به `PHASE15_TEST_DATABASE_URL` bind می‌شود.
- `app/db/session.py` پیش از `create_async_engine` برابری URL تأییدشده را بررسی می‌کند و `avgcrm` یا `localhost:5432` را رد می‌کند.
- اجرای مستقیم بدون تنظیمات تست با پیام fail-closed متوقف شد و هیچ SQL اجرا نشد.

### Overlay تست

- `docker-compose.phase15-test.yml` اضافه شد: application PostGIS، PostgreSQL مستقل Keycloak، Keycloak image هم‌نسخه، volumeها و network مستقل.
- `keycloak/phase15-test-realm.json` شامل realm اختصاصی و role/clientهای تست است و هیچ user/credential عملیاتی ندارد.
- Compose با مقادیر dummy فقط validate شد؛ به‌دلیل نبود service-account bootstrap کامل و عدم اجرای preflight واقعی، container Keycloak تست اجرا نشد.

### وضعیت پذیرش

Phase 1.6.1 همچنان **BLOCKED** است:

- PostgreSQL application مستقل موجود است، اما runner متصل به network تست و migration تستی آماده نشده.
- Keycloak test container/DB/realm واقعی با service account محدود هنوز health و discovery نشده است.
- Full Suite در محیط کاملاً ایزوله اجرا نشده؛ اجرای قبلی به `avgcrm` invalid بود.
- ۲۵ حساب در Realm تست ایجاد نشده‌اند.
- Seed و E2E عمداً اجرا نشدند.

### Rollback امن

- توقف مجاز فقط با project مستقل `shekarchi-phase15-test` و overlay Phase 1.6.1 است.
- حذف احتمالی فقط volumeهای `phase15_app_pgdata` و `phase15_keycloak_pgdata` مجاز است؛ volume `avg_*` یا `phase23_test_pgdata` نباید حذف شود.
- هیچ restart/stop روی containerهای `avg_*` انجام نشده است.

## الحاقیه Phase 1.6.2 — Test Infrastructure Activation & Validation

### محیط فعال‌شده

- Compose project: `shekarchi-phase15-test`
- Application DB: `postgis/postgis:16-3.4`، database `shekarchi_phase15`، volume `shekarchi_phase15_app_pgdata`
- Keycloak DB: `postgres:16-alpine`، database `shekarchi_phase15_keycloak`، volume `shekarchi_phase15_keycloak_pgdata`
- Keycloak Realm: `shekarchi-phase15-test`
- Keycloak network: `shekarchi_phase15_net`
- OIDC discovery و application DB با identity واقعی Container تأیید شدند؛ `avgcrm` در مقصد تست وجود نداشت.
- Service Account تست با roleهای `view-users`, `query-users`, `manage-users` تأیید شد. برای emission roleهای client-credentials در Keycloak image فعلی `fullScopeAllowed` لازم بود؛ این مورد فقط در Realm تست فعال است و باید قبل از Production با mapper محدود جایگزین شود.
- SMS fake و payment disabled بودند؛ هیچ SMS/پرداخت واقعی انجام نشد.

### Migration و تست

- `alembic upgrade head` فقط روی application DB تست اجرا شد.
- Preflight قبل از pytest با موفقیت اجرا شد.
- Security Suite: `96 passed, 1 warning` در اجرای هدفمند.
- Full Suite نهایی: `682 passed, 15 skipped, 11 warnings` در 36.01 ثانیه.
- هیچ failure یا error در Full Suite باقی نماند.
- warningهای باقی‌مانده عمدتاً SQLAlchemy connection cleanup و یک warning deprecated از TestClient هستند.

### Seed و اعتبارسنجی

- Seed واقعی با batch `phase15-20261028` اجرا شد.
- اجرای دوم بدون رکورد تکراری موفق شد.
- Keycloak: دقیقاً ۲۵ حساب با roleهای واقعی Realm تست.
- Workspace: دقیقاً ۵ دفتر (`bronze`, `silver`, `gold`, `expired`, `pending`).
- Property scenario: دقیقاً ۶ رکورد شامل active، draft، withdrawn، personal owner و scraped.
- Subscription: پلن‌های Catalog واقعی `monthly`, `quarterly`, `yearly` و وضعیت‌های active/expired/pending.
- role distribution طبق Seed: USER=3، UNVERIFIED=2، OWNER=4، JUNIOR=4، SENIOR=4، OFFICE_MANAGER=4، DATA_ANALYST=2، SUPERVISOR=1، ADMIN=1.
- Cleanup Dry Run: `users=25, offices=5, properties=6`; هیچ رکوردی حذف نشد و حساب‌ها برای فازهای بعد حفظ شدند.

### اصلاحات تستی

- fixture Property جداول وابسته را کامل می‌سازد و cleanup را بدون lazy-load انجام می‌دهد.
- assertion OSM با تنظیمات واقعی فعلی هماهنگ شد.
- assertion منبع DIVAR دیگر فرض نادرست «canonical همیشه صفر است» ندارد.
- fixture engine در integration mode مقصد Phase 1.6 را بررسی می‌کند.

### توقف و Rollback امن

```text
docker compose --env-file /tmp/phase15-test.env \
  -f docker-compose.phase15-test.yml -p shekarchi-phase15-test stop
```

برای پاک‌سازی داده‌های batch فقط cleanup با `PHASE15_TEST_CLEANUP_DRY_RUN=YES` بررسی شده است؛ حذف واقعی نیازمند دستور جداگانه است. حذف volume فقط با project تست و نام‌های `shekarchi_phase15_*` مجاز است. هیچ `avg_*` container یا volume دست‌کاری نشد.
## الحاقیه Gate 1.7 — Public Publication Lifecycle & Media Authorization

- Schema/Migration proposal در `docs/public-publication-contract-proposal.md` بررسی و تأیید نشده باقی ماند.
- `app/services/publication_policy.py` policy مرکزی deny-by-default را بدون اتصال به Router یا DB اضافه کرد.
- Lifecycle پیشنهادی `DRAFT → PENDING_REVIEW → PUBLISHED → UNPUBLISHED` فقط طراحی است؛ `Property.status` تغییر نکرد.
- `PublicListingDTO` و `PublicMediaDTO` به allowlist مستقل با public ID، متن sanitized و مختصات تقریبی تکمیل شدند.
- هیچ Public API، media public URL، migration، model/table، Keycloak یا Production تغییر نکرد.
- تست Gate 1.7 در محیط Phase 1.6.2: `4 passed`.
- موارد نیازمند تأیید: migration و جدول‌های publication/media authorization/audit، فرآیند consent/review، فرمت public ID، CDN/derivative media و SLA لغو انتشار.

## الحاقیه Gate 1.8 — Publication Schema & Lifecycle Implementation

- مدل‌های `PropertyPublication`، `PropertyMediaPublication` و `PropertyPublicationAudit` اضافه شدند؛ همه‌ی defaults غیرعمومی هستند.
- Migration آماده‌ی اجرا در `alembic/versions/1c7e9a2b4d60_publication_contract.py` با head قبلی `f2a8c1d7b904` ثبت شد؛ **اجرا نشده است**.
- FK ترکیبی رسانه به `(property_id, media_id)` و unique pair برای `property_media` آماده شده است.
- `app/services/publication_lifecycle.py` عملیات consent، revoke، submit، review، media approval، schedule و unpublish را با scope/role checks و audit append-only آماده می‌کند.
- Membership صرف، share داخلی یا `view_summary` مجوز publication/review نیست؛ review فقط `ROLE_SUPERVISOR`/`ROLE_ADMIN` است.
- Public API، public media URL، Cache عمومی، Keycloak و Production تغییر نکردند.
- تست Gate 1.8 در Phase 1.6.2: `5 passed`.
- موارد نیازمند تأیید: قرارداد دقیق delegated consent، محتوای sanitized، moderator workflow، media derivative/CDN و اجرای migration.

## الحاقیه Gate 1.9 — Publication Migration Review & Lifecycle Security

- Migration `1c7e9a2b4d60` به head متصل است و اجرا نشد.
- نقص FK ترکیبی اصلاح شد: unique/reference هر دو ترتیب `(property_id, media_id)` دارند.
- Audit دیگر با حذف Publication cascade نمی‌شود و trigger append-only برای UPDATE/DELETE آماده شده است.
- Consent فقط برای owner ثبت می‌شود؛ delegated consent تا زمان تأیید مدل delegation فعال نیست.
- Review فقط برای Realm roleهای واقعی `ROLE_SUPERVISOR`/`ROLE_ADMIN` است، consent موجود لازم است و separation-of-duties رعایت می‌شود.
- Media approval بدون publication consent یا برای media متعلق به ملک دیگر رد می‌شود.
- Lifecycle از `FOR UPDATE` استفاده می‌کند؛ atomicity کامل وابسته به transaction boundary caller است.
- Gate 1.9 tests در محیط Phase 1.6.2: `5 passed`.
- Integration lifecycle با جدول‌های Publication عمداً اجرا نشد، چون Migration هنوز نیازمند تأیید است.
- بررسی offline کل زنجیره Alembic ابتدا به خطای موجود در migration قدیمی
  `e2f4a6b8c9d1_phase5_crm_and_pii_quota.py` رسید (`None.first()` در enum swap).
  مسیر Offline همان migration و `f1a2b3c4d5e6` برای enum role اصلاح شد؛ سپس زنجیره
  به introspection ناسازگار دیگری در `a3d7f1c95b24_scrape_job_source.py` رسید
  (`sa.inspect(MockConnection)`). بنابراین کل graph هنوز برای Offline SQL آماده
  نیست؛ هیچ migration اجرا یا stamp نشد.

### ریسک‌های باز و Gate 2

- مدل delegated consent هنوز وجود ندارد؛ managerهای Workspace عمداً نمی‌توانند consent بدهند.
- Audit trigger فقط پس از اجرای Migration فعال خواهد شد.
- Cache/media revocation و derivative storage هنوز پیاده‌سازی نشده‌اند.
- Gate 2 تا تصویب Migration، delegation، moderation و media delivery آماده نیست.
## الحاقیه Gate 1.9.2 — Chain-Wide Alembic Audit

### نتیجه Graph و وضعیت تست DB

- Head: `1c7e9a2b4d60`
- Branchpoint: `0a8b5dea0d94` با دو شاخه که در `4f8b2d1c6a90` merge می‌شوند.
- `alembic_version` دیتابیس disposable روی `f2a8c1d7b904` باقی ماند؛ هیچ upgrade/stamp اجرا نشد.

### طبقه‌بندی

| دسته | Migrationها/الگو | نتیجه |
|---|---|---|
| A: DDL-only قابل Offline/Online | initial schema و جدول‌ها/column/indexهای بدون catalog read | کم‌ریسک؛ type/extensionهای Postgres باید بررسی شوند |
| B: Offline با Patch محدود | `e2f4a6b8c9d1`، `f1a2b3c4d5e6`، `a3d7f1c95b24`، `b7e2c9a4d103` | introspection/enum catalog در Offline branch شده؛ Online مسیر اصلی حفظ شده |
| C: ذاتاً Online/data-dependent | `c2f71a4d9b30` referral backfill، downgradeهای `d9b41e7a2c63`/`e7c3b9a4216f` | نیازمند داده واقعی و transaction آنلاین؛ SQL حدسی Offline تولید نمی‌شود |
| D: ریسک واقعی Online | enum label ناشناخته، FK/unique collision و backfill ناسازگار | snapshot و پیش‌شرط داده لازم؛ عبور از Offline Exception کافی نیست |

### یافته‌های کلیدی

- علت اولیه `None.first()` در `e2f4a6b8c9d1` MockConnection Offline بود و Patch محدود شد.
- `f1a2b3c4d5e6` و `a3d7f1c95b24` نیز catalog introspection مشابه داشتند و Offline branch قطعی گرفتند.
- Offline chain اکنون تا `c2f71a4d9b30` پیش می‌رود و آنجا به خواندن agencyها و تولید referral code وابسته می‌شود؛ این migration ذاتاً Online-only است و Patch حدسی اعمال نشد.
- Migration انتشار `1c7e9a2b4d60` از نظر dependency/FK/enum/index و audit trigger بررسی شد؛ اجرا نشده است.

### Validation Online پیشنهادی، اجرا نشده

1. Preflight و تأیید issuer/DB identity.
2. Snapshot از schema و `alembic_version` دیتابیس disposable.
3. تأیید `f2a8c1d7b904` و داده‌های پیش‌نیاز agency/property/payment.
4. اجرای upgrade فقط پس از تأیید صریح.
5. بررسی enum labels، FK/unique/index/trigger و row counts.
6. اجرای Integration Suite.
7. آزمون downgrade فقط روی clone disposable؛ Audit غیرخالی باید downgrade را رد کند.
8. rollback فقط با snapshot/volume تست و بدون لمس `avg_*`.

وضعیت Gate 1.9.2: **BLOCKED برای Online Validation**؛ graph قابل‌تشخیص است، اما `c2f71a4d9b30` و migrationهای data-dependent نیازمند اجرای کنترل‌شده آنلاین هستند.

## الحاقیه Gate 1.9.3 — Online Migration Preflight & Referral Verification

- مسیر واقعی از `f2a8c1d7b904` به `1c7e9a2b4d60` شامل `c2f71a4d9b30` است؛ این revision هنوز در `alembic_version` ثبت نشده است.
- Migration Referral با batchهای 500تایی، کد تصادفی `SH`+10 کاراکتر، query یکتایی و unique index کار می‌کند؛ agencyهای بدون code باید backfill شوند.
- کدهای خالی/تکراری پیش‌شرط خطرناک هستند؛ unique index در حالت Online باید قبل از backfill با داده واقعی بررسی شود.
- اصلاح Gate 1.9.4: وجود `agency_referral`، `referral_credit` و `ix_agency_referral_code` با `alembic_version=f2a8c1d7b904` تناقض ندارد؛ `f2a8c1d7b904` از mergepoint `4f8b2d1c6a90` عبور کرده و ancestors آن شامل `c2f71a4d9b30` است. بنابراین c2 قبلاً در مسیر revision اعمال‌شده محسوب می‌شود و نباید دوباره اجرا شود. provenance دقیق (Alembic upgrade در برابر create_all) بدون audit log قطعی نیست، اما schema و constraintها با c2 منطبق‌اند.
- تعداد Agency تست: 5؛ مقدارهای referral خالی/NULL/تکراری: 0/0/0. این فقط وضعیت فعلی است و جایگزین بررسی migration history نیست.
- Migration انتشار `1c7e9a2b4d60` هنوز اجرا نشده و جدول Publication وجود ندارد.
- هیچ Snapshot، Restore، Upgrade، Stamp یا تغییر داده‌ای انجام نشد.

### آمادگی Online

Online Validation برای c2 به‌دلیل revision فعلی لازم نیست؛ migration referral نباید دوباره اجرا شود. اجرای migration انتشار از `f2a8c1d7b904` به `1c7e9a2b4d60` فقط پس از Snapshot و تأیید صریح مجاز است. `stamp` یا حذف جدول مجاز نیست.

### Snapshot/Restore Runbook (اجرا نشده)

1. اجرای Preflight و ثبت `current_database`, server address/port و `alembic_version`.
2. توقف Write فقط در Compose تست و گرفتن `pg_dump --format=custom` از DB تست؛ secret در command/log چاپ نشود.
3. ذخیره checksum فایل dump و ثبت schema-only dump جداگانه.
4. Restore فقط به DB جدید با نام `shekarchi_phase15_restore_<timestamp>` و همان network تست؛ هرگز روی `avgcrm` یا volume موجود.
5. مقایسه revision، جدول‌ها، indexها، FKها و row counts قبل از هر upgrade.
6. اجرای migration فقط پس از تأیید صریح و سپس اجرای Integration Suite.
7. حذف clone restore فقط با نام دقیق project تست و تأیید دوگانه؛ volume اصلی تست و داده‌های 25 حساب حذف نشوند.

## الحاقیه Gate 1.9.4 — Schema Drift Forensics

- Revision فعلی `f2a8c1d7b904` ancestorهای `4f8b2d1c6a90` و `c2f71a4d9b30` را در خود دارد؛ c2 در مسیر Upgrade به head قبلاً اجراشده محسوب می‌شود.
- Schema واقعی referral با migration c2 منطبق است: ستون‌ها، enumها، FKهای `RESTRICT`، uniqueها، checkهای distinct/percent و indexها همگی وجود دارند.
- داده‌ها: Agency=5، Referral=0، Credit=0، orphanها=0، codeهای NULL/خالی/تکراری=0.
- نتیجه forensic: Drift قابل اقدام اثبات نشد؛ مشاهده جدول‌های Referral در revision f2 طبیعی است. فقط provenance دقیق create_all در برابر upgrade بدون audit log قابل اثبات قطعی نیست.
- اجرای مستقیم c2 خطرناک و غیرضروری است و می‌تواند duplicate column/table/index ایجاد کند؛ نباید اجرا شود.
- گزینه پیشنهادی: حفظ DB و revision فعلی، گرفتن snapshot disposable و فقط بررسی مسیر `f2a8c1d7b904 → 1c7e9a2b4d60` روی clone.
- Gate 1.9.5 برای migration publication پس از Snapshot و تأیید صریح آماده می‌شود؛ Migration/Stamp/Restore در این Gate اجرا نشد.

## الحاقیه Gate 1.9.5 — Disposable Clone & Publication Migration Validation

- تأیید صریح کاربر دریافت شد؛ فقط Clone مستقل استفاده شد.
- Snapshot custom format از `shekarchi_phase15` ساخته و در `/tmp` نگهداری شد؛ secret در گزارش چاپ نشد.
- Clone: database `shekarchi_phase15_clone`، user `phase15_clone`، container مستقل `shekarchi-phase15-clone-db` و volume `shekarchi_phase15_clone_pgdata`.
- Revision Clone قبل از اجرا: `f2a8c1d7b904`؛ بعد از اجرا: `1c7e9a2b4d60`.
- Upgrade فقط روی Clone موفق شد؛ Application DB اصلی همچنان `f2a8c1d7b904` و بدون Publication tables باقی ماند.
- Schema بررسی شد: سه Publication table، Enumها، FK ترکیبی Media، Unique public ID، defaults و Audit trigger.
- Audit append-only با UPDATE مصنوعی رد شد و رکورد اصلی حفظ شد.
- Downgrade روی Clone دارای Audit با خطای محافظتی مورد انتظار متوقف شد و revision روی `1c7e9a2b4d60` باقی ماند.
- Publication security tests روی Clone: `5 passed`.
- ریسک باقی‌مانده: downgrade موفق روی Clone خالی/بدون Audit و بررسی کامل runtime lifecycle جداگانه انجام نشده است.
- وضعیت Gate 1.9.5: **PASS برای Migration روی Clone**؛ DB اصلی، Production، Keycloak عملیاتی و Public API تغییر نکردند.
## Final Execution — Gate 1 Completion

- Clone preflight با target صریح `clone` اصلاح و موفق شد؛ Original DB همچنان روی `f2a8c1d7b904` ماند.
- Sanitization Server-side، نسخه hash متن، Separation of Duties، Media derivative fail-closed و Lifecycle transaction locking تکمیل شدند.
- مدل enum `PriceChangeSource` با نوع واقعی `price_source` سازگار شد.
- Fixtureهای Property/Matching اصلاح شدند؛ cleanup ابتدا Price History را حذف می‌کند.
- Full Suite روی Clone با JUnit XML اجرا شد: `704 passed, 9 warnings`, exit code `0`، مدت `38.11s`.
- Security/Publication tests در همین اجرا پوشش داده شدند؛ تست‌های Publication مستقل نیز `7 passed` بودند.
- Clone migration روی `1c7e9a2b4d60` باقی ماند؛ Original DB بدون Publication table و روی `f2a8c1d7b904` باقی ماند.
- هیچ Public API، Production، avgcrm، Keycloak عملیاتی، SMS یا Payment واقعی تغییر نکرد.
- Warningهای باقی‌مانده عمدتاً connection cleanup مربوط به تست‌های SQLite و deprecation TestClient هستند و شکست امنیتی نیستند.

**تصمیم نهایی Gate 1: PASS مشروط به تأیید محصول برای ورود به Gate 2.**
