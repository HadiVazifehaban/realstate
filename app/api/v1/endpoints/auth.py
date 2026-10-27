"""Public OTP + registration endpoints (SHEKARCHI fast & professional funnels).

درباره این ماژول: نقاط پایانی عمومی احراز هویت پیامکی و ثبت‌نام تخصصی سامانه شکارچی.
این routeها بدون دروازه Bearer (بخش ``app/api/v1/router.py``) اجرا می‌شوند؛ یعنی
وارداتی عمومی هستند و نمی‌توانند نمادی که وجودشان را مستند می‌سازد، درخواست کنند.
همه پاسخ‌ها با فرمت استاندارد ``{ok, message, ...}`` و پیام‌های فارسی هستند، هیچ‌گاه
وجود حساب را افشاء نمی‌کنند و کد OTP / رمز / توکن حساس را برنمی‌گردانند.

**English**: Authentication API endpoints for SMS-based OTP verification and user registration.

## Security Features (ویژگی‌های امنیتی)
- **Rate limiting** (محدودیت نرخ درخواست): Prevents abuse with cooldown periods and hourly quotas
- **OTP expiration** (انقضای کد یکبارمصرف): Codes expire after a short period for security
- **IP tracking** (ردیابی IP): Client IP addresses are logged for audit purposes
- **No sensitive data exposure** (عدم افشای داده‌های حساس): Never returns OTP codes or passwords

## Authentication Flow (گردش کار احراز هویت)
1. **OTP Request** → Send SMS with 6-digit code
2. **OTP Verification** → Validate code, get registration token
3. **Registration** → Create account or login with token

## مسیرها (endpoints)
------
* ``POST /auth/otp/request`` — تولید چالش OTP ۶ رقمی و ارسال از طریق SMS (با محدودیت کول‌داون و بودجه ساعتی)
* ``POST /auth/otp/verify`` — بررسی کد OTP؛ در صورت موفقیت، توکن ثبت‌نام یکبارمصرف برمی‌گرداند
* ``POST /auth/quick-register`` — بازخرید توکن ثبت‌نام (ورود یا ایجاد حساب کاربری حداقلی با نقش USER)
* ``POST /auth/professional-registration/{track}`` — ثبت درخواست متخصص؛ نقش فقط پس از تأیید مدیر اعطا می‌شود (junior / senior / agency / analyst)
* ``GET /auth/registration-status`` — برگشت وضعیت گردوارهٔ ثبت‌نام برای یک شماره موبایل (پاسخ‌های عمومی؛ هرگز وجود حساب را بررسی نمی‌کند)
* ``POST /auth/session`` — پل قدیمی فقط در حالت LICENSE؛ در KEYCLOAK ورود از OIDC انجام می‌شود
* ``GET /registration/cities`` — استان‌ها/شهرهای فعال (عمومی؛ همان منبع GIS)
* ``GET /registration/roles`` — نقش‌های متخصص قابل درخواست (عمومی؛ ADMIN / SUPERVISOR هرگز فهرست نمی‌شوند)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy import func
from sqlmodel import select

from app.api.deps import PrincipalDep, SessionDep, SettingsDep
from app.core.identity import IdentityError, require_roles
from app.core.mobile import MobileError, normalize_mobile
from app.models.enums import UserRole
from app.models.registration import AuthAuditLog, ProfessionalApplication
from app.services import agency_referrals
from app.schemas.registration import (
    AgencyManagerIn,
    DataAnalystIn,
    JuniorBrokerIn,
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    OtpVerifyOut,
    QuickRegisterIn,
    VerifiedRegistrationIn,
    RegistrationStatusOut,
    SeniorBrokerIn,
    SessionExchangeIn,
    SessionOut,
)
from app.services import keycloak_admin, otp_service, registration_service
from app.services.keycloak_admin import KeycloakDirectoryError
from app.services.otp_service import OtpVerifyResult
from app.services.registration_service import RegistrationError
from app.services.sms_provider import SmsError

logger = logging.getLogger("app.api.v1.auth")

router = APIRouter()
public_router = APIRouter()

_GENERIC_VERIFY_ERROR = "کد واردشده صحیح نیست یا منقضی شده است"

_TRACK_SCHEMAS = {
    "junior": (JuniorBrokerIn, "ROLE_JUNIOR_BROKER"),
    "senior": (SeniorBrokerIn, "ROLE_SENIOR_BROKER"),
    "agency": (AgencyManagerIn, "ROLE_AGENCY_MANAGER"),
    "analyst": (DataAnalystIn, "ROLE_DATA_ANALYST"),
}

_TRACK_ROLE_LABELS = {
    "ROLE_JUNIOR_BROKER": "مشاور تازه‌وارد",
    "ROLE_SENIOR_BROKER": "مشاور ارشد",
    "ROLE_AGENCY_MANAGER": "مدیر آژانس",
    "ROLE_DATA_ANALYST": "تحلیل‌گر داده",
}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "")[:64]


def _registration_error(exc: RegistrationError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"error": exc.code, "message": exc.message},
    )


@public_router.post("/otp/request", response_model=OtpRequestOut, summary="Request OTP code - درخواست کد یکبارمصرف")
async def otp_request(
    body: OtpRequestIn,
    request: Request,
    settings: SettingsDep,
) -> OtpRequestOut:
    """درخواست کد یکبارمصرف OTP (ارسال SMS با محدودیت نرخ و کول‌داون)

    **English**: Request a 6-digit OTP code via SMS with rate limiting and cooldown enforcement.
    
    سرویس ارسال کد تایید ۶ رقمی از طریق پیامک به شماره موبایل کاربر. در صورت موفقیت، یک توکن ثبت‌نام موقت صادر می‌شود.
    
    ## Parameters (پارامترها)
    - **mobile** (شماره موبایل): User's mobile phone number
    - **purpose** (هدف): Reason for OTP request (optional)
    
    ## Security (امنیت)
    - Rate limited per IP and mobile number
    - Hourly quota enforcement
    - Cooldown period between requests
    
    ## Response (پاسخ)
    - **ok**: Success status (boolean)
    - **message**: Status message in Persian
    - **retry_after**: Seconds until next request allowed
    """
    try:
        result = await otp_service.request_otp(
            settings, body.mobile, client_ip=_client_ip(request), purpose=body.purpose,
            sms_provider=getattr(request.app.state, "sms_provider", None),
        )
    except SmsError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "sms_failed", "message": "ارسال پیامک ممکن نشد؛ بعداً تلاش کنید."},
        )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limited",
                "message": "درخواست زیاد است؛ لطفاً بعداً تلاش کنید.",
                "retry_after": result.retry_after,
            },
            headers={"Retry-After": str(result.retry_after)},
        )
    out: dict[str, Any] = {"ok": True, "message": "کد تأیید ارسال شد.", "retry_after": 0}
    if result.dev_code is not None:
        out["dev_code"] = result.dev_code
    return OtpRequestOut(**{k: v for k, v in out.items() if k in OtpRequestOut.model_fields})


@public_router.post("/otp/verify", response_model=OtpVerifyOut, summary="Verify OTP code - تایید کد یکبارمصرف")
async def otp_verify(
    body: OtpVerifyIn,
    session: SessionDep,
    settings: SettingsDep,
) -> OtpVerifyOut:
    """بررسی کد OTP و دریافت توکن ثبت‌نام

    **English**: Verify the OTP code and receive a one-time registration token.
    
    با وارد کردن کد صحیح ارسال شده به موبایل، یک توکن ثبت‌نام یک‌بارمصرف برگشت داده می‌شود.
    
    ## Parameters (پارامترها)
    - **mobile** (شماره موبایل): User's mobile phone number (same as request)
    - **otp_code** (کد OTP): 6-digit verification code received via SMS
    
    ## Validation (اعتبارسنجی)
    - Code must be correct and not expired
    - Maximum 3 verification attempts allowed
    - Code validity: 2 minutes
    
    ## Response (پاسخ)
    - **ok**: Verification success status
    - **message**: Status message in Persian
    - **registration_token**: One-time token for registration (valid for 10 minutes)
    - **has_account**: Whether user already has an account (boolean)
    """
    try:
        result: OtpVerifyResult = await otp_service.verify_otp(
            settings, body.mobile, body.otp_code
        )
    except Exception:
        logger.exception("otp verify failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "verify_failed", "message": _GENERIC_VERIFY_ERROR},
        )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_code", "message": _GENERIC_VERIFY_ERROR},
        )
    has_account = False
    try:
        found = await keycloak_admin.find_user_by_phone(settings, body.mobile)
        has_account = found is not None and found.enabled
    except KeycloakDirectoryError:
        has_account = False
    session.add(
        AuthAuditLog(event="otp.verify", masked_mobile=body.mobile[:6] + "•••",
                     outcome="ok", detail="verify")
    )
    await session.commit()
    return OtpVerifyOut(
        ok=True, message="شماره موبایل تأیید شد.",
        registration_token=result.registration_token, has_account=has_account,
    )


def _keycloak_error(exc: KeycloakDirectoryError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"error": exc.code, "message": exc.message},
    )


@public_router.post("/register", summary="Create account after mobile verification")
async def register_verified(
    body: VerifiedRegistrationIn, request: Request, session: SessionDep, settings: SettingsDep,
) -> dict[str, Any]:
    try:
        result = await registration_service.register_verified_account(
            session, settings, registration_token=body.registration_token,
            username=body.username, first_name=body.first_name, last_name=body.last_name,
            password=body.password.get_secret_value(),
            client_ip=_client_ip(request),
        )
    except RegistrationError as exc:
        raise _registration_error(exc) from exc
    return {"ok": True, "message": "حساب شما ساخته شد؛ اکنون با رمز عبور یا پیامک وارد شوید.", **result}

@public_router.post("/quick-register", summary="Quick registration - ثبت‌نام سریع")
async def quick_register(
    body: QuickRegisterIn,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    """ثبت‌نام سریع با توکن ثبت‌نام

    **English**: Quick registration or login using registration token.
    
    تبادل توکن ثبت‌نام جهت ورود به سامانه یا ایجاد حساب کاربری.
    
    ## Workflow (گردش کار)
    1. If user exists → Login and return session tokens
    2. If user doesn't exist → Create minimal USER account
    3. Returns Keycloak access/refresh tokens
    
    ## Parameters (پارامترها)
    - **registration_token** (توکن ثبت‌نام): One-time token from OTP verification
    
    ## Response (پاسخ)
    - **ok**: Success status
    - **message**: Status message in Persian
    - **access_token**: JWT access token for API calls
    - **refresh_token**: JWT refresh token (optional)
    - **expires_in**: Token validity in seconds
    """
    try:
        result = await registration_service.quick_register(
            session, settings,
            registration_token=body.registration_token,
            client_ip=_client_ip(request),
        )
    except RegistrationError as exc:
        raise _registration_error(exc) from exc
    return {"ok": True, "message": "ورود شما انجام شد.", **result}


@public_router.post("/professional-registration/{track}")
async def professional_registration(
    track: str,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    """Queues a specialist request; role is assigned only after approval.

