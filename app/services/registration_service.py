"""Account provisioning for the OTP funnels.

``quick_register`` redeems a registration token: existing, enabled realm
user  -> rotate the OTP-bridge credential and mark the mobile verified;
absent user -> create a minimal ``ROLE_VERIFIED_USER`` account (no password
from the caller, no requested role honored). Suspended/disabled accounts
are never re-enabled here.

``submit_professional`` validates the per-track payload (cities against the
real tree when reachable, invite code for analysts, agency papers for
managers), persists a ``ProfessionalApplication`` in
``ROLE_REVIEW_PENDING``, and -- when Keycloak is reachable -- ensures the
realm account exists with the *base* role only. The requested specialist
role is stored, never assigned, until ``approve_application`` runs.

``issue_session`` retains a password-grant compatibility bridge only for the
isolated LICENSE topology. KEYCLOAK mode refuses it and uses Auth.js OIDC. In
``otp_test_mode`` it returns a deterministic stub instead (tests only).
"""

from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import AuthMode, Settings
from app.core.identity import KEYCLOAK_ROLE_MAP
from app.core.logging import get_logger
from app.core.mobile import mask_mobile
from app.models.enums import UserRole
from app.models.registration import AuthAuditLog, ProfessionalApplication
from app.services import keycloak_admin
from app.services.keycloak_admin import KeycloakDirectoryError
from app.services.otp_service import consume_registration_token

logger = get_logger("app.registration")

#: Requested realm role -> (application status, Keycloak base tier).
_TRACKS: dict[str, tuple[str, UserRole]] = {
    "ROLE_JUNIOR_BROKER": ("ROLE_REVIEW_PENDING", UserRole.USER),
    "ROLE_SENIOR_BROKER": ("ROLE_REVIEW_PENDING", UserRole.USER),
    "ROLE_AGENCY_MANAGER": ("AGENCY_REVIEW_PENDING", UserRole.USER),
    "ROLE_DATA_ANALYST": ("ROLE_REVIEW_PENDING", UserRole.USER),
}

_FORBIDDEN_ROLES = frozenset({"ROLE_ADMIN", "ROLE_SUPERVISOR"})


class RegistrationError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


async def _audit(
    session: AsyncSession,
    *,
    event: str,
    mobile_e164: str = "",
    keycloak_user_id: str = "",
    outcome: str = "",
    detail: str = "",
    client_ip: str = "",
) -> None:
    session.add(
        AuthAuditLog(
            event=event,
            masked_mobile=mask_mobile(mobile_e164) if mobile_e164 else "",
            keycloak_user_id=keycloak_user_id,
            outcome=outcome,
            detail=detail[:1000],
            client_ip=client_ip[:64],
        )
    )


async def _known_cities() -> set[str] | None:
    """Real active city names, or None when the provider is unreachable."""
    try:
        from app.services import iran_locations

        tree = await iran_locations.fetch_areas_tree()
    except Exception:
        return None
    cities = tree.get("cities") if isinstance(tree, dict) else None
    if not cities:
        return None
    return {str(c) for c in cities}


def _clean_str(value: Any, limit: int = 255) -> str:
    return str(value or "").strip()[:limit]


async def quick_register(
    session: AsyncSession,
    settings: Settings,
    *,
    registration_token: str,
    client_ip: str = "",
) -> dict[str, Any]:
    """Redeem a token: login the existing user or create a minimal account."""
    mobile = await consume_registration_token(settings, registration_token)
    if not mobile:
        await _audit(session, event="quick.register", outcome="bad_token", client_ip=client_ip)
        await session.commit()
        raise RegistrationError(401, "invalid_token", "نشست تأیید منقضی شده است؛ دوباره کد بگیرید.")

    try:
        existing = await keycloak_admin.find_user_by_phone(settings, mobile)
    except KeycloakDirectoryError as exc:
        await _audit(
            session, event="quick.register", mobile_e164=mobile,
            outcome="keycloak_down", detail=exc.code, client_ip=client_ip,
        )
        await session.commit()
        raise RegistrationError(
            exc.status_code, exc.code, "ارتباط با مرکز هویت برقرار نشد؛ بعداً تلاش کنید."
        ) from exc

    if existing is not None:
        if not existing.enabled:
            await _audit(
                session, event="quick.register", mobile_e164=mobile,
                keycloak_user_id=existing.id, outcome="suspended", client_ip=client_ip,
            )
            await session.commit()
            raise RegistrationError(403, "account_suspended", "حساب شما معلق است؛ با پشتیبانی تماس بگیرید.")
        await keycloak_admin.mark_mobile_verified(settings, existing.id, mobile)
        await _audit(
            session, event="quick.register", mobile_e164=mobile,
            keycloak_user_id=existing.id, outcome="login", client_ip=client_ip,
        )
        await session.commit()
        logger.info("quick login for %s", mask_mobile(mobile))
        return {"mobile": mobile, "has_account": True, "keycloak_user_id": existing.id}

    try:
        created = await keycloak_admin.create_mobile_user(
            settings, mobile_e164=mobile, role=UserRole.USER,
            kyc_status=settings.keycloak_required_kyc_status,
            quota=settings.new_user_pii_quota,
        )
    except KeycloakDirectoryError as exc:
        if exc.status_code == 409:
            await _audit(
                session, event="quick.register", mobile_e164=mobile,
                outcome="race_duplicate", client_ip=client_ip,
            )
            await session.commit()
            raise RegistrationError(
                409, "duplicate", "این شماره هم‌اکنون ثبت شده است؛ وارد شوید."
            ) from exc
        await _audit(
            session, event="quick.register", mobile_e164=mobile,
            outcome="keycloak_down", detail=exc.code, client_ip=client_ip,
        )
        await session.commit()
        raise RegistrationError(
            exc.status_code, exc.code, "ارتباط با مرکز هویت برقرار نشد؛ بعداً تلاش کنید."
        ) from exc
    await _audit(
        session, event="quick.register", mobile_e164=mobile,
        keycloak_user_id=created.id, outcome="created", client_ip=client_ip,
    )
    await session.commit()
    logger.info("quick account created for %s", mask_mobile(mobile))
    return {"mobile": mobile, "has_account": False, "keycloak_user_id": created.id}


