# Shekarchi Keycloak SMS OTP SPI

Custom Keycloak SMS OTP Authenticator for Shekarchi.

## Features
- Independent SmsSenderService SPI with pluggable providers (Kavenegar, FarazSMS, MelliPayamak)
- Passwordless OTP and Password+MFA flows
- Secure OTP with HMAC and session-scoped state
- Fail-closed security model
- RTL Persian UI templates matching Shekarchi theme

## Build
```bash
mvn clean package -DskipTests
```

## Deploy (Quarkus)
1. Copy target/*.jar to /opt/keycloak/providers/
2. Run /opt/keycloak/bin/kc.sh build
3. Restart Keycloak

## Configuration
- OTP HMAC secret: SHEKARCHI_OTP_HMAC_SECRET env var
- SMS provider config via Keycloak Admin Console
