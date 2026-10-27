# SMS-verified Keycloak registration

The Keycloak sign-up page collects first name, last name, a chosen username and
mobile, plus a password and confirmation. It requests an OTP, verifies it, then posts the one-use proof, password and identity
to `POST /api/v1/auth/register`. The server takes the mobile exclusively from
the proof, not from the registration request. No Keycloak account is created by
requesting or verifying an OTP alone.

Usernames are 3–64 ASCII letters, numbers, dot, underscore or hyphen, starting
with a letter or number. Keycloak performs final uniqueness enforcement, including
concurrent username claims. Accounts receive only the base USER tier; phone
verification is not identity/KYC verification. The chosen password (12–128 characters)
is included in the same Keycloak request that creates the account, only after
mobile verification. It is not a temporary password and existing accounts' passwords
are never reset by this endpoint. The frontend keeps it only in component memory,
checks confirmation before requesting OTP, and clears both fields after success.
The server schema uses a redacted secret type and preserves password whitespace.
The frontend returns to the existing OIDC browser login with a username hint;
password and SMS login are both available. Use HTTPS outside local development.

The compact dark form is right-aligned on desktop, with the site logo in the
bottom-left corner. The supplied background has an 80% obsidian overlay. The
layout fits standard desktop/mobile heights, but intentionally allows scrolling
on short viewports and zoomed pages instead of clipping inputs or actions.

## Runtime requirements

- A real SMS adapter must be configured. Fake delivery fails closed unless
  explicit OTP test mode is enabled. Never enable test mode in production.
- Configure `OTP_HMAC_SECRET` (at least 32 bytes), or `OTP_HMAC_SECRET_FILE`,
  from the deployment's secret manager. Redis must be reachable.
- Configure the Keycloak service account with user creation and role assignment
  permissions; user profile configuration must preserve `phone`,
  `mobile_verified`, `phoneNumber`, and `phoneVerified`. The latter two are
  consumed by the browser SMS authenticator.
- Existing Kavenegar or explicitly enabled MelliPayamak adapters require their
  configured API credentials and approved OTP template/body ID.

## Retry and deployment boundaries

Registration consumes the proof even on duplicate or provisioning errors; the
user must request a fresh OTP. A Redis lock serializes this registration endpoint
per mobile for 120 seconds. Keycloak username conflicts return HTTP 409. On a lost
success response, a retry cannot create a second account with the same username;
users can continue through SMS login. Other administrative provisioning paths
must enforce the same phone uniqueness policy: Keycloak itself does not enforce
uniqueness of arbitrary phone attributes.

No live SMS or production deployment is implied by passing unit tests. Verify
real delivery, profile-attribute persistence, and browser SMS login in isolation
before rollout. Keycloak native self-registration should remain disabled so it
cannot bypass this verified creation endpoint.