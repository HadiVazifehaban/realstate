"""Schemas for OTP quick-registration and the professional funnel.

Every payload that carries a mobile normalizes it to E.164 (``+989...``)
-- Persian/Arabic digits, spaces and ``09``/``+98``/``0098`` prefixes all
fold to one form -- and every sensitive payload forbids unknown fields
(``extra="forbid"``) so a caller cannot smuggle ``assigned_role``,
``registration_status`` or ``mobile_verified`` past validation.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.core.mobile import MobileError, normalize_mobile

_GENERIC_OTP_ERROR = "کد واردشده صحیح نیست یا منقضی شده است"


class MobileIn(BaseModel):
    """Shared mobile field with E.164 normalization."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    mobile: str = Field(min_length=10, max_length=20)

    @field_validator("mobile")
    @classmethod
    def _normalize_mobile(cls, value: str) -> str:
        try:
            return normalize_mobile(value)
        except MobileError:
            raise ValueError("شماره موبایل معتبر وارد کنید.") from None


class OtpRequestIn(MobileIn):
    """``POST /auth/otp/request`` -- purpose is informational only."""

    purpose: Literal["login", "professional"] = "login"


class OtpRequestOut(BaseModel):
    ok: bool = True
    message: str = "کد تأیید ارسال شد."
    retry_after: int = 0


class OtpVerifyIn(MobileIn):
    """``POST /auth/otp/verify`` -- six ASCII digits."""

    otp_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class OtpVerifyOut(BaseModel):
    ok: bool = True
    message: str = "شماره موبایل تأیید شد."
    registration_token: str = ""
    has_account: bool = False


class QuickRegisterIn(BaseModel):
    """``POST /auth/quick-register`` -- redeem a registration token."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    registration_token: str = Field(min_length=20, max_length=128)


class VerifiedRegistrationIn(QuickRegisterIn):
    """Create a new account only after redeeming a one-time mobile proof."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    @field_validator("first_name", "last_name", "username", "registration_token", mode="before")
    @classmethod
    def _strip_identity(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    first_name: str = Field(min_length=2, max_length=128)
    last_name: str = Field(min_length=2, max_length=128)
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}$")
    password: SecretStr = Field(min_length=12, max_length=128)


class ProfessionalBaseIn(BaseModel):
    """Shared identity block of the professional funnel."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    registration_token: str = Field(min_length=20, max_length=128)
    first_name: str = Field(min_length=2, max_length=128)
    last_name: str = Field(min_length=2, max_length=128)
    email: str = Field(default="", max_length=255)
    cities: list[str] = Field(default_factory=list, max_length=10)
    accepted_terms: bool = False

    @field_validator("email")
    @classmethod
    def _email_valid(cls, value: str) -> str:
        value = (value or "").strip().lower()
        if not value:
            return ""
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("ایمیل معتبر وارد کنید.")
        return value

    @field_validator("accepted_terms")
    @classmethod
    def _terms_required(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("پذیرش قوانین الزامی است.")
        return True


class JuniorBrokerIn(ProfessionalBaseIn):
    agency_name: str = Field(default="", max_length=255)
    agency_invite_code: str = Field(default="", max_length=64)
    experience_years: int = Field(default=0, ge=0, le=60)
    activity_fields: list[str] = Field(default_factory=list, max_length=10)


class SeniorBrokerIn(ProfessionalBaseIn):
    experience_years: int = Field(ge=0, le=60)
    agency_name: str = Field(default="", max_length=255)
    specialty: str = Field(default="", max_length=255)
    certificate_ref: str = Field(default="", max_length=255)


class AgencyManagerIn(ProfessionalBaseIn):
    referral_code: str = Field(default="", max_length=16)
    agency_official_name: str = Field(min_length=2, max_length=255)
    agency_brand_name: str = Field(default="", max_length=255)
    trade_code: str = Field(min_length=2, max_length=64)
    registration_no: str = Field(default="", max_length=64)
    national_id: str = Field(default="", max_length=32)
    landline: str = Field(default="", max_length=32)
    office_address: str = Field(min_length=5, max_length=1000)
    latitude: float = Field(default=0.0, ge=-90, le=90)
    longitude: float = Field(default=0.0, ge=-180, le=180)
    consultant_count: int = Field(default=1, ge=1, le=10000)
    agency_docs_ref: str = Field(min_length=2, max_length=512)


class DataAnalystIn(ProfessionalBaseIn):
    organization: str = Field(min_length=2, max_length=255)
    position: str = Field(min_length=2, max_length=255)
    invite_code: str = Field(min_length=4, max_length=64)
    data_purpose: str = Field(min_length=10, max_length=2000)
    analysis_type: str = Field(default="", max_length=255)


class ProfessionalSubmitOut(BaseModel):
    ok: bool = True
    message: str = "درخواست شما ثبت شد و در صف بررسی قرار گرفت."
    application_id: str = ""
    status: str = "ROLE_REVIEW_PENDING"


class RegistrationStatusOut(BaseModel):
    mobile_verified: bool = False
    has_account: bool = False
    application_status: str = ""
    requested_role: str = ""


class SessionExchangeIn(BaseModel):
    """``POST /auth/session`` -- swap a registration token for realm tokens."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    registration_token: str = Field(min_length=20, max_length=128)


class SessionOut(BaseModel):
    access_token: str = ""
    refresh_token: str = ""
    expires_in: int = 0
    token_type: str = "Bearer"
    test_mode: bool = False


__all__ = [
    "AgencyManagerIn",
    "DataAnalystIn",
    "JuniorBrokerIn",
    "MobileIn",
    "OtpRequestIn",
    "OtpRequestOut",
    "OtpVerifyIn",
    "OtpVerifyOut",
    "ProfessionalBaseIn",
    "ProfessionalSubmitOut",
    "QuickRegisterIn",
    "RegistrationStatusOut",
    "SeniorBrokerIn",
    "SessionExchangeIn",
    "SessionOut",
]
