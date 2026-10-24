# بازیابی نسخه Keycloak بدون از دست‌دادن داده

## تشخیص تأییدشده

- Image عملیاتی گزارش‌شده: `shekarchi-keycloak:26.0.0` و باینری آن واقعاً `26.0.0` است.
- مقدار `public.migration_model.version`: `26.0.8`.
- چهار Changeset پاک‌سازی Index در `DATABASECHANGELOG` با شناسه‌های مجزا و وضعیت `EXECUTED` ثبت شده‌اند.
- ایندکس `idx_offline_uss_createdon` وجود ندارد؛ این با اجرای موفق cleanup سازگار است.
- لاگ باینری 26.0.0 تلاش برای اجرای شناسه تجمیعی `25.0.0-28265-index-cleanup` را نشان می‌دهد که در `DATABASECHANGELOG` فعلی ثبت نشده است.
- بنابراین مسئله، ناسازگاری runtime/changelog با Schema مهاجرت‌شده است. ایجاد Index، ویرایش `DATABASECHANGELOG` یا Import مجدد Realm راهکار نیست.

## وضعیت کد و نسخه هدف

`pom.xml` فعلی نسخه SPI را به‌صورت پیش‌فرض روی 26.0.0 دارد. فایل `Dockerfile.keycloak-26.0.8` برای ساخت Recovery Candidate، مقدار Maven را با `-Dkeycloak.version=26.0.8` به تمام dependencyهای Keycloak می‌دهد و Base Image را هم روی 26.0.8 ثابت می‌کند. Dockerfile و Compose عملیاتی اجرا یا جایگزین نمی‌شوند.

قبل از استفاده از Image کاندیدا باید این موارد موفق شوند:

1. `mvn -Dkeycloak.version=26.0.8 clean verify`
2. ساخت Image با Tag مستقل `shekarchi-keycloak:26.0.8-recovery-candidate`
3. Startup و Factory Discovery روی PostgreSQL موقت
4. Backup معتبر و Restore کامل روی Clone ایزوله
5. Startup Candidate روی Clone دیتابیس و تطبیق تعداد موجودیت‌ها

Image محلی 26.3.2 نیز نسخه متفاوتی است و Provider فعلی را ندارد؛ استفاده از آن مسیر ارتقاست، نه جایگزین مستقیم. هرگونه ارتقای جلوتر از 26.0.8 باید جداگانه روی Clone ارزیابی شود.

## محدودیت عملیاتی

درست‌کردن نسخه فایل Compose روی دیسک با Deploy یکی نیست. هیچ‌کدام از کانتینرهای عملیاتی، Image عملیاتی، دیتابیس، Realm یا Secretها نباید بدون تأیید صریح تغییر کنند. بازگشت صرفاً به Image قدیمی، در حالی که Schema جدید باقی است، Rollback معتبر نیست.
