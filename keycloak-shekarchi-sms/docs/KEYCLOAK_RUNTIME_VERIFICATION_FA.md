# راستی‌آزمایی Runtime بازیابی Keycloak

این Runbook ابتدا Image و Factory را روی دیتابیس خالی و موقت آزمایش می‌کند؛ سپس فقط بعد از تأیید Backup، همان Candidate روی Clone Backup آزمایش می‌شود. هیچ مرحله‌ای به دیتابیس عملیاتی وصل نمی‌شود.

## ۱. بررسی Image Candidate

از پوشه `keycloak-shekarchi-sms`:

```bash
docker build --pull \
  --build-arg KEYCLOAK_VERSION=26.0.8 \
  -f Dockerfile.keycloak-26.0.8 \
  -t shekarchi-keycloak:26.0.8-recovery-candidate .

docker run --rm --network none \
  --entrypoint /opt/keycloak/bin/kc.sh \
  shekarchi-keycloak:26.0.8-recovery-candidate --version
```

باید نسخه `26.0.8` گزارش شود. این Image یک Tag مستقل دارد و Tag عملیاتی 26.0.0 را جایگزین نمی‌کند.

## ۲. تست تازه و ایزوله

```bash
docker compose -f docker-compose.runtime-test.yml \
  -p shekarchi-keycloak-2608-runtime-test up --build -d

docker compose -f docker-compose.runtime-test.yml \
  -p shekarchi-keycloak-2608-runtime-test ps

docker compose -f docker-compose.runtime-test.yml \
  -p shekarchi-keycloak-2608-runtime-test logs --no-color keycloak
```

پذیرش: Keycloak Healthy، بدون خطای Liquibase، `kc.sh build` موفق و Admin API آزمایشی شامل `shekarchi-sms-authenticator`. تست Flow باید با Test Realm و Fake SMS اجرا شود. هیچ Credential یا توکن در خروجی ذخیره یا گزارش نشود.

پاک‌سازی مجاز فقط پس از بررسی نام Project آزمایشی:

```bash
docker compose -f docker-compose.runtime-test.yml \
  -p shekarchi-keycloak-2608-runtime-test down --volumes --remove-orphans
```

این فرمان را فقط وقتی اجرا کنید که `ps` و `docker volume ls` نشان دهند منابع متعلق به همین تست مستقل هستند.

## ۳. تست Clone Backup

پس از تأیید و اعتبارسنجی Backup، Restore آن را طبق `KEYCLOAK_BACKUP_RESTORE_FA.md` در PostgreSQL مجزا انجام دهید. سپس Candidate را به Clone وصل کنید و ثبت‌های اولیه را قبل/بعد به‌صورت شمارش کلی مقایسه کنید:

```sql
BEGIN READ ONLY;
SELECT 'realm' AS entity, count(*) FROM public.realm
UNION ALL SELECT 'users', count(*) FROM public.user_entity
UNION ALL SELECT 'clients', count(*) FROM public.client
UNION ALL SELECT 'authentication_flows', count(*) FROM public.authentication_flow;
ROLLBACK;
```

این Query فقط روی Clone اجرا شود. هیچ نام کاربر، ایمیل، شماره تلفن، Credential یا محتوای Realm گزارش نشود.

همچنین بررسی کنید:

- `migration_model.version` قبل از اجرای Candidate برابر 26.0.8 باشد.
- Changesetهای مربوط به پاک‌سازی Index همچنان در تاریخچه باشند.
- Indexهای حذف‌شده به‌صورت ساختگی بازسازی نشده باشند.
- هیچ Migration Error یا `Unable to find factory` در Startup جدید نباشد.
- Factory از Admin API آزمایشی کشف شود.
- Realm، کاربران، Clientها و Flowها با شمارش‌های قبل از تست برابر باشند.
- Login آزمایشی و Fake SMS موفق شود؛ هیچ SMS واقعی ارسال نشود.

## ۴. توقف فوری و وضعیت استقرار

در صورت خطای Migration، عدم کشف Factory، تغییر شمارش موجودیت‌ها، دسترسی Clone به شبکه عملیاتی یا Health Check ناموفق، تست را متوقف کنید و دیتابیس Clone را حفظ کنید تا علت بررسی شود.

Deploy عملیاتی، توقف Restart Loop، تغییر Compose عملیاتی و جایگزینی کانتینر تا تأیید صریح جداگانه انجام نمی‌شود. پیش از Deploy باید Backup معتبر، Restore آزمایش‌شده، Image Digest و Checksum JAR ثبت شده باشند.
