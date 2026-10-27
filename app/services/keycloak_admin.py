"""Keycloak Admin API client backing the user directory.

Why the directory lives in Keycloak
-----------------------------------
``/dashboard/users`` used to read the local ``agency_user`` table, which meant
the office directory and the identity provider could disagree: a user disabled
in Keycloak still logged in, and a user removed from the realm kept a staff row
and its PII quota. Keycloak is now the single source of truth for *who exists*
and *what tier they hold*.

``agency_user`` is deliberately still there. It is a local projection used for
quota accounting and audit rows (see ``crm._resolve_actor_user``), neither of
which belongs in an external IdP.

Translation rules
-----------------
Realm roles are folded onto the internal ladder through
:data:`app.core.identity.KEYCLOAK_ROLE_MAP`, and a multi-role user resolves to
the *highest* tier in ``ROLE_ORDER`` -- never "whichever role came first",
because that would silently reduce privilege whenever the order changed.

When a role is written back, an existing realm role that already maps to the
requested tier is preserved. That keeps a junior broker junior instead of
promoting them to senior every time someone re-saves their profile.

The service-account token is obtained with the client-credentials flow, so no
user password ever reaches this process. It is cached for a short window and
refreshed transparently on a 401.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.core.identity import KEYCLOAK_ROLE_MAP, ROLE_ORDER
from app.core.logging import get_logger
from app.models.enums import UserRole

logger = get_logger("app.keycloak_admin")

#: Internal tier -> the realm role written when a manager sets that tier.
#: AGENT has two realm roles; ROLE_SENIOR_BROKER is the canonical one and the
#: junior variant is preserved from the user's existing grants when present.
_REALM_ROLE_BY_TIER: dict[UserRole, str] = {
    UserRole.ADMIN: "ROLE_ADMIN",
    UserRole.SUPERVISOR: "ROLE_SUPERVISOR",
    UserRole.OFFICE_MANAGER: "ROLE_AGENCY_MANAGER",
    UserRole.AGENT: "ROLE_SENIOR_BROKER",
    UserRole.OWNER: "ROLE_OWNER",
    UserRole.USER: "ROLE_VERIFIED_USER",
    UserRole.GUEST: "ROLE_UNVERIFIED_USER",
}

#: Alternative realm roles for a tier, tried in order. Used to avoid promoting
#: a junior broker to senior when the requested tier is unchanged.
_TIER_ALTERNATIVES: dict[UserRole, tuple[str, ...]] = {
    UserRole.AGENT: ("ROLE_JUNIOR_BROKER", "ROLE_SENIOR_BROKER"),
}

#: Keycloak's user list omits realm roles unless they are fetched separately,
#: and there is no batch endpoint for them -- one call per user. Office realms
#: are small, but the concurrency is bounded anyway so a large realm cannot
#: open hundreds of sockets at once.
_ROLE_LOOKUP_CONCURRENCY = 8

#: Guard against a runaway realm: the directory never materialises more than
#: this many users in one pass.
_MAX_DIRECTORY_USERS = 500

#: Keycloak's paging is 1-based.
_PAGE_SIZE = 100

#: Attribute used to carry the phone number, since UserRepresentation has no
#: dedicated field for it. Every attribute below must also be declared in the
#: realm's user profile, or Keycloak silently drops it on any Admin REST write.
_PHONE_ATTRIBUTE = "phone"
_KYC_ATTRIBUTE = "kyc_status"
_TENANT_ATTRIBUTE = "tenant_id"
_QUOTA_ATTRIBUTE = "daily_pii_quota"
_MOBILE_VERIFIED_ATTRIBUTE = "mobile_verified"


class KeycloakDirectoryError(RuntimeError):
    """A directory call failed.

    Carries an HTTP status so the router can translate it without this module
    importing FastAPI.
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class DirectoryUser:
    """One realm user, projected onto the shape the directory table wants."""

    id: str
    username: str
    email: str
    first_name: str
    last_name: str
    phone: str
    enabled: bool
    realm_roles: frozenset[str]
    created_at: datetime | None
    updated_at: datetime | None
    kyc_status: str = "PENDING"
    mobile_verified: bool = False

    @property
    def role(self) -> UserRole:
        """Highest tier this user's realm roles grant.

        An unmapped or empty role set lands on ``GUEST``: the least-privileged
        tier, so an unknown realm role can never widen access.
        """
        mapped = {
            KEYCLOAK_ROLE_MAP[name]
            for name in self.realm_roles
            if name in KEYCLOAK_ROLE_MAP
        }
        if not mapped:
            return UserRole.GUEST
        return max(mapped, key=lambda r: ROLE_ORDER[r])


