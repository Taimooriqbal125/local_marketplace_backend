# app/core/redis.py

"""Centralized async Redis client used by caching and rate limiting.

This module exposes one shared Redis connection for the whole app and helper
utilities for startup health checks and graceful shutdown.
"""

from __future__ import annotations

from urllib.parse import urlparse

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logging import logger

# Centralized via Settings (.env -> app/core/config.py)
REDIS_URL = settings.REDIS_URL


def _redis_log_target(url: str) -> str:
    """Return a sanitized Redis target string safe for logs."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "unknown-host"
        port = parsed.port or 6379
        db = parsed.path.lstrip("/") or "0"
        scheme = parsed.scheme or "redis"
        return f"{scheme}://{host}:{port}/{db}"
    except Exception:
        return "redis://redacted"


REDIS_LOG_TARGET = _redis_log_target(REDIS_URL)

# Shared async Redis client.
# - decode_responses=True returns strings instead of bytes
# - health_check_interval keeps long-lived connections healthy
redis: Redis = Redis.from_url(
    REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    health_check_interval=30,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
)


def get_redis() -> Redis:
    """Return the shared Redis client instance."""
    return redis


async def test_redis_connection() -> bool:
    """Ping Redis during app startup and return connection status."""
    try:
        pong = await redis.ping()
        if pong:
            logger.info("Redis connection successful", redis_target=REDIS_LOG_TARGET)
            return True

        logger.error("Redis ping returned falsy response", redis_target=REDIS_LOG_TARGET)
        return False
    except RedisError as exc:
        logger.error("Redis connection error", error=str(exc), redis_target=REDIS_LOG_TARGET)
        return False


async def close_redis_connection() -> None:
    """Close Redis connection pool gracefully on app shutdown."""
    try:
        await redis.aclose()
        logger.info("Redis connection closed")
    except RedisError as exc:
        logger.error("Failed to close Redis connection", error=str(exc))