"""Lightweight health probes for Postgres and Redis.

Used by the `/readyz` endpoint to do a real check instead of returning
"skipped". Each function returns a small dict the endpoint can serialize.

Concept: a readiness check should be *cheap* and *real*. Cheap means a few
milliseconds — no expensive joins, no app-level queries. Real means it
actually round-trips the dependency, not just "did the pool initialize."
"""

from __future__ import annotations

from typing import TypedDict

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger

logger = get_logger(__name__)


class CheckResult(TypedDict):
    status: str  # "ok" | "error"
    detail: str | None  # error message when status == "error"


async def check_database(engine: AsyncEngine) -> CheckResult:
    """Execute `SELECT 1` against the configured Postgres."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "detail": None}
    except Exception as exc:
        logger.warning("health.db.failed", error=str(exc))
        return {"status": "error", "detail": str(exc)}


async def check_redis(client: aioredis.Redis) -> CheckResult:
    """PING the configured Redis."""
    try:
        pong = await client.ping()
        if pong is not True and pong != "PONG":
            return {"status": "error", "detail": f"unexpected ping response: {pong!r}"}
        return {"status": "ok", "detail": None}
    except Exception as exc:
        logger.warning("health.redis.failed", error=str(exc))
        return {"status": "error", "detail": str(exc)}