def _bridge_password() -> str:
    return secrets.token_urlsafe(32)


def _role_or_400(requested: str, allowed: tuple[str, ...]) -> str:
    name = (requested or "").strip().upper()
    if name in _FORBIDDEN_ROLES:
        raise RegistrationError(422, "forbidden_role", "این نقش قابل درخواست نیست.")
    if name not in allowed:
        raise RegistrationError(422, "unknown_role", "نقش درخواستی معتبر نیست.")
    if name not in KEYCLOAK_ROLE_MAP:
        raise RegistrationError(422, "unknown_role", "نقش درخواستی معتبر نیست.")
    return name

async def submit_professional(
    session: AsyncSession,
    settings: Settings,
    *,
    registration_token: str,
    requested_role: str,
    first_name: str,
    last_name: str,
    email: str,
    cities: list[str],
    payload: dict[str, Any],
    client_ip: str = "",
) -> ProfessionalApplication:
    """Validate a specialist request and queue it for review."""
    mobile = await consume_registration_token(settings, registration_token)
    if not mobile:
        raise RegistrationError(401, "invalid_token", "نشست تأیید منقضی شده است؛ دوباره کد بگیرید.")
    role = _role_or_400(requested_role, settings.professional_allowed_role_list)
    track_status, base_tier = _TRACKS[role]

    known = await _known_cities()
    clean_cities = [_clean_str(c, 64) for c in (cities or []) if _clean_str(c, 64)][:10]
    if known is not None and clean_cities:
        unknown = [c for c in clean_cities if c not in known]
        if unknown:
            raise RegistrationError(422, "unknown_city", f"شهر معتبر نیست: {unknown[0]}")

    safe_payload = {k: _clean_str(v, 1000) for k, v in (payload or {}).items() if isinstance(k, str)}
    if role == "ROLE_DATA_ANALYST":
        invite = _clean_str(safe_payload.get("invite_code"), 64)
        expected = (settings.analyst_invite_code or "").strip()
        if not expected or not invite or invite != expected:
            await _audit(
                session, event="professional.submit", mobile_e164=mobile,
                outcome="bad_invite", detail=role, client_ip=client_ip,
            )
            await session.commit()
            raise RegistrationError(422, "bad_invite", "کد دعوت معتبر نیست.")

    keycloak_user_id = ""
    try:
        existing = await keycloak_admin.find_user_by_phone(settings, mobile)
        if existing is None:
            created = await keycloak_admin.create_mobile_user(
                settings, mobile_e164=mobile, role=base_tier,
                first_name=_clean_str(first_name, 128), last_name=_clean_str(last_name, 128),
                email=_clean_str(email, 255),
                kyc_status="PENDING", quota=settings.new_user_pii_quota,
            )
            keycloak_user_id = created.id
        elif not existing.enabled:
            raise RegistrationError(403, "account_suspended", "حساب شما معلق است؛ با پشتیبانی تماس بگیرید.")
        else:
            keycloak_user_id = existing.id
            await keycloak_admin.mark_mobile_verified(settings, existing.id, mobile)
    except RegistrationError:
        raise
    except KeycloakDirectoryError:
        logger.warning("keycloak unreachable at professional submit; queuing for retry")

    statement = (
        select(ProfessionalApplication)
        .where(ProfessionalApplication.mobile == mobile)
        .where(ProfessionalApplication.status.not_in(["ACTIVE", "REJECTED", "SUSPENDED"]))
    )
    prior = (await session.exec(statement)).first()
    if prior is not None:
        prior.requested_role = role
        prior.first_name = _clean_str(first_name, 128)
        prior.last_name = _clean_str(last_name, 128)
        prior.email = _clean_str(email, 255)
        prior.payload = {**prior.payload, **safe_payload, "cities": clean_cities}
        prior.status = track_status
        if keycloak_user_id:
            prior.keycloak_user_id = keycloak_user_id
        session.add(prior)
        await _audit(
            session, event="professional.submit", mobile_e164=mobile,
            keycloak_user_id=prior.keycloak_user_id, outcome="updated",
            detail=role, client_ip=client_ip,
        )
        await session.commit()
        await session.refresh(prior)
        return prior

    row = ProfessionalApplication(
        mobile=mobile,
        keycloak_user_id=keycloak_user_id,
        requested_role=role,
        first_name=_clean_str(first_name, 128),
        last_name=_clean_str(last_name, 128),
        email=_clean_str(email, 255),
        payload={**safe_payload, "cities": clean_cities},
        status=track_status,
    )
    session.add(row)
    await _audit(
        session, event="professional.submit", mobile_e164=mobile,
        keycloak_user_id=keycloak_user_id, outcome="queued",
        detail=role, client_ip=client_ip,
    )
    await session.commit()
    await session.refresh(row)
    logger.info("professional application queued for %s role=%s", mask_mobile(mobile), role)
    return row


