# برنامه فاز نهایی مسکنچی (Maskanchi Final Phase Plan)
**کد سند:** `MASKANCHI-FINAL-PHASE-2026-V1`
**تاریخ صدور:** ۱۲ مهر ۱۴۰۵ (اکتبر ۲۰۲۶)
**وضعیت:** مصوب توسعه محلی — مرجع ماندگار تیم
**حالت احراز هویت فعلی:** `AUTH_MODE=LICENSE` (توسعه محلی، موقت)

---

## ۱. نقطه شروع (وضعیت فعلی — چه چیزی تمام شده)

### ۱.۱ بک‌اند (FastAPI — پورت 8080)
| قابلیت | وضعیت | مرجع کد |
|---|---|---|
| مدل‌های دامنه (Property، Owner PII، PriceHistory، Media) | ✅ انجام شده | `app/models/` |
| PII Vault (Fernet + Blind Index) + لاگ ممیزی | ✅ انجام شده | `app/core/crypto.py`، `app/models/owner_access_log.py` |
| Valuation / AVM + تست | ✅ انجام شده | `app/services/valuation.py`، `tests/test_valuation.py` |
| Dedup مکانی (Haversine + امتیازدهی، merge ۰٫۷۸) | ✅ انجام شده | `app/services/ingestion/deduplicator.py` |
| CRM پنج‌ستونه + گذارهای محافظت‌شده + تست | ✅ انجام شده | `app/services/crm.py`، `tests/test_phase5_crm_and_vault.py` |
| سهمیه PII + مسیر reveal-contact | ✅ انجام شده | `app/services/pii_vault.py` |
| RBAC هفت‌نقشی | ✅ انجام شده | `app/models/enums.py` |
| User Directory واقعی (`agency_user`) | ✅ انجام شده | `app/api/v1/endpoints/users.py` |
| هویت Keycloak (JWKS، Principal) — غیرفعال در LICENSE | ✅ کد آماده، غیرفعال | `app/core/identity.py` |
| ۱۶۸+ تست بک‌اند | ✅ سبز | `tests/` |

### ۱.۲ فرانت‌اند (Next.js — پورت 3000)
| قابلیت | وضعیت | مرجع کد |
|---|---|---|
| رادار شکار قیمت | ✅ انجام شده | `src/features/properties/` |
| جزئیات ملک + تایم‌لاین قیمت | ✅ انجام شده | `property-detail-page.tsx` |
| ویزارد ثبت مستقیم (۳ مرحله‌ای + Reverse-Geocode) | ✅ انجام شده | `submit-property-page.tsx` |
| بورد CRM پنج‌ستونه با DnD | ✅ انجام شده | `src/features/crm/` |
| جدول کاربران واقعی (`/dashboard/users`) | ✅ انجام شده، داده زنده | `src/features/users/api/service.ts` |
| فارسی‌سازی قیمت/ارقام، منوی Maskanchi | ✅ انجام شده | `src/lib/utils.ts` |
| بای‌پس احراز هویت — قابل بازگردانی، موقت | ✅ انجام شده | `src/hooks/use-auth.ts` |

### ۱.۳ قوانین معماری (تغییرناپذیر)
1. `visit_date` در هیچ جدول/اسکیما/پیلودی وجود ندارد؛ زمان بازدید فقط `LeadInteraction` با نوع `VISIT_EVENT`.
2. شماره تماس هرگز plain ذخیره/لاگ نمی‌شود؛ فقط `encrypted_contact_phone` + `blind_index_phone`.
3. تقدم منبع: ثبت مستقیم مالک (۱۰۰) > دفتر (۸۰) > اسکرپ (۴۰).
4. WebSocket هرگز PII ارسال نمی‌کند (هنوز پیاده نشده — بند ۲٫۴).


## ۲. کارهای فاز نهایی (چه چیزی مانده)

