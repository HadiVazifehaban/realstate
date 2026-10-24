# Keycloak realm — notes

`realm-export.json` is imported automatically on first boot
(`docker compose up -d keycloak`). Keycloak's parser is **strict**: it rejects
any property it does not know, so this file must contain nothing but valid
`RealmRepresentation` fields. That is why the documentation lives here instead
of in `_comment` keys inside the JSON — that approach makes the container
crash-loop on `Unrecognized field`.

Re-importing is **not** automatic once the realm exists: Keycloak skips the
import for an existing realm. To force a fresh import, drop the volume:

```bash
docker compose down
docker volume rm avg_real_avg_keycloakpgdata   # realm is destroyed with it
docker compose up -d keycloak
```

That deletes every account in the realm.

## Roles

Realm roles must stay in sync with `KEYCLOAK_ROLE_MAP` in
`app/core/identity.py` and `KEYCLOAK_ROLES` in
`frontend/src/hooks/use-auth.ts`. A realm role the backend does not recognise
is silently ignored at login, so renaming one here locks those users out.

| Realm role | Internal `UserRole` | Notes |
| --- | --- | --- |
| `ROLE_ADMIN` | `ADMIN` | full control incl. PII vault |
| `ROLE_SUPERVISOR` | `SUPERVISOR` | owner data + audit trail |
| `ROLE_AGENCY_MANAGER` | `OFFICE_MANAGER` | manages the office team |
| `ROLE_SENIOR_BROKER` | `AGENT` | full desk access |
| `ROLE_JUNIOR_BROKER` | `AGENT` | limited desk access |
| `ROLE_OWNER` | `OWNER` | property owner, self-registration |
| `ROLE_VERIFIED_USER` | `USER` | authenticated |
| `ROLE_UNVERIFIED_USER` | `GUEST` | public showcase |
| `ROLE_DATA_ANALYST` | `GUEST` | authenticated but **vetoed** from PII |

Two realm roles collapse onto `AGENT`, and `ROLE_DATA_ANALYST` is a *veto*
rather than a grant: a token may hold both a broker role and the analyst role,
and the veto must win. When a user holds several roles the highest tier in
`ROLE_ORDER` wins, never "the first one listed".

## Clients

Three clients, three different jobs:

- **`maskanchi-frontend`** — the browser's public client. PKCE `S256`, never a
  secret. Carries the protocol mappers that put `realm_access.roles`,
  `kyc_status`, `tenant_id`, `agency_name`, `daily_pii_quota` and
  `mobile_verified` into the token, plus the audience mapper that adds
  `maskanchi-backend-api` to `aud`.
- **`maskanchi-backend-api`** — exists only so it can be named in `aud`. The
  core rejects a token whose audience does not match, so this client must exist
  for the audience mapper to resolve.
- **`maskanchi-admin-cli`** — the backend's own service account, used only for
  the user-directory Admin REST calls. Client-credentials flow, no interactive
  login.

`maskanchi-admin-cli` holds only `view-users`, `query-users` and `manage-users`
under `realm-management`. `view-users`/`query-users` are enough to list the
directory; `manage-users` additionally backs the dashboard's invite/edit
buttons. Do not add `admin-console` or any role that can read realm keys.

Its secret lives in `.env` as `KEYCLOAK_ADMIN_CLIENT_SECRET` and must match the
`secret` field in the JSON. Change both together.

## Seed accounts

Passwords are the lowercase username and are only here so a fresh clone can log
in. **Rotate or delete them before any shared deployment.**

| Username | Role | KYC |
| --- | --- | --- |
| `admin` | `ROLE_ADMIN` | VERIFIED |
| `manager` | `ROLE_AGENCY_MANAGER` | VERIFIED |
| `supervisor` | `ROLE_SUPERVISOR` | VERIFIED |
| `agent` | `ROLE_SENIOR_BROKER` | VERIFIED |
| `junior` | `ROLE_JUNIOR_BROKER` | VERIFIED |
| `analyst` | `ROLE_DATA_ANALYST` | VERIFIED |
| `pending` | `ROLE_VERIFIED_USER` | PENDING |
| `owner` | `ROLE_OWNER` | VERIFIED |

`pending` exists to exercise the approval gate: a PENDING `kyc_status` cannot
pass `require_approval` regardless of role.

`owner` was added for testing the PERSON/AGENCY split on `POST /api/v1/properties`:
the token carries `ROLE_OWNER`, which `submitter_type_for` maps to
`SubmitterType.PERSON` — the «شخص حقیقی» path.

## Issuer

`KC_HOSTNAME` (`KEYCLOAK_PUBLIC_URL` in `.env`) must be the address the browser
*and* the backend use to reach Keycloak, and it must match `KEYCLOAK_ISSUER`.
Token verification pins the issuer, so a mismatch rejects every token. For LAN
clients set both to the machine's LAN IP, e.g.
`http://192.168.31.168:8082` — `localhost` resolves to the viewer's own machine.