def is_directory_enabled(settings: Settings) -> bool:
    """True when the node has been given a Keycloak service account.

    Blank credentials mean the directory falls back to ``agency_user`` so a
    fresh clone keeps working before Keycloak is ever started.
    """
    return bool(settings.keycloak_admin_client_id and settings.keycloak_admin_client_secret)


def _admin_base(settings: Settings) -> str:
    """Root of the Keycloak server, derived from the configured issuer.

    Deriving rather than configuring the host separately is deliberate: the
    admin API must never end up pointed at a different server than the one whose
    tokens this node verifies.
    """
    issuer = (settings.keycloak_issuer or settings.keycloak_admin_url or "").strip()
    if not issuer:
        raise KeycloakDirectoryError(
            503,
            "keycloak_not_configured",
            "issuerKeycloak تنظیم نشده است؛ KEYCLOAK_ISSUER را در .env وارد کنید.",
        )
    base = issuer.split("/realms/")[0].rstrip("/")
    if not base:
        raise KeycloakDirectoryError(
            503,
            "keycloak_not_configured",
            "issuerKeycloak نامعتبر است.",
        )
    return base


def _admin_root(settings: Settings) -> str:
    return f"{_admin_base(settings)}/admin/realms/{settings.keycloak_realm}"


def _token_url(settings: Settings) -> str:
    return (
        f"{_admin_base(settings)}/realms/{settings.keycloak_realm}"
        "/protocol/openid-connect/token"
    )


# --------------------------------------------------------------------------- #
# Service-account token
# --------------------------------------------------------------------------- #
# Module-level so the cache survives across requests. Guarded by a lock because
# a cold cache under concurrent first requests would otherwise mint one token
# per request.
_token_cache: dict[str, tuple[str, float]] = {}
_token_lock = asyncio.Lock()


async def _access_token(settings: Settings, *, force_refresh: bool = False) -> str:
    import httpx

    url = _token_url(settings)
    async with _token_lock:
        cached = _token_cache.get(url)
        now = time.monotonic()
        if cached and not force_refresh and cached[1] > now:
            return cached[0]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": settings.keycloak_admin_client_id,
                        "client_secret": settings.keycloak_admin_client_secret,
                    },
                )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("keycloak token request failed: %s", exc)
            raise KeycloakDirectoryError(
                503,
                "keycloak_unavailable",
                "دریافت توکن سرویس از Keycloak ناموفق بود.",
            ) from exc

        token = str(payload.get("access_token") or "")
        if not token:
            raise KeycloakDirectoryError(
                503, "keycloak_unavailable", "Keycloak توکنی برنگرداند."
            )

        # Expire slightly early so a token cannot lapse mid-request.
        ttl = max(5, int(payload.get("expires_in") or 0) - 10)
        ttl = min(ttl, max(5, settings.keycloak_admin_token_ttl_seconds))
        _token_cache[url] = (token, time.monotonic() + ttl)
        return token


