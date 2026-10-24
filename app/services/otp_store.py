"""Shared Redis key-value store with an in-process fallback.

The OTP/registration flow needs atomic counters (rate limits), TTL keys
(challenges, tokens) and hash fields (audit). ``redis.asyncio`` is used
when reachable; otherwise -- and always in the test-suite -- a threaded,
TTL-aware in-process store with the same async surface stands in, so the
office node and the tests keep working with no Redis running.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from app.core.logging import get_logger

logger = get_logger("app.otp.store")


class _MemoryStore:
    """Thread-safe TTL dict emulating the subset of Redis the OTP flow uses."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._kv: dict[str, tuple[float, str]] = {}
        self._hash: dict[str, dict[str, str]] = {}
        self._hash_exp: dict[str, float] = {}

    @staticmethod
    def _expired(expires_at: float) -> bool:
        return bool(expires_at) and expires_at <= time.time()

    def _purge(self, key: str) -> None:
        exp, _ = self._kv.get(key, (0.0, ""))
        if key in self._kv and self._expired(exp):
            self._kv.pop(key, None)
        if key in self._hash and self._expired(self._hash_exp.get(key, 0.0)):
            self._hash.pop(key, None)
            self._hash_exp.pop(key, None)

    async def get(self, key: str) -> str | None:
        with self._lock:
            self._purge(key)
            item = self._kv.get(key)
            return item[1] if item else None

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        with self._lock:
            self._purge(key)
            if nx and key in self._kv:
                return False
            self._kv[key] = (time.time() + ex if ex else 0.0, value)
            return True

    async def delete(self, *keys: str) -> int:
        with self._lock:
            removed = 0
            for key in keys:
                self._purge(key)
                removed += bool(self._kv.pop(key, None) is not None)
                removed += bool(self._hash.pop(key, None) is not None)
                self._hash_exp.pop(key, None)
            return removed

    async def incr(self, key: str) -> int:
        with self._lock:
            self._purge(key)
            current = int(self._kv.get(key, (0.0, "0"))[1] or 0) + 1
            exp, _ = self._kv.get(key, (0.0, ""))
            self._kv[key] = (exp, str(current))
            return current

    async def expire(self, key: str, seconds: int) -> bool:
        with self._lock:
            self._purge(key)
            if key in self._kv:
                _, value = self._kv[key]
                self._kv[key] = (time.time() + seconds, value)
                return True
            if key in self._hash:
                self._hash_exp[key] = time.time() + seconds
                return True
            return False

    async def ttl(self, key: str) -> int:
        with self._lock:
            self._purge(key)
            if key in self._kv:
                exp, _ = self._kv[key]
                return int(exp - time.time()) if exp else -1
            if key in self._hash:
                exp = self._hash_exp.get(key, 0.0)
                return int(exp - time.time()) if exp else -1
            return -2

    async def hget(self, key: str, field: str) -> str | None:
        with self._lock:
            self._purge(key)
            return (self._hash.get(key) or {}).get(field)

    async def hset(self, key: str, field: str, value: str) -> int:
        with self._lock:
            self._purge(key)
            created = field not in (self._hash.get(key) or {})
            self._hash.setdefault(key, {})[field] = value
            return 1 if created else 0

    async def hgetall(self, key: str) -> dict[str, str]:
        with self._lock:
            self._purge(key)
            return dict(self._hash.get(key) or {})

    async def compare_and_delete(self, key: str, expected: str) -> bool:
        """Delete only if the current value equals ``expected`` (anti-replay)."""
        with self._lock:
            self._purge(key)
            item = self._kv.get(key)
            if item and item[1] == expected:
                self._kv.pop(key, None)
                return True
            return False

    async def increment_challenge_attempts(self, key: str, expected: str, maximum: int) -> int:
        """Atomically update a matching challenge; 0=kept, 1=deleted, -1=stale."""
        with self._lock:
            self._purge(key)
            item = self._kv.get(key)
            if item is None or item[1] != expected:
                return -1
            try:
                challenge = json.loads(item[1])
                attempts = int(challenge.get("attempts", 0)) + 1
            except (ValueError, TypeError, AttributeError):
                self._kv.pop(key, None)
                return 1
            if attempts >= maximum:
                self._kv.pop(key, None)
                return 1
            challenge["attempts"] = attempts
            self._kv[key] = (item[0], json.dumps(challenge))
            return 0

    async def rpush_trim(self, key: str, value: str, keep: int) -> None:
        with self._lock:
            self._purge(key)
            raw = self._kv.get(key, (0.0, "[]"))[1]
            try:
                items = json.loads(raw) if raw else []
            except (ValueError, TypeError):
                items = []
            items.append(value)
            self._kv[key] = (0.0, json.dumps(items[-keep:]))

    async def lrange(self, key: str) -> list[str]:
        with self._lock:
            self._purge(key)
            raw = self._kv.get(key, (0.0, "[]"))[1]
            try:
                items = json.loads(raw) if raw else []
            except (ValueError, TypeError):
                return []
            return [str(i) for i in items]

