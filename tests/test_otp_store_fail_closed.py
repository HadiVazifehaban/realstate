import pytest
import redis.asyncio as aioredis

from app.services.otp_store import OtpStore


@pytest.mark.asyncio
async def test_otp_store_does_not_fall_back_to_memory_by_default():
    store = OtpStore("")
    with pytest.raises(RuntimeError, match="OTP Redis is not configured"):
        await store.get(store.key("challenge", "sample"))


@pytest.mark.asyncio
async def test_otp_memory_store_requires_explicit_test_flag():
    store = OtpStore("", allow_memory_fallback=True)
    await store.set(store.key("challenge", "sample"), "test", ex=30)
    assert await store.get(store.key("challenge", "sample")) == "test"


@pytest.mark.asyncio
async def test_redis_connection_failure_fails_closed(monkeypatch):
    class UnavailableRedis:
        async def ping(self):
            raise OSError("test transport failure")

    monkeypatch.setattr(aioredis, "from_url", lambda *args, **kwargs: UnavailableRedis())
    store = OtpStore("redis://unavailable.invalid/0")
    with pytest.raises(RuntimeError, match="OTP Redis is unavailable"):
        await store.get(store.key("challenge", "sample"))
    # Failure stays fail-closed on subsequent operations too.
    with pytest.raises(RuntimeError, match="OTP Redis is unavailable"):
        await store.get(store.key("challenge", "sample"))
