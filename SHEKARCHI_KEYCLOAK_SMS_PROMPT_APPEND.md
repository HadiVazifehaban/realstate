# بخش تکمیلی پرامپت اجرایی SHEKARCHI

## توسعه Keycloak SMS OTP SPI، احراز هویت بدون رمز و MFA

این بخش مکمل پرامپت اصلی توسعه سامانه شکارچی است و باید در همان مخزن، معماری، استاندارد کدنویسی و چرخه تحویل پروژه اجرا شود.

هدف این بخش، پیاده‌سازی یک افزونه‌ (Extension) مستقل و Production-Ready برای Keycloak جهت پشتیبانی از ورود با SMS OTP، MFA پس از رمز عبور و انتخاب روش ورود است.

## ۱. هدف فنی

ایجاد ماژول Maven مستقل با نام `keycloak-shekarchi-sms` شامل دو مؤلفه اصلی:

1. **`SmsSenderService`** – قرارداد کاملاً مستقل برای ارسال پیامک و مجموعه Providerهای درگاه پیامکی
2. **`SmsAuthenticator`** – پیاده‌سازی `Authenticator` و `AuthenticatorFactory` جهت یکپارچه‌سازی با Authentication Flow های Keycloak

**اصل کلیدی:** سرویس ارسال پیامک باید کاملاً از منطق احراز هویت جدا باشد. هیچ وابستگی مستقیم بین `SmsAuthenticator` و پیاده‌سازی خاص درگاه پیامکی نباید وجود داشته باشد.

## ۲. تطبیق نسخه Keycloak (الزامی)

قبل از هرگونه نوشتن کد، نسخه واقعی Keycloak مورد استفاده در پروژه را شناسایی کن:

- بررسی `docker-compose*.yml`، `docker-compose*.yaml`، `.env`، `values.yaml`، `helm/` و هر فایل پیکربندی مرتبط
- استخراج دقیق Image Tag Keycloak (مثال: `quay.io/keycloak/keycloak:26.x.x` یا `keycloak/keycloak:26.x.x`)
- استخراج اطلاعات مربوط به Quarkus Runtime در نسخه هدف
- تطبیق دقیق تمام وابستگی‌های Maven با نسخه هدف:

```xml
<dependency>
  <groupId>org.keycloak</groupId>
  <artifactId>keycloak-server-spi</artifactId>
  <version>${keycloak.version}</version>
  <scope>provided</scope>
</dependency>
<dependency>
  <groupId>org.keycloak</groupId>
  <artifactId>keycloak-server-spi-private</artifactId>
  <version>${keycloak.version}</version>
  <scope>provided</scope>
</dependency>
<dependency>
  <groupId>org.keycloak</groupId>
  <artifactId>keycloak-services</artifactId>
  <version>${keycloak.version}</version>
  <scope>provided</scope>
</dependency>
<dependency>
  <groupId>org.keycloak</groupId>
  <artifactId>keycloak-core</artifactId>
  <version>${keycloak.version}</version>
  <scope>provided</scope>
</dependency>
```

**نباید نسخه فرضی انتخاب شود.** اگر نسخه در هیچ فایل یافت نشد، حتماً از کاربر بپرس قبل از ادامه.

## ۳. ساختار ماژولار پیشنهادی

ماژول را در ریشه مخزن ایجاد کن (در صورت وجود ساختار multi-module، مطابق با الگوی موجود قرار بده).

```text
keycloak-shekarchi-sms/
├── pom.xml
├── README.md
├── docs/
│   ├── DEPLOYMENT.md
│   ├── REALM_CONFIG.md
│   ├── SECRETS.md
│   ├── TROUBLESHOOTING.md
│   └── TEST_REPORT.md
├── scripts/
│   ├── build.sh
│   ├── deploy.sh
│   └── health-check.sh
├── src/
│   ├── main/
│   │   ├── java/com/shekarchi/auth/
│   │   │   ├── sms/
│   │   │   │   ├── SmsSenderService.java
│   │   │   │   ├── SmsSenderServiceFactory.java
│   │   │   │   ├── SmsException.java
│   │   │   │   ├── SmsSpi.java
│   │   │   │   └── provider/
│   │   │   │       ├── KavenegarSmsSenderService.java
│   │   │   │       ├── KavenegarSmsSenderServiceFactory.java
│   │   │   │       ├── FarazSmsSenderService.java
│   │   │   │       ├── FarazSmsSenderServiceFactory.java
│   │   │   │       ├── MelliPayamakSmsSenderService.java
│   │   │   │       └── MelliPayamakSmsSenderServiceFactory.java
│   │   │   ├── authenticator/
│   │   │   │   ├── SmsAuthenticator.java
│   │   │   │   └── SmsAuthenticatorFactory.java
│   │   │   ├── model/
│   │   │   │   └── OtpState.java  (immutable)
│   │   │   ├── util/
│   │   │   │   ├── PhoneNormalizer.java
│   │   │   │   ├── OtpGenerator.java
│   │   │   │   └── OtpHmacUtil.java
│   │   │   └── config/
│   │   │       └── SmsAuthConfig.java
│   │   └── resources/
│   │       ├── META-INF/
│   │       │   └── services/
│   │       │       ├── org.keycloak.provider.Spi
│   │       │       ├── org.keycloak.authentication.AuthenticatorFactory
│   │       │       └── com.shekarchi.auth.sms.SmsSenderServiceFactory
│   │       └── theme-resources/templates/shekarchi/
│   │           ├── login-sms.ftl
│   │           ├── login-otp.ftl
│   │           ├── login-method-select.ftl
│   │           └── login-error.ftl
│   └── test/
│       ├── java/
│       └── resources/
```

