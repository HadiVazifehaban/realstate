# Secrets Management

- SHEKARCHI_OTP_HMAC_SECRET: Minimum 32 bytes random. Never commit.
- SMS provider API keys: Configure via Provider Config in Admin Console or secure env. Never log.
- Never store OTP in logs or plaintext.
