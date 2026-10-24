# Test Report

## Unit Tests
- PhoneNormalizerTest: validates normalization cases

## Security Checks
- No OTP plaintext logging
- Fail-closed on missing provider/config
- HMAC-based OTP storage
- Session-scoped state only

## Theme (Keycloak 26.0) — Deployment & Render Verification (2026-10-17)

Executed via `scripts/deploy.sh` + `scripts/health-check.sh` against the running
`avg_keycloak` container (image `quay.io/keycloak/keycloak:26.0`, realm `maskanchi`,
`loginTheme: shekarchi`).

| # | Check | Result |
|---|-------|--------|
| 1 | SPI JAR present in `/opt/keycloak/providers/keycloak-shekarchi-sms-1.0.0.jar` | PASS |
| 2 | Provider discovery — `kc.sh build` logs `KC-SERVICES0047: shekarchi-sms-authenticator (SmsAuthenticatorFactory)` | PASS |
| 3 | Login page renders custom theme — `lang="fa" dir="rtl"`, `<title>ورود به شکارچی</title>`, `mk-brand`, `kc-form-login` present; **zero** `Failed to find LOGIN theme shekarchi` errors since restart | PASS |
| 4 | `shekarchi.css` served with hashed path — `GET /resources/uyf88/login/shekarchi/css/shekarchi.css` → HTTP 200 (also verified via LAN IP `192.168.31.168:8082`) | PASS |
| 5 | Logo served — `GET /resources/uyf88/login/shekarchi/img/logo.png` → HTTP 200 | PASS |

### Notes
- The hashed `resourcesPath` (`uyf88` in this run) changes on every Keycloak
  restart/theme-cache rebuild; health-check therefore extracts the live path
  from the rendered login HTML instead of hard-coding it.
- `template.ftl` is intentionally **not** inside the SPI JAR: the four
  `login-*.ftl` templates resolve it through the parent `keycloak` theme
  (classpath), confirming the theme parent-chain is intact.
- The `shekarchi-sms-authenticator` is discovered but **not yet bound** to any
  authentication flow in the `maskanchi` realm (checked live DB: no `authentication_execution`
  rows reference it). Flow wiring per `docs/REALM_CONFIG.md`
  (`shekarchi-browser-passwordless`, `shekarchi-browser-mfa`, method-select)
  is a separate realm-admin task — see TROUBLESHOOTING.md.