## ۴. ثبت Custom SPI در Keycloak

صرف اینکه `SmsSenderService extends Provider` کفایت نمی‌کنه. باید یک **Custom SPI** معتبر تعریف شه.

### ۴.۱ کلاس `SmsSpi`
- `isInternal() = false`
- `getName() = "shekarchi-sms"`
- `getProviderClass() = SmsSenderService.class`
- `getProviderFactoryClass() = SmsSenderServiceFactory.class`

### ۴.۲ فایل‌های Service Loader
- `META-INF/services/org.keycloak.provider.Spi` → `com.shekarchi.auth.sms.SmsSpi`
- `META-INF/services/com.shekarchi.auth.sms.SmsSenderServiceFactory` → فهرست Provider Factories
- `META-INF/services/org.keycloak.authentication.AuthenticatorFactory` → `com.shekarchi.auth.authenticator.SmsAuthenticatorFactory`

## ۵. امنیت و چرخه عمر OTP

- تولید با `SecureRandom`، دقیقاً ۶ رقم
- OTP نباید به‌صورت خام ذخیره شه. از HMAC با کلید محرمانه خارج از سورس (`SHEKARCHI_OTP_HMAC_SECRET`) استفاده کن
- State فقط در **AuthenticationSession** نگه‌داری شه. از Singleton/static پرهیز کن
- کنترل‌های TTL، max attempts، resend cooldown، resend limit در window، consumed flag
- اتصال OTP به sessionId + phoneNormalized
- حذف/بی‌اعتبارسازی پس از مصرف موفق
- جلوگیری از Race Condition منطقی
- هیچ OTP/Secret در Log ثبت نشه

## ۶. سه سناریو احراز هویت

1. **Passwordless Fast OTP**: phone → send → verify → find/create user → success
2. **Password + SMS MFA**: username/password → validate → require MFA only if needed → send to verified phone → verify → success
3. **Login Method Selection**: صفحه انتخاب صریح با دو گزینه. **صرف ALTERNATIVE کافی نیست**؛ حتماً فرم سفارشی پیاده‌سازی شه

## ۷. ایجاد حساب عمومی امن

- فقط در حالت Passwordless پس از OTP موفق
- جستجو بر پایه شماره نرمال‌سازی شده
- جلوگیری از ایجاد تکراری هم‌زمان
- فقط نقش‌های مجاز: ROLE_JUNIOR_BROKER, ROLE_SENIOR_BROKER, ROLE_AGENCY_MANAGER, ROLE_DATA_ANALYST
- هرگز ROLE_ADMIN/ROLE_SUPERVISOR تخصیص نده
- phoneVerified = true فقط پس از OTP موفق
- user enabled = true، حداقل دسترسی عمومی

## ۸. Theme و UI

- حفظ تم `shekarchi` موجود
- قالب‌های: login-sms.ftl, login-otp.ftl, login-method-select.ftl, login-error.ftl
- RTL، هماهنگ با گلس‌مورفیسم دارک/طلایی، اعداد فارسی نمایش/انگلیسی ورودی
- جلوگیری از double submit، accessibility، respects prefers-reduced-motion

## ۹. استقرار Quarkus

- JAR بدون Fat-JAR Keycloak libs
- کپی به `providers/`
- اجرای `kc.sh build` پس از اضافه کردن Provider
- بررسی لاگ‌های کشف Provider

## ۱۰. تست‌های الزامی

- Unit: PhoneNormalizer, OtpGenerator, OtpHmacUtil, SmsAuthConfig
- Provider: fail-closed cases، عدم افشای Secret
- Authenticator: OTP lifecycle، MFA constraints، role restrictions، no session on failure
- Integration: هر سه سناریو روی نسخه هدف Keycloak 26.0

## ۱۱. تحویل

شامل سورس کامل، META-INF/services، pom.xml تطبیق با 26.0، theme templates، docs، scripts، تست‌ها و README.

**نکته اجرایی:** نمونه‌کد نباید عیناً استفاده شه. Custom SPI باید با کلاس SmsSpi و فایل‌های Service Loader صحیح ثبت شه. انتخاب روش ورود صرفاً با دو ALTERNATIVE صحیح نیست.
