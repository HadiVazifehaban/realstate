# لبهٔ وب AVG — owjfarda.ir + Nginx Proxy Manager

سایت شرکتی (`owjfarda`) و Nginx Proxy Manager (`npm`) در یک Compose
مستقل (`docker-compose.edge.yml`) روی شبکهٔ ایزولهٔ `avg_edge` اجرا می‌شوند،
تا ری‌استارت لایهٔ وب هرگز به دیتابیس/Redis/Keycloak دست نزند.

```sh
docker compose -f docker-compose.edge.yml up -d --build
docker compose -f docker-compose.edge.yml ps
```

- پنل NPM: `http://127.0.0.1:81` (فقط loopback؛ قابل تنظیم با `NPM_ADMIN_BIND`/`NPM_ADMIN_PORT`)
- سلامت سایت از داخل شبکه: `http://owjfarda:8080/healthz` → `ok`
- داده‌های NPM در volumeهای `avg_npm_data` و `avg_npm_letsencrypt` نگهداری می‌شود.
- پورت‌های ۸۰/۴۴۳ میزبان در اختیار NPM است (قابل تنظیم با `NPM_HTTP_PORT`/`NPM_HTTPS_PORT`).

## جدول روتینگ پیشنهادی در NPM (Proxy Hosts)

NPM از داخل کانتینر به سرویس‌های Compose اصلی با `host.docker.internal`
(معادل gateway میزبان) و پورت منتشرشدهٔ همان سرویس می‌رسد — هر سه مسیر
تست شده و پاسخ می‌دهند:

| دامنهٔ پیشنهادی | مقصد در NPM (Forward Hostname/IP + Port) | وضعیت تست |
|---|---|---|
| `owjfarda.ir` + `www.owjfarda.ir` | `owjfarda` : `8080` (نام سرویس داخل شبکهٔ `avg_edge`) | ✅ `200` + `25806` بایت |
| `shekkarchi.ir` / `app.shekkarchi.ir` (فرانت شکارچی) | `host.docker.internal` : `3000` | ✅ `307` (ریدایرکت NextAuth — یعنی فرانت زنده است) |
| `api.shekkarchi.ir` (بک‌اند FastAPI) | `host.docker.internal` : `8080` → مسیر `/api/v1/health` | ✅ `200` |
| `auth.shekkarchi.ir` (Keycloak) | `host.docker.internal` : `8082` | ✅ `302` (ریدایرکت OIDC — یعنی Keycloak زنده است) |
| پنل NPM خودش | `http://127.0.0.1:81` فقط روی میزبان | ✅ `200` |

نکات:
- برای `owjfarda.ir` و `www.owjfarda.ir` یک Proxy Host بسازید، مقصد
  `owjfarda:8080`، و گواهی Let's Encrypt را همان‌جا فعال کنید.
  DNS هر دو دامنه باید به IP عمومی میزبان برسد.
- ⚠️ Keycloak در حال حاضر issuer ثابت
  `http://192.168.31.168:8082/realms/maskanchi` دارد؛ تا وقتی issuer و
  redirect URIها هماهنگ نشده‌اند، آن را پشت دامنهٔ جدید منتقل نکنید —
  فقط فرانت/بک‌اند را روت کنید.
- تایل‌سرور (`8081`) نیازی به دامنهٔ عمومی ندارد؛ همان LAN کافی است.

## اعتبارسنجی سریع

```sh
# از داخل شبکهٔ edge (نام سرویس):
docker exec avg_npm curl -s -o /dev/null -w '%{http_code}\n' http://owjfarda:8080/healthz
# از میزبان از طریق gateway داخل کانتینر NPM:
docker exec avg_npm curl -s -o /dev/null -w '%{http_code}\n' http://host.docker.internal:3000/
docker exec avg_npm curl -s -o /dev/null -w '%{http_code}\n' http://host.docker.internal:8080/api/v1/health
docker exec avg_npm curl -s -o /dev/null -w '%{http_code}\n' http://host.docker.internal:8082/
```

«کیکلاک» در پروژه سرویس جداگانه‌ای نیست؛ همان Keycloak موجود، سرور هویت شکارچی است.