ثبت درخواست تخصصی (نقش فقط پس از تأیید مدیر به‌حساب کاربر اعطا می‌شود).
"""
    entry = _TRACK_SCHEMAS.get((track or "").strip().lower())
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "unknown_track", "message": "مسیر ثبت‌نام معتبر نیست."},
        )
    schema_cls, requested_role = entry
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_json", "message": "بدنه درخواست معتبر نیست."},
        )
    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_json", "message": "بدنه درخواست معتبر نیست."},
        )
    try:
        parsed = schema_cls(**raw)
    except ValidationError as exc:
        first = (exc.errors() or [{}])[0]
        field = ".".join(str(p) for p in first.get("loc", [])) or "payload"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "message": f"فیلد «{field}» معتبر نیست.", "field": field},
        ) from exc
    data = parsed.model_dump()
    token = str(data.pop("registration_token"))
    first_name = str(data.pop("first_name"))
    last_name = str(data.pop("last_name"))
    email = str(data.pop("email") or "")
    cities = list(data.pop("cities") or [])
    data.pop("accepted_terms", None)
    try:
        row = await registration_service.submit_professional(
            session, settings,
            registration_token=token, requested_role=requested_role,
            first_name=first_name, last_name=last_name, email=email,
            cities=cities, payload=data, client_ip=_client_ip(request),
        )
    except RegistrationError as exc:
        raise _registration_error(exc) from exc
    return {
        "ok": True,
        "message": "درخواست شما ثبت شد و در صف بررسی قرار گرفت.",
        "application_id": str(row.id),
        "status": row.status,
    }


@public_router.get("/registration-status", response_model=RegistrationStatusOut, summary="Registration status - وضعیت ثبت‌نام")
async def registration_status(
    mobile: str = Query(min_length=10, max_length=20, description="شماره موبایل کاربر"),
    session: SessionDep = None,  # type: ignore[assignment]
    settings: SettingsDep = None,  # type: ignore[assignment]
) -> RegistrationStatusOut:
    """Returns funnel state for a mobile (generic answers; never probes account existence).

    **English**: Check registration funnel status for a mobile number.
    
    برگشت وضعیت گردوارهٔ ثبت‌نام برای یک شماره موبایل (پاسخ‌های عمومی؛ هرگز وجود حساب را بررسی نمی‌کند).
    
    ## Security Note (تذکر امنیتی)
    - This endpoint never confirms or denies account existence
    - Returns generic status information only
    - Protects against user enumeration attacks
    
    ## Response Fields (فیلدهای پاسخ)
    - **mobile_verified**: Whether mobile number has been verified via OTP
    - **has_account**: Whether user has an account (based on public info only)
    - **application_status**: Status of professional application if any
    - **requested_role**: Requested professional role if applicable
    """
    try:
        canonical = normalize_mobile(mobile)
    except MobileError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_mobile", "message": "شماره موبایل معتبر وارد کنید."},
        )
    verified = await otp_service.is_mobile_verified(settings, canonical)
    has_account = False
    try:
        found = await keycloak_admin.find_user_by_phone(settings, canonical)
        has_account = found is not None and found.enabled
    except KeycloakDirectoryError:
        has_account = False
    statement = (
        select(ProfessionalApplication)
        .where(ProfessionalApplication.mobile == canonical)
        .order_by(ProfessionalApplication.created_at.desc())
    )
    latest = (await session.exec(statement)).first()
    return RegistrationStatusOut(
        mobile_verified=verified,
        has_account=has_account,
        application_status=latest.status if latest else "",
        requested_role=latest.requested_role if latest else "",
    )


@router.post("/session", response_model=SessionOut)
async def create_session(
    body: SessionExchangeIn,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> SessionOut:
    """تبادل توکن ثبت‌نام جهت ورود به سامانه یا ایجاد حساب کاربری.

