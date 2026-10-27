"""Keycloak / OIDC identity enforcement for the Maskanchi API.

Separate from :mod:`app.core.security`, which keeps the legacy symmetric-token
and password helpers used by the offline LAN-office flow. This module owns the
production posture: a token the node did not issue, validated against the realm.

Each request is put through three gates, in this order:

1. **Who are you?** Verify the RS256 signature against the realm's JWKS, pinned
   to a single issuer *and* audience. The algorithm is hard-coded rather than
   read from the token header, so a caller cannot re-sign with ``alg: none`` or
   with the public key as an HMAC secret.
2. **Are you allowed?** Map realm roles onto the internal seven-tier ladder. The
   mapping is centralised here so renaming a realm role is a one-line change.
3. **Are you approved?** Enforce the KYC gate as a separate check. No role,
   however privileged, reaches the API while ``kyc_status`` is not VERIFIED.

Handlers receive a typed :class:`Principal` and never touch raw claims.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from dataclasses import dataclass, field
from typing import Any, Iterable

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from app.core.config import AuthMode, Settings, get_settings
from app.models.enums import (
    SaasTier,
    SUBMITTER_TYPE_BY_ROLE,
    SubmitterType,
    UserRole,
)

logger = logging.getLogger("app.core.identity")


class IdentityError(Exception):
    """Authentication or authorization failed.

    Carries an HTTP status so the FastAPI dependency can translate it without
    this module importing web types.
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


# --------------------------------------------------------------------------- #
# Realm roles -> internal ladder
# --------------------------------------------------------------------------- #
#: External role name -> internal role. The single translation point, so
#: renaming a realm role is a one-line change here rather than an outage.
KEYCLOAK_ROLE_MAP: dict[str, UserRole] = {
    "ROLE_ADMIN": UserRole.ADMIN,
    "ROLE_SUPERVISOR": UserRole.SUPERVISOR,
    "ROLE_AGENCY_MANAGER": UserRole.OFFICE_MANAGER,
    "ROLE_SENIOR_BROKER": UserRole.AGENT,
    "ROLE_JUNIOR_BROKER": UserRole.AGENT,
    "ROLE_OWNER": UserRole.OWNER,
    "ROLE_VERIFIED_USER": UserRole.USER,
    "ROLE_UNVERIFIED_USER": UserRole.GUEST,
    # An analyst is authenticated but must never reach the PII vault.
    "ROLE_DATA_ANALYST": UserRole.GUEST,
}

#: Realm roles that explicitly forbid contact data. Kept apart from the ladder
#: because it is a *veto*: a token may hold both a broker role and this, and the
#: veto must win.
PII_DENY_ROLES: frozenset[str] = frozenset({"ROLE_DATA_ANALYST"})

# This is an independent finance permission; it deliberately does not map to the
# broad ADMIN role ladder and is checked against verified Keycloak realm claims.
FINANCIAL_ADMIN_ROLE = "financial_admin"

_TIER_BY_ROLE: dict[str, SaasTier] = {
    "ROLE_JUNIOR_BROKER": SaasTier.FREE,
    "ROLE_SENIOR_BROKER": SaasTier.BASIC,
    "ROLE_AGENCY_MANAGER": SaasTier.PRO,
    "ROLE_ADMIN": SaasTier.ENTERPRISE,
}

#: Higher wins, used to fold a multi-role token into one effective role.
ROLE_ORDER: dict[UserRole, int] = {
    UserRole.GUEST: 0,
    UserRole.USER: 1,
    UserRole.OWNER: 2,
    UserRole.AGENT: 3,
    UserRole.OFFICE_MANAGER: 4,
    UserRole.SUPERVISOR: 5,
    UserRole.ADMIN: 6,
}

_TIER_ORDER: dict[SaasTier, int] = {
    SaasTier.FREE: 0,
    SaasTier.BASIC: 1,
    SaasTier.PRO: 2,
    SaasTier.ENTERPRISE: 3,
}


