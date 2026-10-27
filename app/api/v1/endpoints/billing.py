"""Card-to-card subscription checkout and financial review API."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select as sa_select
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    ActiveAgencyDep,
    PrincipalDep,
    SessionDep,
    SettingsDep,
    get_active_agency_membership,
    require_financial_admin,
)
from app.models.agency_network import Agency
from app.models.billing import AgencySubscription, FinancialAuditLog, PaymentAttempt, PaymentOrder, PaymentReceipt, PaymentReview, SubscriptionPlan
from app.services import entitlements
from app.models.enums import PaymentOrderStatus, PaymentReviewDecision
from app.services import billing
from app.services import agency_referrals
from app.services.zibal import ZibalError, ZibalNotConfigured, ZibalPaymentProvider
from app.services import zibal_billing
from app.services import zibal_config

router = APIRouter()
public_router = APIRouter()
financial_router = APIRouter(dependencies=[Depends(require_financial_admin)])


@router.get("/referrals")
async def referral_summary(active: ActiveAgencyDep, session: SessionDep) -> dict:
    """Referral state for the currently authorized office only."""
    _, membership, agency = active
    if membership.role not in {"FOUNDER", "ADMIN"}:
        raise HTTPException(403, detail={"error": "agency_referral_forbidden"})
    try:
        result = await agency_referrals.referral_dashboard_data(session, agency.id)
        await session.commit()
        return result
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc)) from exc


class CreateOrderBody(BaseModel):
    plan_id: str = Field(min_length=1, max_length=32)
    payment_method: Literal["CARD_TO_CARD", "ZIBAL"] = "CARD_TO_CARD"


@router.post("/checkout/preview")
async def preview_checkout(payload: CreateOrderBody, request: Request, session: SessionDep, principal: PrincipalDep) -> dict:
    plan = await billing.get_plan(session, payload.plan_id)
    if plan is None or plan.id == "free":
        raise HTTPException(422, detail="پلن انتخاب‌شده برای خرید معتبر نیست.")
    agency_id = await _resolve_agency_id(session, principal, request)
    previous = (await session.exec(sa_select(PaymentOrder.id).where(
        PaymentOrder.agency_id == agency_id,
        PaymentOrder.plan != "free",
        PaymentOrder.is_test.is_(False),
        PaymentOrder.status == PaymentOrderStatus.APPROVED,
    ).limit(1))).first()
    active_subscription = (await session.exec(sa_select(AgencySubscription.id).where(
        AgencySubscription.agency_id == agency_id,
        AgencySubscription.status == "active",
        AgencySubscription.starts_at <= datetime.now(timezone.utc),
        AgencySubscription.expires_at > datetime.now(timezone.utc),
    ).limit(1))).first()
    renewal_workspace = False
    try:
        workspace = await session.get(Agency, uuid.UUID(agency_id))
        renewal_workspace = workspace is not None and workspace.status.value != "SUSPENDED"
    except ValueError:
        pass
    await agency_referrals.release_expired_reservations(session)
    credits, count = await agency_referrals.preview_credits(session, agency_id=agency_id)
    if previous is None or active_subscription is None or not renewal_workspace:
        credits, count = 0, 0
    discount_percent = min(credits, agency_referrals.REFERRAL_POLICY.invoice_cap_percent)
    discount_amount = plan.price_toman * discount_percent // 100
    await session.commit()
    return {
        "plan": billing.public_plan(plan), "base_amount_toman": plan.price_toman,
        "referral_discount_percent": discount_percent,
        "referral_discount_toman": discount_amount,
        "referral_credit_count": count,
        "amount_toman": plan.price_toman - discount_amount,
    }


class ReviewBody(BaseModel):
    reason: str = Field(default="", max_length=2000)


class ConfirmNotPaidBody(BaseModel):
    confirmed_not_paid: bool
    reason: str = Field(min_length=20, max_length=1000)


class PlanFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=2, max_length=128)
    description: str = Field(default="", max_length=1000)
    price_toman: int = Field(ge=0, le=10**12)
    duration_days: int = Field(ge=0, le=3650)
    listing_quota: int | None = Field(ge=0)
    sms_quota: int = Field(ge=0, le=10**9)
    regions_quota: int = Field(ge=0, le=10**6)
    advisor_quota: int | None = Field(ge=0, le=100_000)
    is_unlimited: bool = False
    features: list[str] = Field(default_factory=list, max_length=32)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=100_000)

    @model_validator(mode="after")
    def unlimited_is_explicit(self):
        if self.is_unlimited and (self.listing_quota is not None or self.advisor_quota is not None):
            raise ValueError("برای سهمیهٔ نامحدود، سقف آگهی و مشاور باید null باشد.")
        if not self.is_unlimited and (self.listing_quota is None or self.advisor_quota is None):
            raise ValueError("سقف null فقط همراه حالت نامحدود مجاز است.")
        if any(not item.strip() or len(item) > 160 for item in self.features):
            raise ValueError("ویژگی پلن خالی یا بیش از حد طولانی است.")
        return self


class PlanCreateBody(PlanFields):
    id: str = Field(min_length=2, max_length=32, pattern=r"^[a-z][a-z0-9_]{1,31}$")

    @model_validator(mode="after")
    def price_matches_plan_kind(self):
        if self.id == "free" and self.price_toman != 0:
            raise ValueError("پلن پایه باید رایگان باشد.")
        if self.id != "free" and self.price_toman <= 0:
            raise ValueError("پلن پولی باید قیمت مثبت داشته باشد.")
        return self


class PlanUpdateBody(PlanFields):
    pass


#: Tenant handles arrive from the realm as free-form text, so they are
#: constrained to an identifier-safe alphabet before they are ever used as a
#: lookup key or written to a table.
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _agency_id(principal: PrincipalDep) -> str:
    """The tenant/agency handle that owns this principal's billing records.

    The handle is kept as opaque text, matching the ``agency_user.agency_id``
    convention in this codebase (a slug such as ``local`` or a UUID string),
    rather than being forced into the ``agency.id`` UUID column.
    """
    value = (principal.tenant_id or "").strip()
    if not value:
        raise HTTPException(
            403,
            detail={"error": "agency_required", "message": "حساب شما به دفتر املاک متصل نیست."},
        )
    if not _TENANT_PATTERN.match(value):
        raise HTTPException(
            403,
            detail={"error": "agency_invalid", "message": "شناسهٔ دفتر املاک معتبر نیست."},
        )
    return value


async def _resolve_agency_id(session: SessionDep, principal: PrincipalDep, request: Request) -> str:
    """Use the active DB membership for UUID workspaces; retain opaque local IDs."""
    requested = request.headers.get("x-workspace-id")
    tenant = (principal.tenant_id or "").strip()
    try:
        tenant_uuid = uuid.UUID(tenant) if tenant else None
    except ValueError:
        tenant_uuid = None
    if requested or tenant_uuid is not None:
        _scoped, _membership, agency = await get_active_agency_membership(session, principal, request)
        return str(agency.id)
    return _agency_id(principal)


def _order_access(order: PaymentOrder, principal: PrincipalDep, agency_id: str) -> None:
    """Allow the uploader, or anyone in the same agency, to see the order."""
    if order.user_id != principal.subject and order.agency_id != agency_id:
        raise HTTPException(404, detail="سفارش پیدا نشد.")


def _request_context(request: Request) -> dict[str, str]:
    client = request.client.host if request.client else ""
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return {
        "request_id": request.headers.get("x-request-id", "")[:128],
        "ip_address": (forwarded or client)[:64],
        "user_agent": request.headers.get("user-agent", "")[:512],
    }


def _receipt_metadata(receipt: PaymentReceipt | None) -> dict | None:
    if receipt is None:
        return None
    return {
        "id": str(receipt.id), "original_filename": receipt.original_filename,
        "content_type": receipt.content_type, "file_size": receipt.file_size,
        "sha256": receipt.sha256, "transfer_tracking_number": receipt.transfer_tracking_number,
        "transfer_datetime": receipt.transfer_datetime.isoformat(), "created_at": receipt.created_at.isoformat(),
    }


async def _order_detail(session: SessionDep, order: PaymentOrder, settings: SettingsDep) -> dict:
    receipt = (await session.exec(sa_select(PaymentReceipt).where(PaymentReceipt.order_id == order.id))).first()
    attempt = (await session.exec(
        sa_select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        .order_by(PaymentAttempt.attempt_number.desc()).limit(1)
    )).first()
    return {
        **billing.payment_order_public(order, settings=settings),
        "receipt": _receipt_metadata(receipt),
        "payment_attempt": zibal_billing.public_attempt(attempt, order) if attempt else None,
    }


@public_router.get("/plans")
async def get_plans(session: SessionDep, settings: SettingsDep) -> dict:
    zibal_settings = await _get_zibal_runtime_settings(session, settings)
    zibal_available = zibal_settings is not None
    plans = await billing.list_plans(session)
    if not plans:
        raise HTTPException(503, detail={"error": "plan_catalog_unavailable", "message": "کاتالوگ پلن‌ها آماده نیست."})
    return {
        "plans": [billing.public_plan(plan) for plan in plans],
        "payment_methods": {
            "CARD_TO_CARD": bool(settings.payment_encryption_key.strip()),
            "ZIBAL": zibal_available,
            "ZIBAL_TEST_MODE": bool(zibal_settings and zibal_settings.zibal_test_mode),
        },
    }


async def _get_zibal_runtime_settings(session: SessionDep, settings: SettingsDep):
    try:
        runtime = await zibal_config.load_zibal_settings(session, settings)
        ZibalPaymentProvider(runtime).ensure_ready()
        return runtime
    except ZibalNotConfigured:
        return None


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_payment_order(
    payload: CreateOrderBody, request: Request, session: SessionDep, principal: PrincipalDep, settings: SettingsDep,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=128),
) -> dict:
    runtime_settings = settings
    if payload.payment_method == "ZIBAL":
        runtime_settings = await _get_zibal_runtime_settings(session, settings)
        if runtime_settings is None:
            raise HTTPException(503, detail={"error": "zibal_not_configured", "message": "پرداخت آنلاین موقتاً در دسترس نیست."})
    try:
        agency_id = await _resolve_agency_id(session, principal, request)
        order, plan = await billing.create_order(
            session, agency_id=agency_id, user_id=principal.subject,
            plan_id=payload.plan_id, settings=runtime_settings, payment_method=payload.payment_method,
            idempotency_key=idempotency_key,
        )
        attempt = None
        if payload.payment_method == "ZIBAL":
            order, attempt = await zibal_billing.start_zibal_checkout(
                session, order_id=order.id, provider=ZibalPaymentProvider(runtime_settings), settings=runtime_settings,
                **_request_context(request),
            )
    except ZibalNotConfigured as exc:
        raise HTTPException(503, detail={"error": exc.code, "message": "پرداخت آنلاین موقتاً در دسترس نیست."}) from exc
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail={"error": "payment_not_configured", "message": "تنظیم امن پرداخت انجام نشده است."}) from exc
    return {
        **billing.payment_order_public(order, settings=settings),
        "plan_detail": billing.public_plan(plan),
        "payment_attempt": zibal_billing.public_attempt(attempt, order) if attempt else None,
    }


@router.post("/orders/{order_id}/checkout")
async def start_order_checkout(
    order_id: uuid.UUID, request: Request, session: SessionDep, principal: PrincipalDep,
    settings: SettingsDep,
) -> dict:
    order = await billing.order_by_id(session, order_id)
    if order is None:
        raise HTTPException(404, detail="سفارش پیدا نشد.")
    agency_id = await _resolve_agency_id(session, principal, request)
    _order_access(order, principal, agency_id)
    runtime_settings = await _get_zibal_runtime_settings(session, settings)
    if runtime_settings is None:
        raise HTTPException(503, detail={"error": "zibal_not_configured", "message": "پرداخت آنلاین موقتاً در دسترس نیست."})
    try:
        order, attempt = await zibal_billing.start_zibal_checkout(
            session, order_id=order_id, provider=ZibalPaymentProvider(runtime_settings), settings=runtime_settings,
            **_request_context(request),
        )
    except ZibalNotConfigured as exc:
        raise HTTPException(503, detail={"error": exc.code, "message": "پرداخت آنلاین موقتاً در دسترس نیست."}) from exc
    except LookupError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    return {"order": billing.payment_order_public(order, settings=settings),
            "payment_attempt": zibal_billing.public_attempt(attempt, order)}


@router.get("/orders/{order_id}/payment-attempt")
async def get_order_payment_attempt(
    order_id: uuid.UUID, request: Request, session: SessionDep, principal: PrincipalDep,
) -> dict:
    order = await billing.order_by_id(session, order_id)
    if order is None:
        raise HTTPException(404, detail="سفارش پیدا نشد.")
    agency_id = await _resolve_agency_id(session, principal, request)
    _order_access(order, principal, agency_id)
    attempt = (await session.exec(
        sa_select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        .order_by(PaymentAttempt.attempt_number.desc()).limit(1)
    )).first()
    if attempt is None:
        raise HTTPException(404, detail="تلاش پرداختی برای این سفارش ثبت نشده است.")
    return zibal_billing.public_attempt(attempt, order)


@public_router.get("/zibal/callback")
async def zibal_callback(
    request: Request, session: SessionDep, settings: SettingsDep,
    track_id: str = Query(alias="trackId", min_length=1, max_length=64),
) -> RedirectResponse:
    """Browser return is only a notification; the server verifies with Zibal."""
    try:
        runtime_settings = await zibal_config.load_zibal_settings(session, settings)
        order, _, result = await zibal_billing.verify_zibal_callback(
            session, track_id=track_id, provider=ZibalPaymentProvider(runtime_settings),
            **_request_context(request),
        )
    except LookupError as exc:
        raise HTTPException(404, detail="تراکنش قابل شناسایی نیست.") from exc
    except ZibalError as exc:
        raise HTTPException(503, detail={"error": exc.code, "message": "نتیجهٔ پرداخت هنوز قابل تأیید نیست."}) from exc
    except ValueError as exc:
        raise HTTPException(409, detail="وضعیت سفارش با نتیجهٔ درگاه سازگار نیست.") from exc

    result_url = runtime_settings.zibal_result_url
    parsed = urlsplit(result_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
        raise HTTPException(503, detail="نشانی بازگشت پرداخت پیکربندی نشده است.")
    separator = "&" if parsed.query else "?"
    location = f"{result_url}{separator}{urlencode({'order_id': str(order.id), 'payment_result': result})}"
    return RedirectResponse(location, status_code=303, headers={"Cache-Control": "no-store"})


@router.get("/orders")
async def list_payment_orders(
    request: Request, session: SessionDep, principal: PrincipalDep, settings: SettingsDep,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status_filter: PaymentOrderStatus | None = Query(default=None, alias="status"),
) -> dict:
    agency_id = await _resolve_agency_id(session, principal, request)
    query = sa_select(PaymentOrder).where(
        PaymentOrder.agency_id == agency_id,
        PaymentOrder.user_id == principal.subject,
    )
    if status_filter:
        query = query.where(PaymentOrder.status == status_filter)
    query = query.order_by(PaymentOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await session.exec(query)).all()
    return {"items": [await _order_detail(session, row, settings) for row in rows], "page": page, "page_size": page_size}


@router.get("/orders/{order_id}")
async def get_payment_order(order_id: uuid.UUID, request: Request, session: SessionDep, principal: PrincipalDep, settings: SettingsDep) -> dict:
    order = await billing.order_by_id(session, order_id)
    if not order:
        raise HTTPException(404, detail="سفارش پیدا نشد.")
    agency_id = await _resolve_agency_id(session, principal, request)
    _order_access(order, principal, agency_id)
    return await _order_detail(session, order, settings)


@router.post("/orders/{order_id}/receipt", status_code=status.HTTP_202_ACCEPTED)
async def submit_receipt(
    order_id: uuid.UUID, request: Request, session: SessionDep, principal: PrincipalDep,
    settings: SettingsDep, file: UploadFile = File(...), transfer_tracking_number: str = Form(...),
    transfer_datetime: datetime = Form(...),
) -> dict:
    order = await billing.order_by_id(session, order_id, lock=True)
    if not order:
        raise HTTPException(404, detail="سفارش پیدا نشد.")
    agency_id = await _resolve_agency_id(session, principal, request)
    _order_access(order, principal, agency_id)
    if order.status is not PaymentOrderStatus.AWAITING_TRANSFER:
        raise HTTPException(409, detail="این سفارش در وضعیت دریافت رسید نیست.")
    if order.expires_at <= datetime.now(timezone.utc):
        order.status = PaymentOrderStatus.EXPIRED
        await session.commit()
        raise HTTPException(409, detail="مهلت سفارش پایان یافته است.")
    tracking = re.sub(r"\s+", "", transfer_tracking_number)
    if not 4 <= len(tracking) <= 128:
        raise HTTPException(422, detail="شماره پیگیری معتبر نیست.")
    if transfer_datetime.tzinfo is None:
        transfer_datetime = transfer_datetime.replace(tzinfo=timezone.utc)
    if transfer_datetime > datetime.now(timezone.utc) or transfer_datetime < order.created_at - timedelta(days=1):
        raise HTTPException(422, detail="زمان انتقال خارج از بازهٔ معتبر است.")
    data = await file.read(settings.payment_receipt_max_bytes + 1)
    await file.close()
    if len(data) > settings.payment_receipt_max_bytes:
        raise HTTPException(413, detail="حجم رسید بیش از حد مجاز است.")
    try:
        storage_key, content_type, digest = await billing.store_receipt(data, settings=settings)
    except ValueError as exc:
        raise HTTPException(415, detail=str(exc)) from exc
    receipt = PaymentReceipt(
        order_id=order.id, storage_key=storage_key,
        original_filename=Path(file.filename or "receipt").name[:255],
        content_type=content_type, file_size=len(data), sha256=digest,
        transfer_tracking_number=tracking, transfer_datetime=transfer_datetime,
        uploader_user_id=principal.subject,
    )
    previous = order.status
    order.status = PaymentOrderStatus.RECEIPT_SUBMITTED
    order.submitted_at = datetime.now(timezone.utc)
    order.version += 1
    session.add(receipt)
    session.add(billing.audit_entry(
        actor=principal.subject, actor_role="user", action="receipt_submitted", entity_id=order.id,
        before={"status": previous.value}, after={"status": order.status.value, "receipt_sha256": digest},
        **_request_context(request),
    ))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        billing.receipt_path(storage_key, settings).unlink(missing_ok=True)
        raise HTTPException(409, detail="رسید یا شماره پیگیری تکراری است.") from exc
    return {"order_id": str(order.id), "status": order.status.value, "message": "رسید برای بررسی مدیر مالی ثبت شد؛ ثبت رسید به‌معنای تأیید پرداخت یا فعال‌شدن اشتراک نیست."}


@router.get("/subscriptions/current")
async def current_subscription(request: Request, session: SessionDep, principal: PrincipalDep) -> dict:
    agency_id = await _resolve_agency_id(session, principal, request)
    now = datetime.now(timezone.utc)
    query = sa_select(AgencySubscription).where(
        AgencySubscription.agency_id == agency_id,
        AgencySubscription.status == "active",
        AgencySubscription.starts_at <= now,
        AgencySubscription.expires_at > now,
    ).order_by(AgencySubscription.starts_at.desc(), AgencySubscription.expires_at.desc())
    sub = (await session.exec(query)).first()
    agency_uuid = None
    try:
        agency_uuid = uuid.UUID(agency_id)
    except (TypeError, ValueError):
        pass
    actor = await entitlements.resolve_local_actor_id(
        session, username=principal.username or principal.subject
    )
    quota = await entitlements.get_listing_quota(
        session,
        agency_key=agency_id if agency_uuid or agency_id == "local" else None,
        agency_uuid=agency_uuid,
        actor_user_id=actor,
        now=now,
    )
    usage = {"listings": quota.used}
    quota_data = {
        "listings": {
            "used": quota.used,
            "limit": quota.limit,
            "unlimited": quota.unlimited,
            "remaining": quota.remaining,
        }
    }
    plan = await billing.get_plan(session, sub.plan, include_inactive=True) if sub else None
    if plan is None:
        plan = await billing.get_plan(session, "free", include_inactive=True)
    if plan is None:
        raise HTTPException(503, detail={"error": "plan_catalog_unavailable", "message": "پلن پایه در کاتالوگ موجود نیست."})
    if sub is None:
        return {"plan": plan.id, "title": plan.title, "status": "active", "starts_at": None, "expires_at": None,
                "listing_quota": plan.listing_quota, "sms_quota": plan.sms_quota,
                "regions_quota": plan.regions_quota, "advisor_quota": plan.advisor_quota,
                "is_unlimited": plan.is_unlimited, "usage": usage, "quota": quota_data}
    return {"plan": sub.plan, "title": plan.title, "status": sub.status,
            "starts_at": sub.starts_at.isoformat(), "expires_at": sub.expires_at.isoformat(),
            "listing_quota": sub.listing_quota, "sms_quota": sub.sms_quota,
            "regions_quota": sub.regions_quota, "advisor_quota": sub.advisor_quota,
            "is_unlimited": sub.is_unlimited, "usage": usage, "quota": quota_data}


@router.get("/quota/me")
async def current_quota(request: Request, session: SessionDep, principal: PrincipalDep) -> dict:
    agency_id = await _resolve_agency_id(session, principal, request)
    agency_uuid = None
    try:
        agency_uuid = uuid.UUID(agency_id)
    except (TypeError, ValueError):
        pass
    actor = await entitlements.resolve_local_actor_id(
        session, username=principal.username or principal.subject
    )
    quota = await entitlements.get_listing_quota(
        session,
        agency_key=agency_id if agency_uuid or agency_id == "local" else None,
        agency_uuid=agency_uuid,
        actor_user_id=actor,
    )
    return {
        "plan": quota.plan,
        "period_starts_at": quota.period_starts_at.isoformat(),
        "expires_at": quota.expires_at.isoformat() if quota.expires_at else None,
        "quotas": {"listings": {
            "used": quota.used, "limit": quota.limit,
            "unlimited": quota.unlimited, "remaining": quota.remaining,
        }},
    }


@financial_router.get("/payment-orders")
async def financial_queue(
    session: SessionDep, settings: SettingsDep,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status_filter: PaymentOrderStatus | None = Query(default=None, alias="status"),
    is_test: bool | None = None, q: str | None = Query(default=None, max_length=64),
) -> dict:
    query = sa_select(PaymentOrder)
    if status_filter:
        query = query.where(PaymentOrder.status == status_filter)
    if is_test is not None:
        query = query.where(PaymentOrder.is_test == is_test)
    if q:
        query = query.where(PaymentOrder.order_number.ilike(f"%{q}%"))
    rows = (await session.exec(query.order_by(PaymentOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    return {"items": [await _order_detail(session, row, settings) for row in rows], "page": page, "page_size": page_size}


@financial_router.get("/payment-orders/{order_id}")
async def financial_detail(order_id: uuid.UUID, session: SessionDep, settings: SettingsDep) -> dict:
    order = await billing.order_by_id(session, order_id)
    if not order:
        raise HTTPException(404, detail="سفارش پیدا نشد.")
    result = await _order_detail(session, order, settings)
    reviews = (await session.exec(sa_select(PaymentReview).where(PaymentReview.order_id == order.id).order_by(PaymentReview.created_at))).all()
    result["reviews"] = [{"reviewer_user_id": r.reviewer_user_id, "decision": r.decision.value,
                          "reason": r.reason, "previous_status": r.previous_status.value,
                          "new_status": r.new_status.value, "is_test_review": r.is_test_review,
                          "created_at": r.created_at.isoformat()} for r in reviews]
    return result


@financial_router.get("/payment-orders/{order_id}/receipt")
async def financial_receipt(order_id: uuid.UUID, session: SessionDep, settings: SettingsDep) -> FileResponse:
    order = await billing.order_by_id(session, order_id)
    if not order:
        raise HTTPException(404, detail="سفارش پیدا نشد.")
    receipt = (await session.exec(sa_select(PaymentReceipt).where(PaymentReceipt.order_id == order.id))).first()
    if not receipt:
        raise HTTPException(404, detail="رسیدی برای این سفارش ثبت نشده است.")
    try:
        path = billing.receipt_path(receipt.storage_key, settings)
    except ValueError as exc:
        raise HTTPException(404, detail="رسید پیدا نشد.") from exc
    if not path.is_file():
        raise HTTPException(404, detail="فایل رسید در دسترس نیست.")
    return FileResponse(path, media_type=receipt.content_type, filename=receipt.original_filename,
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@financial_router.post("/payment-orders/{order_id}/start-review")
async def start_review(order_id: uuid.UUID, request: Request, session: SessionDep, principal: PrincipalDep) -> dict:
    order = await billing.order_by_id(session, order_id, lock=True)
    if not order:
        raise HTTPException(404, detail="سفارش پیدا نشد.")
    if order.status is not PaymentOrderStatus.RECEIPT_SUBMITTED:
        raise HTTPException(409, detail="این سفارش آمادهٔ شروع بررسی نیست.")
    previous = order.status
    order.status = PaymentOrderStatus.UNDER_REVIEW
    order.version += 1
    session.add(PaymentReview(order_id=order.id, reviewer_user_id=principal.subject,
                              decision=PaymentReviewDecision.STARTED, reason="", previous_status=previous,
                              new_status=order.status, is_test_review=order.is_test))
    session.add(billing.audit_entry(actor=principal.subject, actor_role="financial_admin", action="review_started",
                               entity_id=order.id, before={"status": previous.value},
                               after={"status": order.status.value}, **_request_context(request)))
    await session.commit()
    return {"order_id": str(order.id), "status": order.status.value}


async def _decide(order_id: uuid.UUID, decision: PaymentReviewDecision, reason: str,
                  request: Request, session: SessionDep, principal: PrincipalDep, settings: SettingsDep) -> dict:
    order = await billing.order_by_id(session, order_id, lock=True)
    if not order:
        raise HTTPException(404, detail="سفارش پیدا نشد.")
    try:
        order = await billing.review_order(session, order=order, reviewer_id=principal.subject,
                                           decision=decision, reason=reason, **_request_context(request))
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    return billing.payment_order_public(order, settings=settings)


@financial_router.post("/payment-orders/{order_id}/approve")
async def approve_payment(order_id: uuid.UUID, request: Request, session: SessionDep,
                          principal: PrincipalDep, settings: SettingsDep) -> dict:
    order = await billing.order_by_id(session, order_id)
    if order is None:
        raise HTTPException(404, detail="سفارش پیدا نشد.")
    decision = PaymentReviewDecision.TEST_APPROVED if order.is_test else PaymentReviewDecision.APPROVED
    return await _decide(order_id, decision, "", request, session, principal, settings)


@financial_router.post("/payment-orders/{order_id}/reject")
async def reject_payment(order_id: uuid.UUID, payload: ReviewBody, request: Request,
                         session: SessionDep, principal: PrincipalDep, settings: SettingsDep) -> dict:
    if not payload.reason.strip():
        raise HTTPException(422, detail="دلیل رد درخواست الزامی است.")
    return await _decide(order_id, PaymentReviewDecision.REJECTED, payload.reason, request, session, principal, settings)


@financial_router.get("/plans")
async def financial_plans(session: SessionDep) -> dict:
    plans = await billing.list_plans(session, include_inactive=True)
    return {"items": [billing.public_plan(plan) for plan in plans]}


@financial_router.post("/plans", status_code=201)
async def create_subscription_plan(
    payload: PlanCreateBody, session: SessionDep, principal: PrincipalDep,
) -> dict:
    if payload.id == "free" and payload.price_toman != 0:
        raise HTTPException(422, detail="پلن پایه باید رایگان باقی بماند.")
    if payload.id != "free" and payload.price_toman <= 0:
        raise HTTPException(422, detail="پلن پولی باید قیمت مثبت داشته باشد.")
    row = SubscriptionPlan(id=payload.id, **payload.model_dump(exclude={"id"}))
    session.add(row)
    audit_id = uuid.uuid5(uuid.NAMESPACE_URL, f"shekarchi:billing-plan:{row.id}")
    session.add(billing.audit_entry(
        actor=principal.subject, actor_role="financial_admin", action="subscription_plan_created",
        entity_id=audit_id, entity_type="subscription_plan",
        after=billing.public_plan(billing.Plan(
            id=row.id, title=row.title, price_toman=row.price_toman, duration_days=row.duration_days,
            listing_quota=row.listing_quota, sms_quota=row.sms_quota, regions_quota=row.regions_quota,
            advisor_quota=row.advisor_quota, is_unlimited=row.is_unlimited,
            features=tuple(row.features), description=row.description, is_active=row.is_active,
            sort_order=row.sort_order,
        )),
    ))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, detail="شناسهٔ پلن از قبل وجود دارد.") from exc
    plan = await billing.get_plan(session, row.id, include_inactive=True)
    if plan is None:
        raise HTTPException(500, detail="پلن پس از ایجاد قابل بازیابی نیست.")
    return billing.public_plan(plan)


@financial_router.put("/plans/{plan_id}")
async def update_subscription_plan(
    plan_id: str, payload: PlanUpdateBody, session: SessionDep, principal: PrincipalDep,
) -> dict:
    row = (await session.exec(
        sa_select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id).with_for_update()
    )).first()
    if row is None:
        raise HTTPException(404, detail="پلن پیدا نشد.")
    if plan_id == "free" and (payload.price_toman != 0 or not payload.is_active):
        raise HTTPException(409, detail="پلن پایه باید فعال و رایگان بماند.")
    if plan_id != "free" and payload.price_toman <= 0:
        raise HTTPException(422, detail="پلن پولی باید قیمت مثبت داشته باشد.")
    before = billing.public_plan(await billing.get_plan(session, plan_id, include_inactive=True))
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.add(billing.audit_entry(
        actor=principal.subject, actor_role="financial_admin", action="subscription_plan_updated",
        entity_id=uuid.uuid5(uuid.NAMESPACE_URL, f"shekarchi:billing-plan:{row.id}"),
        entity_type="subscription_plan", before=before,
        after=payload.model_dump() | {"id": row.id},
    ))
    await session.commit()
    await session.refresh(row)
    updated = await billing.get_plan(session, row.id, include_inactive=True)
    if updated is None:
        raise HTTPException(500, detail="پلن پس از ویرایش قابل بازیابی نیست.")
    return billing.public_plan(updated)


@financial_router.get("/payment-attempts")
async def financial_payment_attempts(
    session: SessionDep,
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    query = sa_select(PaymentAttempt).where(PaymentAttempt.provider == "ZIBAL")
    if status_filter:
        query = query.where(PaymentAttempt.status == status_filter.upper())
    rows = (await session.exec(
        query.order_by(PaymentAttempt.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all()
    items: list[dict] = []
    for attempt in rows:
        order = await billing.order_by_id(session, attempt.order_id)
        items.append(zibal_billing.public_attempt(attempt, order))
    return {"items": items, "page": page, "page_size": page_size}


@financial_router.get("/reconciliation")
async def financial_reconciliation_queue(
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    query = sa_select(PaymentAttempt).where(
        PaymentAttempt.provider == "ZIBAL",
        PaymentAttempt.status.in_(["PENDING", "UNKNOWN", "RECONCILIATION_REQUIRED"]),
    )
    rows = (await session.exec(
        query.order_by(PaymentAttempt.updated_at).offset((page - 1) * page_size).limit(page_size)
    )).all()
    items: list[dict] = []
    for attempt in rows:
        order = await billing.order_by_id(session, attempt.order_id)
        items.append(zibal_billing.public_attempt(attempt, order))
    return {"items": items, "page": page, "page_size": page_size}


@financial_router.post("/reconciliation/run")
async def run_financial_reconciliation(
    request: Request, session: SessionDep, settings: SettingsDep,
    limit: int = Query(default=5, ge=1, le=20),
    older_than_minutes: int = Query(default=5, ge=1, le=1440),
) -> dict:
    runtime_settings = await _get_zibal_runtime_settings(session, settings)
    if runtime_settings is None:
        raise HTTPException(503, detail={"error": "zibal_not_configured", "message": "استعلام زیبال فعال نیست."})
    counts = await zibal_billing.reconcile_stale_zibal_attempts(
        session, provider=ZibalPaymentProvider(runtime_settings), limit=limit,
        older_than=timedelta(minutes=older_than_minutes), **_request_context(request),
    )
    return {"success": True, **counts}


@financial_router.post("/payment-attempts/{attempt_id}/reconcile")
async def reconcile_financial_attempt(
    attempt_id: uuid.UUID, request: Request, session: SessionDep, settings: SettingsDep,
) -> dict:
    runtime_settings = await _get_zibal_runtime_settings(session, settings)
    if runtime_settings is None:
        raise HTTPException(503, detail={"error": "zibal_not_configured", "message": "استعلام زیبال فعال نیست."})
    try:
        order, attempt, result = await zibal_billing.reconcile_zibal_attempt(
            session, attempt_id=attempt_id, provider=ZibalPaymentProvider(runtime_settings),
            **_request_context(request),
        )
    except LookupError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ZibalError as exc:
        raise HTTPException(503, detail={"error": exc.code, "message": "استعلام تراکنش انجام نشد."}) from exc
    return {"result": result, "order": billing.payment_order_public(order, settings=settings),
            "payment_attempt": zibal_billing.public_attempt(attempt, order)}


@financial_router.post("/payment-attempts/{attempt_id}/confirm-not-paid")
async def confirm_zibal_not_paid(
    attempt_id: uuid.UUID, payload: ConfirmNotPaidBody, request: Request,
    session: SessionDep, principal: PrincipalDep, settings: SettingsDep,
) -> dict:
    if not payload.confirmed_not_paid:
        raise HTTPException(422, detail="تأیید بررسی پنل پذیرندهٔ زیبال الزامی است.")
    try:
        order, attempt = await zibal_billing.confirm_zibal_attempt_not_paid(
            session,
            attempt_id=attempt_id,
            actor=principal.subject,
            reason=payload.reason,
            **_request_context(request),
        )
    except LookupError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    return {"order": billing.payment_order_public(order, settings=settings),
            "payment_attempt": zibal_billing.public_attempt(attempt, order)}


@financial_router.get("/audit-logs")
async def financial_audit_logs(
    session: SessionDep,
    action: str | None = Query(default=None, max_length=128),
    entity_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict:
    query = sa_select(FinancialAuditLog)
    if action:
        query = query.where(FinancialAuditLog.action == action)
    if entity_id:
        query = query.where(FinancialAuditLog.entity_id == entity_id)
    rows = (await session.exec(
        query.order_by(FinancialAuditLog.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all()
    return {"items": [{
        "id": str(row.id), "actor_user_id": row.actor_user_id, "actor_role": row.actor_role,
        "action": row.action, "entity_type": row.entity_type, "entity_id": str(row.entity_id),
        "before": row.before_data, "after": row.after_data, "request_id": row.request_id,
        "created_at": row.created_at.isoformat(),
    } for row in rows], "page": page, "page_size": page_size}
