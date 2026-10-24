# MelliPayamak Pattern Provider

The official MelliPayamak REST sample for `BaseServiceNumber` uses HTTPS
`POST`, `application/x-www-form-urlencoded`, and the fields `username`,
`password`, `text`, `to`, and `bodyId`. It does not require a sender number for
this shared service-number operation. Pattern variables are sent positionally
in registry order and separated by `;`. The endpoint remains configurable.

The response is JSON. MelliPayamak SDKs describe `Value` as a receipt ID or
error value and expose `RetStatus`/`StrRetStatus`; this adapter accepts only
HTTP 2xx, `RetStatus == 1`, and a numeric receipt ID. Panel-specific response
semantics must still be confirmed against the account's current API page before
enabling real delivery. HTTP failures and provider business errors are mapped
to safe generic classifications; response bodies and credentials are never
logged. A bounded response size, TLS-only remote endpoint, connection/request
timeouts, and disabled redirects are enforced. POST requests are not retried:
after an ambiguous timeout, retrying may send a duplicate OTP.

## Java / Keycloak environment

Configure credentials through the deployment secret manager:

- `MELLIPAYAMAK_USERNAME`
- `MELLIPAYAMAK_PASSWORD`
- `MELLIPAYAMAK_ENABLED` (defaults to `false`; must remain false while panel templates are pending approval)
- `MELLIPAYAMAK_ENDPOINT` (configurable; defaults to the official REST sample endpoint)
- `MELLIPAYAMAK_CONNECT_TIMEOUT_MS` (defaults to 5000)
- `MELLIPAYAMAK_TIMEOUT_SECONDS` (FastAPI) / `MELLIPAYAMAK_TIMEOUT_MS` (Java)
- `MELLIPAYAMAK_OTP_BODY_ID`
- `MELLIPAYAMAK_VISIT_BODY_ID`
- `MELLIPAYAMAK_LEAD_BODY_ID`
- `MELLIPAYAMAK_SUBSCRIPTION_BODY_ID`

The Body IDs are account-specific and must be approved in the panel. They are
intentionally not copied into source or environment files.
The FastAPI switch is `MELLIPAYAMAK_ENABLED` and also defaults to false; setting
Body IDs alone must never enable sending. Both adapters use the same
`MELLIPAYAMAK_ENABLED=false` gate. No live SMS should be used to verify
the contract.

## قرارداد API و محدودیت تأیید

نمونه REST رسمی MelliPayamak در مخزن Lua عملیات `BaseServiceNumber` را با
`POST`، بدنه‌ی `application/x-www-form-urlencoded` و فیلدهای بالا نشان می‌دهد.
راهنمای عمومی رسمی نیز ارسال با الگو و پارامترهای مرتب را توضیح می‌دهد. نسخه‌ی
دقیق پاسخ و وضعیت‌های کسب‌وکاری به حساب پنل بستگی دارد؛ هیچ درخواست واقعی برای
تأیید آن اجرا نشده است. تا بررسی مستندات داخل پنل و تأیید الگو/Body ID، ارسال
واقعی باید غیرفعال بماند.

منابع: https://github.com/Melipayamak/melipayamak-Lua/blob/master/RestClientAsync.lua
و https://github.com/Melipayamak/Webservices

Body IDs have no defaults. An empty ID disables that pattern. Never put real
credentials in source control or logs. Local HTTP is accepted only for loopback
mock testing; remote endpoints must use HTTPS and normal certificate validation.

## FastAPI environment

Set `SMS_PROVIDER=melli-payamak`, `SMS_MELLI_USERNAME`, `SMS_MELLI_PASSWORD`,
and optionally `SMS_MELLI_ENDPOINT`, `SMS_MELLI_TIMEOUT_SECONDS`,
`SMS_MELLI_OTP_BODY_ID`, `SMS_MELLI_VISIT_BODY_ID`,
`SMS_MELLI_PRICE_ALERT_BODY_ID`, `SMS_MELLI_AGENCY_SUB_BODY_ID`.
FastAPI owns one pooled `httpx.AsyncClient` during application lifespan and
closes it at shutdown. A configured real provider with missing credentials
fails startup; it never falls back to the fake provider.

The four registry contracts are:

| Pattern | Ordered variables |
|---|---|
| `shekarchi_otp_login` | `code` |
| `shekarchi_visit_booking` | `property_id`, `date`, `time` |
| `shekarchi_price_alert` | `region`, `price` |
| `shekarchi_agency_sub` | `plan_name`, `expire_date` |

No actual Body ID was available during implementation. Consequently no live
pattern can send until its corresponding Body ID is configured. Provider-level
deduplication is not claimed: reliable duplicate prevention requires a durable
business idempotency key/outbox before calling the gateway. The adapter avoids
the common duplicate source by never retrying an ambiguous POST.

For an isolated Keycloak test Realm, select provider ID `melli-payamak` in the
authenticator setting `sms.provider-id`. The fake provider remains guarded by
the existing development/test-only checks.

## Verification

Run Python tests with `python -m pytest tests/test_melli_payamak.py -q`.
Run Java tests from this module with `mvn test`. Tests use mocks/local HTTP only;
they do not send SMS.