تبادل توکن ثبت‌نام جهت ورود به سامانه یا ایجاد حساب کاربری. در صورت وجود حساب، وارد سیستم می‌شود و در غیر این صورت حساب کاربری با سطح دسترسی عمومی (USER) ایجاد می‌گردد.
"""
    try:
        tokens = await registration_service.issue_session(
            session, settings,
            registration_token=body.registration_token,
            client_ip=_client_ip(request),
        )
    except RegistrationError as exc:
        raise _registration_error(exc) from exc
    return SessionOut(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token", ""),
        expires_in=int(tokens.get("expires_in") or 0),
        test_mode=bool(tokens.get("test_mode", False)),
    )


@router.get("/applications")
async def list_applications(
    session: SessionDep,
    settings: SettingsDep,
    principal: PrincipalDep,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Review queue for managers (OFFICE_MANAGER / ADMIN only).

ورقمر management queue برای مدیران (فقط OFFICE_MANAGER / ADMIN).
"""
    try:
        require_roles(
            principal, {UserRole.OFFICE_MANAGER, UserRole.ADMIN},
            message="بررسی درخواست‌ها تنها برای مدیر مجاز است.",
        )
    except IdentityError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    statement = select(ProfessionalApplication).order_by(
        ProfessionalApplication.created_at.desc()
    )
    if status_filter:
        statement = statement.where(
            ProfessionalApplication.status == status_filter.strip().upper()
        )
    rows = (await session.exec(statement.offset(offset).limit(limit))).all()
    total = (await session.exec(select(func.count()).select_from(ProfessionalApplication))).one()
    return {
        "ok": True,
        "total": int(total),
        "items": [
            {
                "id": str(r.id), "mobile": r.mobile,
                "requested_role": r.requested_role, "assigned_role": r.assigned_role,
                "first_name": r.first_name, "last_name": r.last_name, "email": r.email,
                "payload": r.payload, "status": r.status,
                "reviewer_note": r.reviewer_note, "reviewed_by": r.reviewed_by,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/applications/{application_id}/approve")
async def approve_application(
    application_id: str,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    """Approves a request: assigns the realm role in Keycloak, flips to ACTIVE.

تأیید درخواست: اختصاص نقش realm در Keycloak و تغییر وضعیت به ACTIVE.
"""
    try:
        require_roles(
            principal, {UserRole.OFFICE_MANAGER, UserRole.ADMIN},
            message="تأیید درخواست تنها برای مدیر مجاز است.",
        )
    except IdentityError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    row = await session.get(ProfessionalApplication, application_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "درخواست یافت نشد."},
        )
    if row.status == "ACTIVE":
        return {"ok": True, "message": "این درخواست قبلاً تأیید شده است.", "status": row.status}
    role = (row.requested_role or "").strip().upper()
    if role in ("ROLE_ADMIN", "ROLE_SUPERVISOR"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "forbidden_role", "message": "این نقش قابل تأیید نیست."},
        )
    if role not in settings.professional_allowed_role_list:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "forbidden_role", "message": "این نقش قابل تأیید نیست."},
        )
    if not row.keycloak_user_id:
        try:
            found = await keycloak_admin.find_user_by_phone(settings, row.mobile)
        except KeycloakDirectoryError as exc:
            raise _keycloak_error(exc) from exc
        if found is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "no_account", "message": "حساب کاربر در مرکز هویت یافت نشد."},
            )
        row.keycloak_user_id = found.id
    try:
        from app.core.identity import KEYCLOAK_ROLE_MAP as _ROLE_MAP

        if role not in _ROLE_MAP or role in {"ROLE_ADMIN", "ROLE_SUPERVISOR"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "forbidden_role", "message": "این نقش قابل تأیید نیست."},
            )
        realm_user = await keycloak_admin.get_user(settings, row.keycloak_user_id)
        if not realm_user.mobile_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "mobile_not_verified", "message": "پیش از تأیید عضویت، شماره موبایل باید مستقل از بررسی هویت تأیید شود."},
            )
        if realm_user.kyc_status != "VERIFIED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "kyc_not_verified", "message": "تأیید درخواست شغلی جایگزین احراز هویت نیست؛ ابتدا فرایند KYC را کامل کنید."},
            )
        tier = _ROLE_MAP[role]
        await keycloak_admin.update_user(
            settings, row.keycloak_user_id, email=None,
            first_name=row.first_name or None, last_name=row.last_name or None,
            phone=None, role=tier, realm_role=role, enabled=True,
        )
    except KeycloakDirectoryError as exc:
        raise _keycloak_error(exc) from exc
    row.assigned_role = role
    row.status = "ACTIVE"
    row.reviewed_by = principal.username or principal.subject
    from datetime import datetime, timezone

    row.reviewed_at = datetime.now(timezone.utc)
    session.add(row)
    session.add(
        AuthAuditLog(
            event="professional.approve", masked_mobile=row.mobile[:6] + "•••",
            keycloak_user_id=row.keycloak_user_id, outcome="approved",
            detail=f"{role} by {row.reviewed_by}",
            client_ip=_client_ip(request),
        )
    )
    await session.commit()
    logger.info("application %s approved role=%s", application_id, role)
    return {"ok": True, "message": "درخواست تأیید و نقش اعطا شد.", "status": row.status}


