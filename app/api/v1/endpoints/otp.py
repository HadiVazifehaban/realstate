"""OTP challenge management endpoints for Iran-mobile quick registration."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, SettingsDep
from app.core.config import Settings
from app.core.logging import get_logger
from app.core.mobile import MobileError, normalize_mobile
from app.services.otp_service import (
    OtpRequestResult,
    OtpVerifyResult,
    audit_trail,
    is_mobile_verified,
    request_otp,
    verify_otp,
)

logger = get_logger("app.api.otp")

router = APIRouter(prefix="/otp", tags=["OTP"])


class OtpRequestRequest(BaseModel):
    mobile: str = Field(..., description="Mobile number in E.164 format (e.g., +989123456789)")
    purpose: str = Field(default="login", description="Purpose: 'login' or 'register'")


class OtpVerifyRequest(BaseModel):
    mobile: str = Field(..., description="Mobile number in E.164 format")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")


class OtpStatusResponse(BaseModel):
    mobile: str
    is_verified: bool
    verified_at: int | None = None


@router.post("/request", response_model=OtpRequestResult)
async def request_otp_endpoint(
    payload: OtpRequestRequest,
    settings: SettingsDep,
    session: SessionDep,
) -> OtpRequestResult:
    """Request an OTP challenge for a mobile number.
    
    Validates the mobile number, enforces rate limits, and dispatches a 6-digit code
    via SMS. In test mode, the code is returned in the response.
    """
    try:
        mobile_e164 = normalize_mobile(payload.mobile)
    except MobileError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_mobile", "message": str(exc)})
    
    result = await request_otp(
        settings=settings,
        mobile_e164=mobile_e164,
        purpose=payload.purpose,
    )
    return result


@router.post("/verify", response_model=OtpVerifyResult)
async def verify_otp_endpoint(
    payload: OtpVerifyRequest,
    settings: SettingsDep,
    session: SessionDep,
) -> OtpVerifyResult:
    """Verify an OTP code for a mobile number.
    
    Checks the code against the stored hash. On success, consumes the challenge
    and returns a registration token for the next step.
    """
    try:
        mobile_e164 = normalize_mobile(payload.mobile)
    except MobileError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_mobile", "message": str(exc)})
    
    result = await verify_otp(
        settings=settings,
        mobile_e164=mobile_e164,
        code=payload.code,
    )
    return result


@router.get("/status/{mobile}", response_model=OtpStatusResponse)
async def get_otp_status_endpoint(
    mobile: str,
    settings: SettingsDep,
    session: SessionDep,
) -> OtpStatusResponse:
    """Check if a mobile number is currently verified.
    
    Returns true if the mobile has a verified grace period active.
    """
    try:
        mobile_e164 = normalize_mobile(mobile)
    except MobileError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_mobile", "message": str(exc)})
    
    is_verified = await is_mobile_verified(settings, mobile_e164)
    return OtpStatusResponse(mobile=mobile_e164, is_verified=is_verified)


@router.get("/audit/{mobile}")
async def get_otp_audit_endpoint(
    mobile: str,
    settings: SettingsDep,
    session: SessionDep,
) -> list[dict]:
    """Get the recent OTP audit trail for a mobile number.
    
    Returns a list of recent events (masked mobile, timestamp, outcome) for
    support and debugging purposes.
    """
    try:
        mobile_e164 = normalize_mobile(mobile)
    except MobileError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_mobile", "message": str(exc)})
    
    trail = await audit_trail(settings, mobile_e164)
    return trail