@dataclass(frozen=True)
class Principal:
    """Who is calling, and what they may do.

    Built once per request and passed to handlers, so authorisation decisions
    are made against a typed object rather than ad-hoc dict lookups.
    """

    subject: str
    username: str = ""
    full_name: str = ""
    realm_roles: frozenset[str] = field(default_factory=frozenset)
    roles: frozenset[UserRole] = field(default_factory=frozenset)
    tenant_id: str | None = None
    active_agency_id: str | None = None
    agency_name: str = ""
    kyc_status: str = "PENDING"
    saas_tier: SaasTier = SaasTier.FREE
    daily_pii_quota: int = 0
    mobile_verified: bool = False
    token_id: str = ""

    @property
    def is_verified(self) -> bool:
        """True once an administrator has approved the identity."""
        return self.kyc_status.upper() == "VERIFIED"

    @property
    def pii_denied(self) -> bool:
        """This token carries an explicit no-contact-data role."""
        return bool(self.realm_roles & PII_DENY_ROLES)

    def has_role(self, *roles: UserRole) -> bool:
        return bool(self.roles & set(roles))

    def describe(self) -> dict[str, Any]:
        """Audit-friendly summary; never includes the raw token."""
        return {
            "subject": self.subject,
            "username": self.username,
            "tenant_id": self.tenant_id,
            "active_agency_id": self.active_agency_id,
            "roles": sorted(self.realm_roles),
            "kyc_status": self.kyc_status,
            "saas_tier": self.saas_tier.value,
        }


@functools.lru_cache(maxsize=4)
def _jwks_client(issuer: str, cache_seconds: int, timeout: int) -> PyJWKClient:
    """Cached JWKS client, keyed by realm so a settings change rebuilds it."""
    return PyJWKClient(
        f"{issuer.rstrip('/')}/protocol/openid-connect/certs",
        cache_keys=True,
        lifespan=cache_seconds,
        timeout=timeout,
    )


async def verify_access_token(
    token: str, settings: Settings | None = None
) -> dict[str, Any]:
    """Verify signature, issuer, audience and expiry; return the claims.

    RS256 is the only accepted algorithm, taken from configuration rather than
    from the token's own header.
    """
    s = settings or get_settings()
    if not s.keycloak_issuer:
        raise IdentityError(
            500,
            "keycloak_not_configured",
            "حالت احراز هویت KEYCLOAK است اما KEYCLOAK_ISSUER تنظیم نشده است.",
        )

    # PyJWKClient does blocking network I/O (urllib). Calling it inline blocks the
    # event loop on every request, and on a cache miss for an unparseable token it
    # raises a urllib/socket error that escaped the handler as a 500. Offloading
    # to a worker thread keeps the loop free and funnels every failure into 401.
    client = _jwks_client(
        s.keycloak_issuer, s.jwks_cache_seconds, s.jwks_request_timeout_seconds
    )
    try:
        signing_key = await asyncio.to_thread(client.get_signing_key_from_jwt, token)
    except IdentityError:
        raise
    except Exception as exc:  # noqa: BLE001 - any lookup failure is a 401
        # Provider exceptions can contain request URLs or attacker supplied JWT
        # fragments. Log only the class, never exception text or token material.
        logger.warning("JWKS lookup failed (%s)", type(exc).__name__)
        raise IdentityError(
            401, "token_signature_unknown", "امضای توکن قابل بررسی نیست."
        ) from exc

    try:
        return await asyncio.to_thread(_decode_verified, token, signing_key.key, s)
    except IdentityError:
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced as a 401
        logger.warning("token verification failed (%s)", type(exc).__name__)
        raise IdentityError(401, "token_invalid", "توکن نامعتبر است.") from exc


