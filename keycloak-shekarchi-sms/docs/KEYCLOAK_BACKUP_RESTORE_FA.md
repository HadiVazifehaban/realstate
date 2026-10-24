# Backup و Restore آزمایشی Keycloak

> دستورات این راهنما فقط پس از تأیید صریح مالک سرویس اجرا شوند. تا پیش از تأیید، هیچ Backup یا Clone عملیاتی تهیه نشود.

## پیش‌شرط‌ها

1. تأیید مقصد امن و محدوددسترسی برای Backup.
2. بررسی اندازه DB و فضای آزاد. فضای مقصد حداقل برابر اندازه فشرده Backup به‌علاوه فضای لازم برای Clone باشد؛ برای برنامه‌ریزی اولیه، حداقل 2 برابر اندازه دیتابیس در نظر گرفته شود.
3. اطمینان از اینکه هیچ Keycloak دیگری روی همان دیتابیس در حال Migration نیست.
4. استفاده از مسیر با مجوز `0700` و فایل با مجوز `0600`.
5. Backup شامل داده‌های کاربران است؛ Clone فقط در شبکه داخلی آزمایشی و با SMS جعلی اجرا شود.

## بررسی فضای دیسک و اندازه دیتابیس (Read-Only)

```bash
docker exec avg_keycloak_db sh -ec \
  'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT pg_database_size(current_database())"'
df -B1 /var/backups
```

مسیر `/var/backups/keycloak` باید توسط اپراتور بررسی و با مجوز محدود آماده شود. ساخت مسیر و نوشتن Backup را بدون مجوز اجرا نکنید.

## ساخت Backup سفارشی PostgreSQL

پس از تأیید:

```bash
set -euo pipefail
umask 077
BACKUP_DIR=/var/backups/keycloak
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="$BACKUP_DIR/keycloak-$STAMP.dump"

docker exec avg_keycloak_db sh -ec \
  'exec pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$BACKUP"
test -s "$BACKUP"
chmod 600 "$BACKUP"
pg_restore --list "$BACKUP" > "$BACKUP.list"
chmod 600 "$BACKUP.list"
sha256sum "$BACKUP" > "$BACKUP.sha256"
chmod 600 "$BACKUP.sha256"
stat --format='size=%s mode=%a file=%n' "$BACKUP"
cat "$BACKUP.sha256"
```

محتوای `pg_restore --list` داده کاربران را چاپ نمی‌کند، اما نام Schema و جدول‌ها را نشان می‌دهد؛ فایل فهرست هم محرمانه نگهداری شود. خروجی دستورات نباید شامل Credential باشد.

## Restore روی Clone ایزوله

1. با Project Name، Network و Volume کاملاً مستقل یک PostgreSQL آزمایشی ایجاد کنید؛ هیچ Volume یا Network عملیاتی را mount یا join نکنید.
2. نسخه PostgreSQL Clone را با نسخه Source هماهنگ کنید.
3. دیتابیس و Role آزمایشی را با نام‌های جداگانه بسازید.
4. Backup را فقط read-only به Clone mount کنید.
5. Restore را روی دیتابیس خالی Clone، با `pg_restore --exit-on-error --no-owner` اجرا کنید.
6. Keycloak Candidate را فقط به Clone وصل کنید و SMS جعلی را فعال نگه دارید.
7. بعد از تست، فقط منابع دارای Project Label آزمایشی را حذف کنید؛ Volume و منابع عملیاتی دست‌نخورده بمانند.

نمونه فرمان Restore پس از آماده‌شدن Clone خالی و ایزوله:

```bash
docker exec -i shekarchi-kc-recovery-postgres \
  pg_restore --exit-on-error --no-owner -U keycloak_test -d keycloak_test \
  < /secure/path/keycloak-UTC_TIMESTAMP.dump
```

این نمونه فقط برای Clone است. اجرای آن روی `avg_keycloak_db` ممنوع است.

## Rollback

Rollback نسخه‌ای یعنی بازگرداندن هم‌زمان Artifact/پیکربندی قبلی و Backup دیتابیس متناظر همان نسخه. برگرداندن Image 26.0.0 روی دیتابیسی با `migration_model=26.0.8` Rollback معتبر نیست.