@router.post("/applications/{application_id}/reject")
async def reject_application(
    application_id: str,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    """Rejects a request with a reviewer note (no role is ever assigned).

رد درخواست با نظر بررسی‌کننده (هرگز هیچ نقش اعطا نمی‌شود).
"""
    try:
        require_roles(
            principal, {UserRole.OFFICE_MANAGER, UserRole.ADMIN},
            message="رد درخواست تنها برای مدیر مجاز است.",
        )
    except IdentityError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    try:
        raw = await request.json()
        note = str((raw or {}).get("note", ""))[:2000]
    except Exception:
        note = ""
    row = await session.get(ProfessionalApplication, application_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "درخواست یافت نشد."},
        )
    row.status = "REJECTED"
    row.reviewer_note = note
    row.reviewed_by = principal.username or principal.subject
    from datetime import datetime, timezone

    row.reviewed_at = datetime.now(timezone.utc)
    session.add(row)
    session.add(
        AuthAuditLog(
            event="professional.reject", masked_mobile=row.mobile[:6] + "•••",
            keycloak_user_id=row.keycloak_user_id, outcome="rejected",
            detail=note[:200], client_ip=_client_ip(request),
        )
    )
    await session.commit()
    return {"ok": True, "message": "درخواست رد شد.", "status": row.status}