### ۲.۱ اتصال Keycloak — راه B (اولویت ۱)
وضعیت فعلی موقت است: همه به‌عنوان bootstrap operator با نقش ADMIN دیده می‌شوند.
- [ ] فعال‌سازی ریلم `maskanchi-platform` و ثبت `KEYCLOAK_ISSUER` / `KEYCLOAK_AUDIENCE` در `.env` بک‌اند
- [ ] افزودن interceptor در `users/api/service.ts` و `crm/api/client.ts` برای ارسال `Authorization: Bearer` (محل توکن: Clerk session یا localStorage)
- [ ] برگرداندن `.env` به `AUTH_MODE=KEYCLOAK` و restart uvicorn پورت 8080
- [ ] خاموش کردن `NEXT_PUBLIC_AUTH_BYPASS` در `frontend/.env`
- [ ] تست سرتاسری: کاربر تأییدنشده → 403؛ GUEST → 403 روی `/users`؛ ADMIN → 200

### ۲.۲ نقشه واقعی OSM/Leaflet (اولویت ۲)
ویزارد فعلاً ورودی عددی مختصات + Reverse-Geocode است، نه نقشه تعاملی.
- [ ] افزودن `leaflet` + `react-leaflet` به `frontend/package.json`
- [ ] ساخت `location-picker.tsx` (پین‌گذاری، تم تیره Obsidian)
- [ ] جایگزینی ورودی عددی در `submit-property-page.tsx`
- [ ] نمایش blur تقریبی (±۲۰۰m) در ویترین عمومی

### ۲.۳ تم Ultra-Luxury Glassmorphism (اولویت ۳)
`lang='fa' dir='rtl'` فعال است، اما پالت لوکس اعمال نشده.
- [ ] متغیرهای CSS در `globals.css`: `#060b13`، `#ffd8be` / `#e5a87b`، `#00f5a0`
- [ ] کلاس `glass-panel` و اعمال روی کارت‌های رادار/CRM
- [ ] فونت Vazirmatn و RTL کامل کامپوننت‌های Radix

### ۲.۴ WebSocket لید زنده (اولویت ۴)
کانبان فعلاً refresh است، نه push زیر ۳ ثانیه.
- [ ] هاب `wss://…/ws/v1/broker-leads` در بک‌اند (بدون PII، heartbeat ۳۰ ثانیه)
- [ ] هوک `useLeadSocket` در `src/features/crm/hooks/` و اتصال به `LeadBoard`
- [ ] تست p95 < ۵۰۰ms و عدم نشت PII در پیام‌ها

### ۲.۵ pHash رسانه (اولویت ۵)
مدل `property_media` هست ولی هش ادراکی نیست.
- [ ] محاسبه pHash هنگام آپلود + پرچم `SUSPECTED_MEDIA_REUSE`
- [ ] اثر روی `quality_score` و صف بازبینی SUPERVISOR

### ۲.۶ بدهی‌های کوچک
- [ ] یکدست‌سازی ایمپورت تکراری `select` در `endpoints/crm.py`
- [ ] تصمیم آستانه AVM (−۱۲٪ سند ↔ −۱۵٪ کد) و تلورانس متراژ (۵٪ ↔ ۳٪) — فعلاً کد ملاک است
- [ ] اتصال دکمه PATCH قیمت در فرانت (endpoint بک‌اند `POST` است)

---

## ۳. معیار پذیرش فاز نهایی (Definition of Done)
1. `AUTH_MODE=KEYCLOAK` فعال و جدول users با توکن واقعی کار می‌کند.
2. ثبت ملک با پین نقشه → district فارسی درست → دیده‌شدن در CRM.
3. دو ملک همسان در ۴۵ متری → یک master + یک `price_history`؛ در ۵۵ متری → دو master مستقل.
4. رمزگشایی تماس → کسر سهمیه + ثبت ممیزی؛ اتمام سهمیه → 403 فارسی.
5. `tsc --noEmit` پاک، `oxlint` صفر خطا، `next build` موفق، `pytest` سبز.
6. هیچ `visit_date`، هیچ شماره plain، هیچ PII در WebSocket/لاگ.

---

## ۴. تاریخچه تغییرات
| تاریخ | تغییر |
|---|---|
| ۱۲ مهر ۱۴۰۵ | صدور نسخه اول؛ ثبت سوئیچ LICENSE و فهرست کارهای مانده |
