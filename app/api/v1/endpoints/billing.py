"""Card-to-card subscription checkout and financial review API."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select as sa_select
from sqlalchemy.exc import IntegrityError

from app.api.deps import PrincipalDep, SessionDep, SettingsDep, require_financial_admin
from app.models.billing import AgencySubscription, PaymentOrder, PaymentReceipt, PaymentReview
from app.models.enums import PaymentOrderStatus, PaymentReviewDecision
from app.services import billing

router = APIRouter()
public_router = APIRouter()
financial_router = APIRouter(dependencies=[Depends(require_financial_admin)])


class CreateOrderBody(BaseModel):
    plan_id: str = Field(min_length=1, max_length=32)


class ReviewBody(BaseModel):
    reason: str = Field(default="", max_length=2000)


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


def _order_access(order: PaymentOrder, principal: PrincipalDep) -> None:
    """Allow the uploader, or anyone in the same agency, to see the order."""
    tenant = (principal.tenant_id or "").strip()
    if order.user_id != principal.subject and order.agency_id != tenant:
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
    return {**billing.payment_order_public(order, settings=settings), "receipt": _receipt_metadata(receipt)}


@public_router.get("/plans")
async def get_plans() -> dict:
    return {"plans": [billing.public_plan(plan) for plan in billing.PLANS.values()]}


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_payment_order(
    payload: CreateOrderBody, session: SessionDep, principal: PrincipalDep, settings: SettingsDep
) -> dict:
    try:
        order, plan = await billing.create_order(
            session, agency_id=_agency_id(principal), user_id=principal.subject,
            plan_id=payload.plan_id, settings=settings,
        )
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail={"error": "payment_not_configured", "message": "تنظیم امن پرداخت انجام نشده است."}) from exc
    return {**billing.payment_order_public(order, settings=settings), "plan_detail": billing.public_plan(plan)}


@router.get("/orders")
async def list_payment_orders(
    session: SessionDep, principal: PrincipalDep, settings: SettingsDep,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status_filter: PaymentOrderStatus | None = Query(default=None, alias="status"),
) -> dict:
    query = sa_select(PaymentOrder).where(
        PaymentOrder.agency_id == _agency_id(principal),
        PaymentOrder.user_id == principal.subject,
    )
    if status_filter:
        query = query.where(PaymentOrder.status == status_filter)
    query = query.order_by(PaymentOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await session.exec(query)).all()
    return {"items": [billing.payment_order_public(row, settings=settings) for row in rows], "page": page, "page_size": page_size}


@router.get("/orders/{order_id}")
async def get_payment_order(order_id: uuid.UUID, session: SessionDep, principal: PrincipalDep, settings: SettingsDep) -> dict:
    order = await billing.order_by_id(session, order_id)
    if not order:
        raise HTTPException(404, detail="سفارش پیدا نشد.")
    _order_access(order, principal)
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
    _order_access(order, principal)
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
async def current_subscription(session: SessionDep, principal: PrincipalDep) -> dict:
    agency_id = _agency_id(principal)
    query = sa_select(AgencySubscription).where(
        AgencySubscription.agency_id == agency_id,
        AgencySubscription.status == "active",
        AgencySubscription.expires_at > datetime.now(timezone.utc),
    ).order_by(AgencySubscription.expires_at.desc())
    sub = (await session.exec(query)).first()
    if sub is None or sub.plan not in billing.PLANS:
        plan = billing.PLANS["free"]
        return {"plan": plan.id, "title": plan.title, "status": "active", "starts_at": None, "expires_at": None,
                "listing_quota": plan.listing_quota, "sms_quota": plan.sms_quota,
                "regions_quota": plan.regions_quota, "advisor_quota": plan.advisor_quota,
                "is_unlimited": False, "usage": {}}
    return {"plan": sub.plan, "title": billing.PLANS[sub.plan].title, "status": sub.status,
            "starts_at": sub.starts_at.isoformat(), "expires_at": sub.expires_at.isoformat(),
            "listing_quota": sub.listing_quota, "sms_quota": sub.sms_quota,
            "regions_quota": sub.regions_quota, "advisor_quota": sub.advisor_quota,
            "is_unlimited": sub.is_unlimited, "usage": {}}


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