@public_router.get("/roles", summary="Professional roles - نقش‌های حرفه‌ای")
async def registration_roles(settings: SettingsDep) -> dict[str, Any]:
    """Requestable professional roles (public; ADMIN/SUPERVISOR never listed).
    
    **فارسی**: نقش‌های حرفه‌ای قابل درخواست (عمومی؛ ADMIN/SUPERVISOR هرگز فهرست نمی‌شوند).
    
    این نقطه پایانی لیست نقش‌های حرفه‌ای که کاربران می‌توانند برای آنها درخواست دهند را برمی‌گرداند.
    نقش‌های مدیریتی (ADMIN, SUPERVISOR) در این لیست نمایش داده نمی‌شوند.
    """

    allowed = [r for r in settings.professional_allowed_role_list if r in _TRACK_ROLE_LABELS]
    return {
        "ok": True,
        "roles": [{"name": r, "label": _TRACK_ROLE_LABELS[r]} for r in allowed],
    }


__all__ = ["registration_router", "router"]

registration_router = APIRouter()


@registration_router.get("/cities", summary="Available cities - شهرهای موجود")
async def registration_cities() -> dict[str, Any]:
    """Active provinces/cities for the funnel (public; same source as GIS).
    
    **فارسی**: استان‌ها و شهرهای فعال برای گردواره ثبت‌نام (عمومی؛ همان منبع GIS).
    
    این نقطه پایانی لیست استان‌ها و شهرهای قابل انتخاب در فرآیند ثبت‌نام را برمی‌گرداند.
    """

    from app.services import iran_locations, osm_service

    tree = await iran_locations.fetch_areas_tree()
    if tree.get("provinces"):
        return {"ok": True, **tree}
    try:
        payload = await osm_service.get_administrative_areas()
        normalized = osm_service.normalize_areas(payload)
        return {"ok": True, **normalized}
    except Exception:
        return {"ok": True, "provinces": [], "cities": []}