async def issue_session(
    session: AsyncSession,
    settings: Settings,
    *,
    registration_token: str,
    client_ip: str = "",
) -> dict[str, Any]:
    """Rotate the bridge credential and exchange it for realm tokens."""
    if settings.auth_mode is AuthMode.KEYCLOAK and not settings.otp_test_mode:
        raise RegistrationError(
            409,
            "oidc_required",
            "ورود باید از طریق صفحه احراز هویت Keycloak انجام شود.",
        )
    if settings.otp_test_mode:
        mobile = await consume_registration_token(settings, registration_token)
        if not mobile:
            raise RegistrationError(401, "invalid_token", "نشست تأیید منقضی شده است؛ دوباره کد بگیرید.")
        await _audit(
            session, event="token.exchange", mobile_e164=mobile,
            outcome="test_stub", client_ip=client_ip,
        )
        await session.commit()
        return {
            "access_token": f"test-access-for-{mobile}",
            "refresh_token": f"test-refresh-for-{mobile}",
            "expires_in": 900,
            "test_mode": True,
        }
    mobile = await consume_registration_token(settings, registration_token)
    if not mobile:
        await _audit(session, event="token.exchange", outcome="bad_token", client_ip=client_ip)
        await session.commit()
        raise RegistrationError(401, "invalid_token", "نشست تأیید منقضی شده است؛ دوباره کد بگیرید.")
    try:
        account = await keycloak_admin.find_user_by_phone(settings, mobile)
    except KeycloakDirectoryError as exc:
        raise RegistrationError(
            exc.status_code, exc.code, "ارتباط با مرکز هویت برقرار نشد؛ بعداً تلاش کنید."
        ) from exc
    if account is None or not account.enabled:
        await _audit(
            session, event="token.exchange", mobile_e164=mobile,
            outcome="no_account", client_ip=client_ip,
        )
        await session.commit()
        raise RegistrationError(404, "no_account", "حسابی یافت نشد؛ ابتدا ثبت‌نام سریع را کامل کنید.")
    bridge = _bridge_password()
    try:
        await keycloak_admin.set_user_password(settings, account.id, bridge)
        tokens = await keycloak_admin.exchange_direct_grant(settings, mobile, bridge)
    except KeycloakDirectoryError as exc:
        await _audit(
            session, event="token.exchange", mobile_e164=mobile,
            keycloak_user_id=account.id, outcome="exchange_failed",
            detail=exc.code, client_ip=client_ip,
        )
        await session.commit()
        raise RegistrationError(
            exc.status_code, exc.code, "صدور نشست ممکن نشد؛ بعداً تلاش کنید."
        ) from exc
    await _audit(
        session, event="token.exchange", mobile_e164=mobile,
        keycloak_user_id=account.id, outcome="issued", client_ip=client_ip,
    )
    await session.commit()
    logger.info("session issued for %s", mask_mobile(mobile))
    return {**tokens, "test_mode": False}


__all__ = [
    "RegistrationError",
    "issue_session",
    "quick_register",
    "submit_professional",
]