async def _send(
    settings: Settings,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | list[dict[str, Any]] | None = None,
    params: dict[str, Any] | None = None,
):
    """One Admin REST call, returning the raw response.

    The response is returned rather than its body because several endpoints
    answer 201/204 with an empty payload and put the only useful information in
    a header -- creating a user, for instance, returns the new id in
    ``Location`` and nothing at all in the body.
    """
    import httpx

    root = _admin_root(settings)

    async def _attempt(token: str):
        async with httpx.AsyncClient(timeout=20.0) as client:
            return await client.request(
                method,
                f"{root}{path}",
                headers={"Authorization": f"Bearer {token}"},
                json=json_body,
                params=params,
            )

    token = await _access_token(settings)
    response = await _attempt(token)

    if response.status_code == 401:
        # The cached token was revoked or rotated out from under us.
        token = await _access_token(settings, force_refresh=True)
        response = await _attempt(token)

    if response.status_code == 404:
        raise KeycloakDirectoryError(404, "not_found", "کاربر یافت نشد.")
    if response.status_code in (401, 403):
        logger.error("keycloak admin call denied: %s %s", method, path)
        raise KeycloakDirectoryError(
            503,
            "keycloak_forbidden",
            "دسترسی سرویس به مدیریت کاربران Keycloak کافی نیست.",
        )
    if response.status_code == 409:
        raise KeycloakDirectoryError(409, "duplicate_user", "این کاربر قبلاً ثبت شده است.")
    if response.status_code >= 400:
        detail = response.text[:300]
        logger.error("keycloak admin call failed: %s %s -> %s", method, path, detail)
        raise KeycloakDirectoryError(
            502, "keycloak_error", "ارتباط با Keycloak با خطا مواجه شد."
        )
    return response