class OtpStore:
    """Async KV facade: real Redis when reachable, memory otherwise."""

    _COMPARE_AND_DELETE_LUA = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) else return 0 end"
    )
    _INCREMENT_ATTEMPT_LUA = """
        local current = redis.call('get', KEYS[1])
        if not current or current ~= ARGV[1] then return -1 end
        local ok, challenge = pcall(cjson.decode, current)
        if not ok or type(challenge) ~= 'table' then
          redis.call('del', KEYS[1]); return 1
        end
        challenge.attempts = tonumber(challenge.attempts or 0) + 1
        if challenge.attempts >= tonumber(ARGV[2]) then
          redis.call('del', KEYS[1]); return 1
        end
        local ttl = redis.call('ttl', KEYS[1])
        if ttl < 1 then redis.call('del', KEYS[1]); return 1 end
        redis.call('set', KEYS[1], cjson.encode(challenge), 'EX', ttl)
        return 0
    """

    def __init__(self, redis_url: str | None = None, *, namespace: str = "shekarchi:otp", allow_memory_fallback: bool = False) -> None:
        self._namespace = namespace.rstrip(":")
        self._redis_url = redis_url
        self._allow_memory_fallback = allow_memory_fallback
        self._redis: Any | None = None
        self._checked = False
        self._memory = _MemoryStore()

    def key(self, *parts: str) -> str:
        return ":".join([self._namespace, *[str(p) for p in parts]])

    async def _get_redis(self) -> Any | None:
        if self._checked:
            if self._redis is None and not self._allow_memory_fallback:
                raise RuntimeError("OTP Redis is unavailable")
            return self._redis
        self._checked = True
        if not self._redis_url:
            if self._allow_memory_fallback:
                return None
            raise RuntimeError("OTP Redis is not configured")
        try:  # pragma: no cover - needs a live Redis
            import redis.asyncio as aioredis

            client = aioredis.from_url(self._redis_url, socket_timeout=5)
            await client.ping()
            self._redis = client
        except Exception as exc:  # noqa: BLE001 - fallback is the point
            if not self._allow_memory_fallback:
                raise RuntimeError("OTP Redis is unavailable") from None
            logger.warning("OTP store: Redis unavailable; using test-only memory store")
            self._redis = None
        return self._redis

    async def get(self, key: str) -> str | None:
        client = await self._get_redis()
        if client is None:
            return await self._memory.get(key)
        value = await client.get(key)
        return value.decode() if isinstance(value, bytes) else value

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        client = await self._get_redis()
        if client is None:
            return await self._memory.set(key, value, ex=ex, nx=nx)
        return bool(await client.set(key, value, ex=ex, nx=nx))

    async def delete(self, *keys: str) -> int:
        client = await self._get_redis()
        if client is None or not keys:
            return await self._memory.delete(*keys)
        return int(await client.delete(*keys))

    async def incr(self, key: str) -> int:
        client = await self._get_redis()
        if client is None:
            return await self._memory.incr(key)
        return int(await client.incr(key))


    async def expire(self, key: str, seconds: int) -> bool:
        client = await self._get_redis()
        if client is None:
            return await self._memory.expire(key, seconds)
        return bool(await client.expire(key, seconds))

    async def ttl(self, key: str) -> int:
        client = await self._get_redis()
        if client is None:
            return await self._memory.ttl(key)
        return int(await client.ttl(key))

    async def hget(self, key: str, field: str) -> str | None:
        client = await self._get_redis()
        if client is None:
            return await self._memory.hget(key, field)
        value = await client.hget(key, field)
        return value.decode() if isinstance(value, bytes) else value

    async def hset(self, key: str, field: str, value: str) -> int:
        client = await self._get_redis()
        if client is None:
            return await self._memory.hset(key, field, value)
        return int(await client.hset(key, field, value))

    async def hgetall(self, key: str) -> dict[str, str]:
        client = await self._get_redis()
        if client is None:
            return await self._memory.hgetall(key)
        raw = await client.hgetall(key)
        return {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in raw.items()
        }

    async def compare_and_delete(self, key: str, expected: str) -> bool:
        """Atomic consume: delete only when the value still matches."""
        client = await self._get_redis()
        if client is None:
            return await self._memory.compare_and_delete(key, expected)
        deleted = await client.eval(self._COMPARE_AND_DELETE_LUA, 1, key, expected)
        return int(deleted) == 1

    async def increment_challenge_attempts(self, key: str, expected: str, maximum: int) -> int:
        """Atomically count a wrong guess against the observed challenge value."""
        client = await self._get_redis()
        if client is None:
            return await self._memory.increment_challenge_attempts(key, expected, maximum)
        result = await client.eval(self._INCREMENT_ATTEMPT_LUA, 1, key, expected, maximum)
        return int(result)

    async def rpush_trim(self, key: str, value: str, keep: int) -> None:
        client = await self._get_redis()
        if client is None:
            await self._memory.rpush_trim(key, value, keep)
            return
        pipe = client.pipeline()
        pipe.rpush(key, value)
        pipe.ltrim(key, -keep, -1)
        await pipe.execute()

    async def lrange(self, key: str) -> list[str]:
        client = await self._get_redis()
        if client is None:
            return await self._memory.lrange(key)
        raw = await client.lrange(key, 0, -1)
        return [v.decode() if isinstance(v, bytes) else str(v) for v in raw]


__all__ = ["OtpStore"]