def _decode_verified(token: str, key: Any, s: Settings) -> dict[str, Any]:
    """Signature/issuer/audience/expiry and OIDC access-token checks."""
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=s.keycloak_audience,
            issuer=s.keycloak_issuer.rstrip("/"),
            options={"require": ["exp", "iss", "sub"]},
        )
        # Keycloak access tokens carry `typ=Bearer`; ID tokens and other JWTs
        # must never be accepted as API credentials, even if misconfigured with
        # the API audience.
        if claims.get("typ") != "Bearer":
            raise IdentityError(401, "token_type_invalid", "نوع توکن برای این سرویس معتبر نیست.")
        if claims.get("azp") != s.keycloak_authorized_party:
            raise IdentityError(401, "token_client_invalid", "کلاینت صادرکنندهٔ توکن مجاز نیست.")
        return claims
    except jwt.ExpiredSignatureError as exc:
        raise IdentityError(401, "token_expired", "نشست شما منقضی شده است.") from exc
    except jwt.InvalidAudienceError as exc:
        raise IdentityError(
            401, "token_audience_mismatch", "توکن برای این سرویس صادر نشده است."
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise IdentityError(401, "token_invalid", "توکن نامعتبر است.") from exc
    except PyJWTError as exc:
        # PyJWT raises for structural problems that are not token errors, e.g. an
        # HS256 downgrade signed with the realm's public key. That is an attack
        # signal rather than a server fault, so it must surface as a 401; letting
        # it escape would turn a forgery attempt into a 500.
        logger.warning("token rejected before verification (%s)", type(exc).__name__)
        raise IdentityError(401, "token_invalid", "توکن نامعتبر است.") from exc


def _first_claim(value: Any) -> Any:
    """Keycloak user attributes may be emitted as singleton arrays."""
    return value[0] if isinstance(value, (tuple, list)) and value else value


def _user_attribute(claims: dict[str, Any], name: str) -> Any:
    attributes = claims.get("user_attributes") or {}
    return attributes.get(name) if isinstance(attributes, dict) else None


def _claim_bool(value: Any) -> bool:
    value = _first_claim(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    return isinstance(value, str) and value.strip().casefold() in {"true", "1", "yes"}


def principal_from_claims(
    claims: dict[str, Any], settings: Settings | None = None
) -> Principal:
    """Project Keycloak claims onto the internal principal.

    Unknown realm roles are ignored rather than trusted, the tier is derived
    from the *role* rather than from a claim a caller could edit, and the quota
    is capped by node configuration so a token cannot grant itself a budget.
    """
    s = settings or get_settings()
    realm_access = claims.get("realm_access") or {}
    raw_roles = frozenset(str(role) for role in realm_access.get("roles", []))
    # Drop the realm's auto-assigned baseline role so it never reads as a grant.
    raw_roles = frozenset(r for r in raw_roles if not r.startswith("default-roles"))
    mobile_verified = _claim_bool(
        claims.get("mobile_verified", _user_attribute(claims, "mobile_verified"))
    )
    # A stale/misconfigured token must not be rejected as malformed, but its
    # verified-user grant is not trusted until the independent mobile claim is
    # present. Removing the effective role makes all downstream RBAC guards
    # treat this request as unverified while preserving safe audit context.
    if "ROLE_VERIFIED_USER" in raw_roles and not mobile_verified:
        raw_roles = frozenset(role for role in raw_roles if role != "ROLE_VERIFIED_USER")

    mapped = {
        KEYCLOAK_ROLE_MAP[name] for name in raw_roles if name in KEYCLOAK_ROLE_MAP
    }
    # Keep the most privileged role: folding to "the first one listed" would be a
    # silent privilege reduction, and a security hole when the order flips.
    effective = {max(mapped, key=lambda r: ROLE_ORDER[r])} if mapped else set()

    tier = SaasTier.FREE
    for realm_role in raw_roles:
        candidate = _TIER_BY_ROLE.get(realm_role)
        if candidate is not None:
            tier = max(tier, candidate, key=lambda t: _TIER_ORDER[t])

    try:
        quota = int(claims.get("daily_pii_quota", 0))
    except (TypeError, ValueError):
        quota = 0

    return Principal(
        subject=str(claims.get("sub", "")),
        username=str(_first_claim(claims.get("preferred_username")) or ""),
        full_name=str(_first_claim(claims.get("name")) or ""),
        realm_roles=raw_roles,
        roles=frozenset(effective),
        tenant_id=_first_claim(claims.get("tenant_id", _user_attribute(claims, "tenant_id"))),
        agency_name=str(_first_claim(claims.get("agency_name", _user_attribute(claims, "agency_name"))) or ""),
        kyc_status=str(_first_claim(claims.get("kyc_status", _user_attribute(claims, "kyc_status"))) or "PENDING"),
        saas_tier=tier,
        daily_pii_quota=max(0, min(quota, s.pii_quota_hard_cap)),
        mobile_verified=mobile_verified,
        token_id=str(claims.get("jti", "")),
    )


async def principal_from_token(
    token: str, settings: Settings | None = None
) -> Principal:
    """Verify a bearer token and return the caller it identifies."""
    return principal_from_claims(await verify_access_token(token, settings), settings)


def require_approval(
    principal: Principal, settings: Settings | None = None
) -> None:
    """Enforce the KYC gate.

    Deliberately separate from role checking: a realm role must never be enough
    to reach the API while the identity is still pending.
    """
    s = settings or get_settings()
    if principal.kyc_status.upper() != s.keycloak_required_kyc_status.upper():
        raise IdentityError(
            403, "kyc_pending", "حساب کاربری شما در انتظار تأیید واحد ممیزی است."
        )


def require_roles(
    principal: Principal,
    allowed: Iterable[UserRole],
    *,
    message: str = "",
) -> None:
    """Raise unless the principal holds at least one of ``allowed``."""
    if not principal.roles & set(allowed):
        raise IdentityError(
            403,
            "insufficient_role",
            message or "سطح دسترسی کاربری شما برای این عملیات کافی نیست.",
        )


def submitter_type_for(principal: Principal) -> SubmitterType:
    """The class of party this principal is, for first-party submissions.

    Read off the realm roles on the signed token, never off the request body: a
    caller who could name their own submitter class could file an office
    listing under ``PERSON`` and inherit the owner's trust ranking and the
    «مالک مستقیم» badge.

    The *least* privileged submitter role wins, which is the deliberate inverse
    of :data:`ROLE_ORDER`'s higher-wins fold. A token holding both ROLE_OWNER
    and ROLE_SENIOR_BROKER is somebody who both owns property and works a desk;
    folding that to AGENT would silently reclassify their own listing as office
    business. The endpoint still enforces :data:`SUBMITTER_ROLES` separately,
    so a caller with no submitter role never reaches here.

    Raises ``IdentityError`` for a principal whose roles name no submitter
    class, rather than defaulting to AGENCY: a silent default is how an
    unattributed write becomes "office business" in the audit trail.
    """
    matched = principal.roles & set(SUBMITTER_TYPE_BY_ROLE)
    if not matched:
        raise IdentityError(
            403,
            "not_a_submitter",
            "نقش شما اجازهٔ ثبت ملک را ندارد.",
        )
    least = min(matched, key=lambda role: ROLE_ORDER[role])
    return SUBMITTER_TYPE_BY_ROLE[least]


def require_pii_access(principal: Principal) -> None:
    """Vault gate: approved identity, permitted role, no explicit veto."""
    if principal.pii_denied:
        raise IdentityError(
            403, "pii_forbidden", "این نقش مجاز به مشاهدهٔ اطلاعات تماس نیست."
        )
    require_roles(
        principal,
        {
            UserRole.AGENT,
            UserRole.OFFICE_MANAGER,
            UserRole.SUPERVISOR,
            UserRole.ADMIN,
        },
        message="نقش شما اجازهٔ مشاهدهٔ اطلاعات تماس مالک را ندارد.",
    )


def is_keycloak_mode(settings: Settings | None = None) -> bool:
    """True when tokens, not headers, identify the caller."""
    return (settings or get_settings()).auth_mode is AuthMode.KEYCLOAK


#: Subject of the synthetic principal used on an IdP-less office node. Chosen so
#: an audit row written in LICENSE mode is never mistaken for a real account.
BOOTSTRAP_SUBJECT = "node-bootstrap"


def bootstrap_principal() -> Principal:
    """Principal for the offline LAN-office mode.

    ``LICENSE`` mode means there is no IdP to ask, so the node acts on behalf of
    itself: an approved local operator with the top role. The subject is clearly
    synthetic so an audit trail records "the node did this" rather than implying
    a person signed in.

    This must never be reachable in ``KEYCLOAK`` mode — ``get_principal``
    returns before it can.
    """
    return Principal(
        subject=BOOTSTRAP_SUBJECT,
        username="node-operator",
        full_name="اپراتور نود",
        realm_roles=frozenset({"ROLE_ADMIN"}),
        roles=frozenset({UserRole.ADMIN}),
        kyc_status="VERIFIED",
        saas_tier=SaasTier.ENTERPRISE,
    )