async def _api(
    settings: Settings,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | list[dict[str, Any]] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """One Admin REST call, returning the decoded body (or ``None`` if empty)."""
    response = await _send(
        settings, method, path, json_body=json_body, params=params
    )
    if not response.content:
        return None
    return response.json()


def _created_id(response: Any) -> str:
    """Pull a newly created user's id out of the ``Location`` header.

    ``POST /users`` answers 201 with an empty body; the id is only in the
    header. Falling back to the body keeps this working against a proxy that
    rewrites the response.
    """
    location = response.headers.get("location") or ""
    if location:
        tail = location.rstrip("/").rsplit("/", 1)[-1]
        if tail:
            return tail
    try:
        payload = response.json()
    except Exception:
        return ""
    return str((payload or {}).get("id") or "")


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def _first(attribute: Any) -> str:
    """Keycloak attributes are always lists of strings; take the first."""
    if isinstance(attribute, list):
        return str(attribute[0]) if attribute else ""
    return str(attribute or "")


def _epoch_ms(value: Any) -> datetime | None:
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    if millis <= 0:
        return None
    return datetime.fromtimestamp(millis / 1000, tz=timezone.utc)


def _to_directory_user(raw: dict[str, Any], realm_roles: frozenset[str]) -> DirectoryUser:
    attributes = raw.get("attributes") or {}
    email = str(raw.get("email") or "")
    username = str(raw.get("username") or "")
    return DirectoryUser(
        id=str(raw.get("id") or ""),
        # Prefer the email: it is the login the office actually recognises, and
        # Keycloak's own `username` may be an opaque subject id.
        username=email or username,
        email=email,
        first_name=str(raw.get("firstName") or ""),
        last_name=str(raw.get("lastName") or ""),
        phone=_first(attributes.get(_PHONE_ATTRIBUTE)),
        enabled=bool(raw.get("enabled", True)),
        realm_roles=realm_roles,
        created_at=_epoch_ms(raw.get("createdTimestamp")),
        updated_at=_epoch_ms(raw.get("epoch")),
        kyc_status=(_first(attributes.get(_KYC_ATTRIBUTE)) or "PENDING").upper(),
        mobile_verified=(_first(attributes.get(_MOBILE_VERIFIED_ATTRIBUTE)) or "false").lower() == "true",
    )


async def _fetch_raw_users(settings: Settings) -> list[dict[str, Any]]:
    """Every realm user, with attributes and profile fields."""
    collected: list[dict[str, Any]] = []
    first = 0
    while len(collected) < _MAX_DIRECTORY_USERS:
        batch = await _api(
            settings,
            "GET",
            "/users",
            params={
                "first": first,
                "max": _PAGE_SIZE,
                "briefRepresentation": "false",
            },
        )
        if not isinstance(batch, list) or not batch:
            break
        collected.extend(batch)
        if len(batch) < _PAGE_SIZE:
            break
        first += _PAGE_SIZE
    return collected[:_MAX_DIRECTORY_USERS]


async def _roles_for_users(settings: Settings, user_ids: list[str]) -> dict[str, frozenset[str]]:
    """Realm role mappings per user.

    Keycloak returns no realm roles on the user list, and there is no batch
    endpoint, so this is one request per user with bounded concurrency.
    """
    results: dict[str, frozenset[str]] = {}
    semaphore = asyncio.Semaphore(_ROLE_LOOKUP_CONCURRENCY)

    async def _one(user_id: str) -> None:
        async with semaphore:
            try:
                mappings = await _api(
                    settings, "GET", f"/users/{user_id}/role-mappings/realm"
                )
            except KeycloakDirectoryError:
                # One unreadable account must not blank the whole directory.
                logger.warning("could not read realm roles for user %s", user_id)
                results[user_id] = frozenset()
                return
            names = frozenset(
                str(m.get("name"))
                for m in (mappings or [])
                if m.get("name") and not str(m.get("name")).startswith("default-")
            )
            results[user_id] = names

    await asyncio.gather(*(_one(uid) for uid in user_ids))
    return results


async def list_directory_users(settings: Settings) -> list[DirectoryUser]:
    """The whole realm directory, with each user's effective tier resolved.

    Fetching everything and filtering in Python keeps the table's rows and its
    role histogram derived from one snapshot, so the two can never disagree --
    the same invariant the ``agency_user`` implementation held.
    """
    raw_users = await _fetch_raw_users(settings)
    ids = [str(u.get("id")) for u in raw_users if u.get("id")]
    roles_by_id = await _roles_for_users(settings, ids)

    directory = [
        _to_directory_user(raw, roles_by_id.get(str(raw.get("id")), frozenset()))
        for raw in raw_users
    ]
    # Service accounts are not people: they would otherwise appear as a row
    # named after a client.
    directory = [u for u in directory if not u.username.startswith("service-account-")]
    directory.sort(
        key=lambda u: (u.created_at is None, -(u.created_at.timestamp() if u.created_at else 0))
    )
    return directory


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #
def _realm_role_for(tier: UserRole, existing: frozenset[str]) -> str:
    """Pick the realm role that expresses ``tier``.

    Prefers a role the user already holds among the tier's equivalents, so
    re-saving an AGENT does not promote a junior broker to senior.
    """
    alternatives = _TIER_ALTERNATIVES.get(tier)
    if alternatives:
        for candidate in alternatives:
            if candidate in existing:
                return candidate
    return _REALM_ROLE_BY_TIER[tier]


async def _realm_role_representations(
    settings: Settings, role_names: list[str]
) -> list[dict[str, Any]]:
    """Resolve realm role names into the representations Keycloak expects."""
    known = await _known_realm_roles(settings)
    payload: list[dict[str, Any]] = []
    missing: list[str] = []
    for name in role_names:
        representation = known.get(name)
        if representation is None:
            missing.append(name)
        else:
            payload.append(representation)
    if missing:
        raise KeycloakDirectoryError(
            500,
            "unknown_realm_role",
            f"نقش تعریف‌نشده در Keycloak: {', '.join(missing)}",
        )
    return payload


# Realm roles are effectively static, so they are cached per server URL rather
# than re-read on every write. Keyed by the admin root so two realms (or two
# servers) never share an entry.
_realm_role_cache: dict[str, dict[str, dict[str, Any]]] = {}
_realm_role_lock = asyncio.Lock()


async def _known_realm_roles(settings: Settings) -> dict[str, dict[str, Any]]:
    root = _admin_root(settings)
    async with _realm_role_lock:
        cached = _realm_role_cache.get(root)
        if cached is not None:
            return cached
        roles = await _api(settings, "GET", "/roles")
        table = {str(r["name"]): r for r in (roles or []) if r.get("name")}
        _realm_role_cache[root] = table
        return table


async def invalidate_realm_roles(settings: Settings) -> None:
    """Drop the cached role table, e.g. after the realm is re-imported."""
    _realm_role_cache.pop(_admin_root(settings), None)


async def _set_realm_roles(settings: Settings, user_id: str, role_names: list[str]) -> None:
    """Make the user's realm role mappings exactly ``role_names``.

    Keycloak exposes add and delete but no "set", so this computes the
    difference against what is actually assigned:

    * deleting only the roles about to be added would be a no-op for the case
      that matters -- a demotion would leave the old role in place and the user
      would keep the privileges they were just moved off;
    * deleting the *current* set and re-adding would briefly strip every role,
      which matters if two managers save at once.

    So: remove what is not wanted, add what is missing. The realm's
    auto-assigned baseline (``default-roles-*``) is never touched.
    """
    wanted = await _realm_role_representations(settings, role_names)
    wanted_ids = {r["id"] for r in wanted}

    current = await _api(settings, "GET", f"/users/{user_id}/role-mappings/realm")
    assigned = [
        r
        for r in (current or [])
        if r.get("id") and not str(r.get("name", "")).startswith("default-")
    ]

    to_remove = [r for r in assigned if r["id"] not in wanted_ids]
    to_add = [r for r in wanted if r["id"] not in {a["id"] for a in assigned}]

    if to_remove:
        await _send(
            settings,
            "DELETE",
            f"/users/{user_id}/role-mappings/realm",
            json_body=to_remove,
        )
    if to_add:
        await _send(
            settings,
            "POST",
            f"/users/{user_id}/role-mappings/realm",
            json_body=to_add,
        )


async def create_user(
    settings: Settings,
    *,
    email: str,
    first_name: str,
    last_name: str,
    phone: str,
    role: UserRole,
    realm_role: str | None = None,
    enabled: bool,
) -> DirectoryUser:
    """Create a realm user with the requested tier.

    The account is created without a password: the dashboard never sets
    credentials, so first login must go through Keycloak's own reset flow.

    An office invitation grants an office role only. It does not prove identity
    or mobile ownership; both claims start false/pending and are verified through
    their separate workflows.
    """
    if realm_role is not None and (
        role is not UserRole.AGENT
        or realm_role not in {"ROLE_JUNIOR_BROKER", "ROLE_SENIOR_BROKER"}
    ):
        raise ValueError("Office invitations may assign only a Junior or Senior Broker Realm role.")
    attributes: dict[str, list[str]] = {
        _KYC_ATTRIBUTE: ["PENDING"],
        _MOBILE_VERIFIED_ATTRIBUTE: ["false"],
        # 0 means "no owner-contact reveals"; the tier ceiling in the token
        # still applies, so this cannot widen anyone's budget.
        _QUOTA_ATTRIBUTE: ["0"],
    }
    if phone:
        attributes[_PHONE_ATTRIBUTE] = [phone]

    payload: dict[str, Any] = {
        "username": email,
        "email": email,
        "firstName": first_name,
        "lastName": last_name,
        "enabled": enabled,
        "emailVerified": False,
        "attributes": attributes,
    }

    created = await _send(settings, "POST", "/users", json_body=payload)
    user_id = _created_id(created)
    if not user_id:
        raise KeycloakDirectoryError(502, "keycloak_error", "Keycloak شناسه کاربر برنگرداند.")

    try:
        await _set_realm_roles(settings, user_id, [realm_role or _realm_role_for(role, frozenset())])
    except Exception:
        # The account already exists in the realm, so leaving it behind would
        # strand a half-provisioned user with the default role -- able to log in
        # but holding none of the tier the manager asked for. Roll back.
        logger.error(
            "role assignment failed for new user %s; deleting the partial account", user_id
        )
        try:
            await _api(settings, "DELETE", f"/users/{user_id}")
        except Exception:
            logger.error("could not roll back partial user %s", user_id)
        raise

    logger.info("keycloak user created: %s tier=%s", email, role.value)
    return await get_user(settings, user_id)


async def get_user(settings: Settings, user_id: str) -> DirectoryUser:
    raw = await _api(settings, "GET", f"/users/{user_id}")
    if not isinstance(raw, dict) or not raw.get("id"):
        raise KeycloakDirectoryError(404, "not_found", "کاربر یافت نشد.")
    roles = await _roles_for_users(settings, [user_id])
    return _to_directory_user(raw, roles.get(user_id, frozenset()))


async def _merged_put(settings: Settings, user_id: str, changes: dict[str, Any]) -> None:
    """PUT a user with ``changes`` applied to the *full* stored representation.

    ``PUT /users/{id}`` is a whole-representation replace in Keycloak, not a
    patch: any field left out of the body is written back as null. Sending just
    ``{"attributes": {...}}`` therefore silently erases the user's name, email
    and enabled state. Every write goes through here so that cannot happen.
    """
    raw = await _api(settings, "GET", f"/users/{user_id}")
    if not isinstance(raw, dict):
        raise KeycloakDirectoryError(404, "not_found", "کاربر یافت نشد.")
    merged = {**raw, **changes}
    await _api(settings, "PUT", f"/users/{user_id}", json_body=merged)


async def update_user(
    settings: Settings,
    user_id: str,
    *,
    email: str | None,
    first_name: str | None,
    last_name: str | None,
    phone: str | None,
    role: UserRole | None,
    realm_role: str | None = None,
    enabled: bool | None,
) -> DirectoryUser:
    """Patch profile fields, tier and enabled state.

    Only the supplied fields are touched, so a caller that omits the tier keeps
    whatever the realm already has.
    """
    if realm_role is not None:
        expected_role = KEYCLOAK_ROLE_MAP.get(realm_role)
        if expected_role is None or expected_role is not role or realm_role in {"ROLE_ADMIN", "ROLE_SUPERVISOR"}:
            raise ValueError("Requested Realm role does not match the internal role or is privileged.")

    current = await get_user(settings, user_id)

    changes: dict[str, Any] = {}
    if email and email != current.email:
        changes["email"] = email
        changes["username"] = email
    if first_name is not None:
        changes["firstName"] = first_name
    if last_name is not None:
        changes["lastName"] = last_name
    if phone is not None:
        raw = await _api(settings, "GET", f"/users/{user_id}")
        existing = dict((raw or {}).get("attributes") or {})
        existing[_PHONE_ATTRIBUTE] = [phone]
        changes["attributes"] = existing
    if enabled is not None:
        changes["enabled"] = enabled

    if changes:
        await _merged_put(settings, user_id, changes)

    if realm_role is not None:
        await _set_realm_roles(settings, user_id, [realm_role])
        await invalidate_user_sessions(settings, user_id)
    elif role is not None:
        # Pass the existing roles so an unchanged AGENT tier keeps its seniority.
        await _set_realm_roles(
            settings, user_id, [_realm_role_for(role, current.realm_roles)]
        )
        await invalidate_user_sessions(settings, user_id)

    return await get_user(settings, user_id)


async def set_enabled(settings: Settings, user_id: str, enabled: bool) -> None:
    """Enable or disable an account.

    Disabling is preferred over deletion: Keycloak keeps the user and their
    history, which is what the audit trail needs.
    """
    await _merged_put(settings, user_id, {"enabled": enabled})
    if not enabled:
        await invalidate_user_sessions(settings, user_id)


async def delete_user(settings: Settings, user_id: str) -> None:
    """Remove a just-created realm user if local membership provisioning fails."""
    await _api(settings, "DELETE", f"/users/{user_id}")


async def invalidate_user_sessions(settings: Settings, user_id: str) -> None:
    """Revoke Keycloak refresh sessions after role/status changes."""
    await _api(settings, "POST", f"/users/{user_id}/logout")


async def set_kyc_status(settings: Settings, user_id: str, value: str) -> DirectoryUser:
    """Change KYC without granting/removing Realm roles or touching phone state."""
    status_value = value.strip().upper()
    if status_value not in {"PENDING", "VERIFIED", "REJECTED"}:
        raise ValueError("KYC status is invalid.")
    raw = await _api(settings, "GET", f"/users/{user_id}")
    if not isinstance(raw, dict) or not raw.get("id"):
        raise KeycloakDirectoryError(404, "not_found", "کاربر یافت نشد.")
    attributes = dict(raw.get("attributes") or {})
    attributes[_KYC_ATTRIBUTE] = [status_value]
    await _merged_put(settings, user_id, {"attributes": attributes})
    await invalidate_user_sessions(settings, user_id)
    return await get_user(settings, user_id)


def to_user_out(user: DirectoryUser) -> dict[str, Any]:
    """Render a directory user in the shape ``UserOut`` expects."""
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "status": "ACTIVE" if user.enabled else "INACTIVE",
        "role": user.role,
        "realm_roles": sorted(user.realm_roles),
        "kyc_status": user.kyc_status,
        "mobile_verified": user.mobile_verified,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


# --------------------------------------------------------------------------- #
# OTP registration support (SHEKARCHI fast + professional funnels)
# --------------------------------------------------------------------------- #
async def find_user_by_phone(settings: Settings, mobile_e164: str) -> DirectoryUser | None:
    """Find a realm user by the ``phone`` attribute (exact match).

    Returns ``None`` when absent -- callers must answer identically either
    way so responses never leak account existence.
    """
    raw_users = await _fetch_raw_users(settings)
    ids = [str(u.get("id")) for u in raw_users if u.get("id")]
    roles_by_id = await _roles_for_users(settings, ids)
    for raw in raw_users:
        attributes = raw.get("attributes") or {}
        if _first(attributes.get(_PHONE_ATTRIBUTE)) == mobile_e164:
            return _to_directory_user(
                raw, roles_by_id.get(str(raw.get("id")), frozenset())
            )
    return None


async def create_mobile_user(
    settings: Settings,
    *,
    mobile_e164: str,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    role: UserRole = UserRole.USER,
    kyc_status: str = "VERIFIED",
    quota: int = 0,
    username: str | None = None,
    password: str | None = None,
) -> DirectoryUser:
    """Create a realm user for a verified mobile number.

    Legacy callers use the E.164 mobile as username; verified registration
    supplies the user's chosen username. ``mobile_verified`` is seeded true
    (the caller holds a freshly consumed OTP proof). Verified registration
    includes the chosen password in the same account-creation request.
    """
    attributes: dict[str, list[str]] = {
        _KYC_ATTRIBUTE: [kyc_status],
        _MOBILE_VERIFIED_ATTRIBUTE: ["true"],
        _QUOTA_ATTRIBUTE: [str(quota)],
        _PHONE_ATTRIBUTE: [mobile_e164],
    }
    payload: dict[str, Any] = {
        "username": username if username is not None else mobile_e164,
        "firstName": first_name,
        "lastName": last_name,
        "enabled": True,
        "emailVerified": False,
        "attributes": attributes,
    }
    if username is not None:
        # These are the attributes consumed by the browser SMS authenticator.
        attributes["phoneNumber"] = [mobile_e164]
        attributes["phoneVerified"] = ["true"]
    if email:
        payload["email"] = email
    if password is not None:
        payload["credentials"] = [{"type": "password", "value": password, "temporary": False}]
    created = await _send(settings, "POST", "/users", json_body=payload)
    user_id = _created_id(created)
    if not user_id:
        raise KeycloakDirectoryError(502, "keycloak_error", "Keycloak شناسه کاربر برنگرداند.")
    try:
        await _set_realm_roles(settings, user_id, [_realm_role_for(role, frozenset())])
    except Exception:
        logger.error("role assignment failed for new user %s; rolling back", user_id)
        try:
            await _api(settings, "DELETE", f"/users/{user_id}")
        except Exception:
            logger.error("could not roll back partial user %s", user_id)
        raise
    logger.info("keycloak mobile user created: role=%s", role.value)
    return await get_user(settings, user_id)


async def username_exists(settings: Settings, username: str) -> bool:
    users = await _api(settings, "GET", "/users", params={"username": username, "exact": "true"})
    return any(str(user.get("username", "")).casefold() == username.casefold()
               for user in (users or []))


async def set_user_password(
    settings: Settings, user_id: str, password: str, *, temporary: bool = False
) -> None:
    """(Re)set a realm password via Admin REST."""
    await _api(
        settings,
        "PUT",
        f"/users/{user_id}/reset-password",
        json_body={"type": "password", "value": password, "temporary": temporary},
    )


async def mark_mobile_verified(settings: Settings, user_id: str, mobile_e164: str) -> None:
    """Stamp ``mobile_verified=true`` + canonical phone on a realm user."""
    raw = await _api(settings, "GET", f"/users/{user_id}")
    if not isinstance(raw, dict):
        raise KeycloakDirectoryError(404, "not_found", "کاربر یافت نشد.")
    existing = dict((raw or {}).get("attributes") or {})
    existing[_PHONE_ATTRIBUTE] = [mobile_e164]
    existing[_MOBILE_VERIFIED_ATTRIBUTE] = ["true"]
    await _merged_put(settings, user_id, {"attributes": existing})
    await invalidate_user_sessions(settings, user_id)


async def exchange_direct_grant(
    settings: Settings, username: str, password: str
) -> dict[str, Any]:
    """Password-grant exchange against the public OTP client (OTP bridge only).

    The password is backend-minted and rotated on every OTP login -- never
    typed or seen by a human. Returns access/refresh tokens + expiry.
    """
    import httpx

    token_url = _token_url(settings)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "password",
                    "client_id": settings.otp_keycloak_client_id,
                    "username": username,
                    "password": password,
                    "scope": "openid profile email",
                },
            )
    except Exception as exc:
        raise KeycloakDirectoryError(
            503, "keycloak_unavailable", "ارتباط با Keycloak برقرار نشد."
        ) from exc
    if response.status_code != 200:
        logger.error("direct grant failed: http=%s", response.status_code)
        raise KeycloakDirectoryError(502, "keycloak_error", "صدور نشست ممکن نشد.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise KeycloakDirectoryError(502, "keycloak_error", "صدور نشست ممکن نشد.") from exc
    if not payload.get("access_token"):
        raise KeycloakDirectoryError(502, "keycloak_error", "صدور نشست ممکن نشد.")
    return {
        "access_token": str(payload["access_token"]),
        "refresh_token": str(payload.get("refresh_token") or ""),
        "expires_in": int(payload.get("expires_in") or 0),
    }


__all__ = [
    "DirectoryUser",
    "KeycloakDirectoryError",
    "create_mobile_user",
    "create_user",
    "exchange_direct_grant",
    "find_user_by_phone",
    "get_user",
    "invalidate_realm_roles",
    "is_directory_enabled",
    "list_directory_users",
    "mark_mobile_verified",
    "set_enabled",
    "set_user_password",
    "to_user_out",
    "update_user",
]
