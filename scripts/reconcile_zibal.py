"""Run one bounded Zibal reconciliation pass (intended for an external cron)."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import timedelta

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal, engine
from app.services.zibal import ZibalNotConfigured, ZibalPaymentProvider
from app.services.zibal_billing import reconcile_stale_zibal_attempts


async def _run(limit: int, older_than_minutes: int) -> int:
    settings = get_settings()
    provider = ZibalPaymentProvider(settings)
    try:
        provider.ensure_ready()
    except ZibalNotConfigured as exc:
        print(json.dumps({"enabled": False, "reason": exc.code}))
        return 2

    try:
        async with AsyncSessionLocal() as session:
            result = await reconcile_stale_zibal_attempts(
                session,
                provider=provider,
                older_than=timedelta(minutes=older_than_minutes),
                limit=limit,
            )
        print(json.dumps({"enabled": True, **result}, sort_keys=True))
        return 0
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--older-than-minutes", type=int, default=5)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 200 or args.older_than_minutes < 1:
        parser.error("--limit must be 1..200 and --older-than-minutes must be positive")
    return asyncio.run(_run(args.limit, args.older_than_minutes))


if __name__ == "__main__":
    raise SystemExit(main())
