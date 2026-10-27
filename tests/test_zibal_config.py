from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import NodeMode, Settings
from app.models.billing import ZibalGatewayConfiguration
from app.services.zibal import ZibalNotConfigured
from app.services.zibal_config import load_zibal_settings, public_zibal_settings, save_zibal_settings
from tests.conftest import create_sqlite_schema


@pytest.mark.asyncio
async def test_zibal_merchant_is_encrypted_at_rest_and_never_returned_by_settings_api() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_sqlite_schema(engine, "zibal_gateway_configuration")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    secret = "merchant-secret-ABCDEF"
    settings = Settings(node_mode=NodeMode.LOCAL, zibal_credential_encryption_key=Fernet.generate_key().decode())

    async with factory() as session:
        row = await save_zibal_settings(
            session, settings=settings, actor="system-admin", enabled=False, test_mode=True,
            callback_url="http://localhost:8082/api/v1/billing/zibal/callback",
            result_url="http://localhost:3000/dashboard/billing", expected_version=0,
            merchant_code=secret, clear_merchant=False,
        )
        await session.commit()
        assert secret not in row.merchant_ciphertext
        assert row.merchant_last4 == "CDEF"

        public = await public_zibal_settings(session, settings)
        assert public["merchant_configured"] is True
        assert public["merchant_masked"] == "••••CDEF"
        assert secret not in repr(public)

        runtime = await load_zibal_settings(session, settings)
        assert runtime.zibal_merchant == secret
        assert runtime.zibal_enabled is False

        with pytest.raises(RuntimeError, match="هم‌زمان"):
            await save_zibal_settings(
                session, settings=settings, actor="system-admin", enabled=False, test_mode=True,
                callback_url="http://localhost:8082/api/v1/billing/zibal/callback",
                result_url="http://localhost:3000/dashboard/billing", expected_version=0,
                merchant_code=None, clear_merchant=False,
            )

    await engine.dispose()


@pytest.mark.asyncio
async def test_zibal_credential_storage_fails_closed_without_encryption_key() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_sqlite_schema(engine, "zibal_gateway_configuration")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        with pytest.raises(ZibalNotConfigured):
            await save_zibal_settings(
                session, settings=Settings(node_mode=NodeMode.LOCAL), actor="system-admin",
                enabled=False, test_mode=True,
                callback_url="http://localhost:8082/api/v1/billing/zibal/callback",
                result_url="http://localhost:3000/dashboard/billing", expected_version=0,
                merchant_code="merchant-secret", clear_merchant=False,
            )
        assert await session.get(ZibalGatewayConfiguration, 1) is None
    await engine.dispose()
