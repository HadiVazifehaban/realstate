"""Session-token / phone cache for the scraper.

Uses Redis (``redis.asyncio``) when reachable and transparently falls back to an
in-process TTL cache, so the office node keeps working with no Redis running.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger

logger = get_logger("app.scraper.cache")


class _MemoryTTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at and expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expires_at = (time.time() + ttl) if ttl else 0.0
        self._store[key] = (expires_at, value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class TokenCache:
    """Async cache facade with optional Redis backend."""

    def __init__(self, redis_url: str | None = None, *, namespace: str = "avg") -> None:
        self._namespace = namespace
        self._redis_url = redis_url
        self._redis = None
        self._memory = _MemoryTTLCache()
        self._redis_checked = False

    def _key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    async def _get_redis(self):
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        if not self._redis_url:
            return None
        try:  # pragma: no cover - depends on a live Redis
            import redis.asyncio as aioredis

            client = aioredis.from_url(self._redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
            logger.info("scraper cache: using Redis backend")
        except Exception as exc:  # noqa: BLE001
            logger.info("scraper cache: Redis unavailable (%s), using memory", exc)
            self._redis = None
        return self._redis

    async def get(self, key: str) -> Any | None:
        redis = await self._get_redis()
        if redis is not None:
            try:
                return await redis.get(self._key(key))
            except Exception:  # noqa: BLE001
                pass
        return await self._memory.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        redis = await self._get_redis()
        if redis is not None:
            try:
                await redis.set(self._key(key), value, ex=ttl)
                return
            except Exception:  # noqa: BLE001
                pass
        await self._memory.set(key, value, ttl)

    async def delete(self, key: str) -> None:
        redis = await self._get_redis()
        if redis is not None:
            try:
                await redis.delete(self._key(key))
            except Exception:  # noqa: BLE001
                pass
        await self._memory.delete(key)
