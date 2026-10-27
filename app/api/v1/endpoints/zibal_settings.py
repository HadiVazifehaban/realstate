"""System-admin-only management of encrypted Zibal provider credentials."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.exc import IntegrityError

from app.api.deps import SessionDep, SettingsDep, _bearer_token
from app.core.config import AuthMode
from app.core.identity import IdentityError, Principal, principal_from_token, require_approval
from app.models.billing import ZibalGatewayConfiguration
from app.services import billing, zibal_config
from app.services.zibal import ZibalNotConfigured


async def require_zibal_system_admin(request: Request, settings: SettingsDep) -> Principal:
    if settings.auth_mode is not AuthMode.KEYCLOAK:
        raise HTTPException(status_code=503, detail="Keycloak authentication is required for gateway settings.")
    try:
        principal = await principal_from_token(_bearer_token(request), settings)
        require_approval(principal, settings)
    except IdentityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    if "ROLE_ADMIN" not in principal.realm_roles:
        raise HTTPException(status_code=403, detail={"error": "system_admin_required"})
    return principal


router = APIRouter()


class ZibalSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: int = Field(ge=0)
    enabled: bool
    test_mode: bool
    merchant_code: SecretStr | None = None
    clear_merchant: bool = False
    callback_url: str = Field(min_length=1, max_length=2048)
    result_url: str = Field(min_length=1, max_length=2048)


@router.get("/config")
async def get_zibal_settings(
    session: SessionDep, settings: SettingsDep,
    _principal: Principal = Depends(require_zibal_system_admin),
) -> dict:
    return await zibal_config.public_zibal_settings(session, settings)


@router.put("/config")
async def update_zibal_settings(
    payload: ZibalSettingsUpdate,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    principal: Principal = Depends(require_zibal_system_admin),
) -> dict:
    before = await zibal_config.public_zibal_settings(session, settings)
    try:
        saved = await zibal_config.save_zibal_settings(
            session,
            settings=settings,
            actor=principal.subject,
            enabled=payload.enabled,
            test_mode=payload.test_mode,
            callback_url=payload.callback_url,
            result_url=payload.result_url,
            expected_version=payload.version,
            merchant_code=payload.merchant_code.get_secret_value() if payload.merchant_code is not None else None,
            clear_merchant=payload.clear_merchant,
        )
        session.add(billing.audit_entry(
            actor=principal.subject,
            actor_role="ROLE_ADMIN",
            action="zibal_gateway_configuration_updated",
            entity_type="zibal_gateway_configuration",
            entity_id=uuid.uuid5(uuid.NAMESPACE_URL, "shekarchi:zibal-gateway-configuration"),
            before=before,
            after={
                "enabled": saved.enabled,
                "test_mode": saved.test_mode,
                "merchant_configured": bool(saved.merchant_ciphertext),
                "merchant_masked": f"••••{saved.merchant_last4}" if saved.merchant_last4 else None,
                "callback_url": saved.callback_url,
                "result_url": saved.result_url,
                "version": saved.version,
            },
            request_id=request.headers.get("x-request-id", ""),
            ip_address=request.client.host if request.client else "",
            user_agent=request.headers.get("user-agent", ""),
        ))
        await session.commit()
    except ZibalNotConfigured as exc:
        await session.rollback()
        raise HTTPException(status_code=503, detail={"error": exc.code, "message": str(exc)}) from exc
    except RuntimeError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="تنظیمات هم‌زمان تغییر کرده است؛ صفحه را تازه‌سازی کنید.") from exc
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await zibal_config.public_zibal_settings(session, settings)
